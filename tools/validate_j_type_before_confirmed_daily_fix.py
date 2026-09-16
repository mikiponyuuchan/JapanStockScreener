from pathlib import Path
from datetime import datetime, time as dt_time
import sys

import pandas as pd

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from services.yahoo_service import _download_history_batch


RESULT_DIR = Path("results")
TRACKING_FILE = Path("data/tracking/j_type_tracking.csv")

J_VERSION = "J1"

# Frozen J1 definition - 2026-08-31
#
# Change1 >= 5.0
# VolumeRatio < 3.0
# BreakoutSignal == False
# New30High == False
# DetectionVolumeVsPre5 >= 1.0
#
# Do not change these conditions during prospective validation.


COL_CODE = "\u30b3\u30fc\u30c9"
COL_NAME = "\u9298\u67c4\u540d"
COL_CLOSE = "\u7d42\u5024"
COL_CHANGE1 = "\u524d\u65e5\u6bd4"


def to_bool(value):
    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
    }


def normalize_history(df):
    if df is None or df.empty:
        return None

    x = df.copy()

    if "Date" in x.columns:
        x["Date"] = pd.to_datetime(
            x["Date"],
            errors="coerce",
        )
        x = x.set_index("Date")

    x.index = pd.to_datetime(
        x.index,
        errors="coerce",
    )

    if getattr(x.index, "tz", None) is not None:
        x.index = x.index.tz_localize(None)

    x = x[
        ~x.index.isna()
    ].sort_index()

    return x


def calc_volume_vs_pre5(history, detection_date):
    x = normalize_history(history)

    if x is None:
        return None

    detection_date = pd.Timestamp(
        detection_date
    ).normalize()

    previous = x[
        x.index.normalize() < detection_date
    ].tail(5)

    today = x[
        x.index.normalize() == detection_date
    ]

    if len(previous) < 5 or today.empty:
        return None

    previous_volume = pd.to_numeric(
        previous["Volume"],
        errors="coerce",
    ).dropna()

    if len(previous_volume) < 5:
        return None

    mean_volume = previous_volume.mean()

    detection_volume = pd.to_numeric(
        today.iloc[-1]["Volume"],
        errors="coerce",
    )

    if (
        pd.isna(mean_volume)
        or mean_volume <= 0
        or pd.isna(detection_volume)
    ):
        return None

    return float(
        detection_volume / mean_volume
    )


def main():
    now = datetime.now()

    # J1 is a daily-close validation.
    # Never lock a partial intraday volume into the tracking file.
    if now.time() < dt_time(15, 30):
        print("=" * 72)
        print("J1 VALIDATION STOPPED")
        print("=" * 72)
        print("Run this tool after 15:30.")
        return

    detection_date = now.date().isoformat()

    result_file = (
        RESULT_DIR
        / f"{detection_date}_stock_result.csv"
    )

    if not result_file.exists():
        print(
            "Result file not found:",
            result_file,
        )
        return

    df = pd.read_csv(
        result_file,
        encoding="utf-8-sig",
        low_memory=False,
    )

    required = [
        COL_CODE,
        COL_NAME,
        COL_CLOSE,
        COL_CHANGE1,
        "VolumeRatio",
        "BreakoutSignal",
        "New30High",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        print(
            "Missing columns:",
            missing,
        )
        return

    work = pd.DataFrame()

    work["Code"] = (
        df[COL_CODE]
        .astype(str)
        .str.strip()
    )

    work["Name"] = df[COL_NAME]

    work["BasePrice"] = pd.to_numeric(
        df[COL_CLOSE],
        errors="coerce",
    )

    work["Change1"] = pd.to_numeric(
        df[COL_CHANGE1],
        errors="coerce",
    )

    work["VolumeRatio"] = pd.to_numeric(
        df["VolumeRatio"],
        errors="coerce",
    )

    work["BreakoutSignal"] = (
        df["BreakoutSignal"]
        .apply(to_bool)
    )

    work["New30High"] = (
        df["New30High"]
        .apply(to_bool)
    )

    # First apply all J1 conditions that are already available.
    prefilter = (
        (work["Change1"] >= 5.0)
        & (work["VolumeRatio"] < 3.0)
        & (~work["BreakoutSignal"])
        & (~work["New30High"])
    )

    candidates = work[
        prefilter
    ].copy()

    print("=" * 72)
    print("J1 PROSPECTIVE VALIDATION")
    print("=" * 72)
    print("Date              :", detection_date)
    print("Prefilter count   :", len(candidates))

    if candidates.empty:
        print("J1 candidates     : 0")
        return

    codes = sorted(
        candidates["Code"]
        .dropna()
        .unique()
        .tolist()
    )

    print("Yahoo history     : downloading")

    history_map = _download_history_batch(
        codes,
        period="3mo",
        batch_size=100,
    )

    volume_values = []

    for code in candidates["Code"]:
        ratio = calc_volume_vs_pre5(
            history_map.get(code),
            detection_date,
        )

        volume_values.append(ratio)

    candidates[
        "DetectionVolumeVsPre5"
    ] = volume_values

    final_mask = (
        candidates[
            "DetectionVolumeVsPre5"
        ] >= 1.0
    )

    j = candidates[
        final_mask
    ].copy()

    j.insert(
        0,
        "JVersion",
        J_VERSION,
    )

    j.insert(
        1,
        "DetectionDate",
        detection_date,
    )

    print("J1 candidates     :", len(j))

    if j.empty:
        print("No J1 candidates today.")
        return

    display_cols = [
        "Code",
        "Name",
        "BasePrice",
        "Change1",
        "VolumeRatio",
        "DetectionVolumeVsPre5",
        "BreakoutSignal",
        "New30High",
    ]

    print()
    print(
        j[display_cols]
        .sort_values(
            "DetectionVolumeVsPre5",
            ascending=False,
        )
        .to_string(index=False)
    )

    TRACKING_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if TRACKING_FILE.exists():
        old = pd.read_csv(
            TRACKING_FILE,
            encoding="utf-8-sig",
            low_memory=False,
        )

        combined = pd.concat(
            [old, j],
            ignore_index=True,
        )

    else:
        combined = j.copy()

    combined = combined.drop_duplicates(
        subset=[
            "JVersion",
            "DetectionDate",
            "Code",
        ],
        keep="first",
    )

    combined.to_csv(
        TRACKING_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("Saved :", TRACKING_FILE)
    print("Total :", len(combined))


if __name__ == "__main__":
    main()
