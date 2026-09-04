from pathlib import Path
from datetime import datetime, time as dt_time
import sys

import pandas as pd

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from services.yahoo_service import _download_history_batch
from indicators.technical import add_indicators


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

    # ======================================================
    # Confirmed-close J1 calculation
    #
    # stock_result.csv is used only for Code / Name.
    # All J1 condition values are rebuilt from Yahoo
    # confirmed daily history after the market close.
    # ======================================================

    universe = pd.DataFrame()

    universe["Code"] = (
        df[COL_CODE]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\\.0$",
            "",
            regex=True,
        )
    )

    universe["Name"] = df[COL_NAME]

    universe = (
        universe
        .dropna(subset=["Code"])
        .drop_duplicates(
            subset=["Code"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    codes = sorted(
        universe["Code"]
        .dropna()
        .unique()
        .tolist()
    )

    print("=" * 72)
    print("J1 PROSPECTIVE VALIDATION")
    print("=" * 72)
    print("Date              :", detection_date)
    print("Confirmed input   :", len(codes))
    print("Yahoo history     : downloading")

    history_map = _download_history_batch(
        codes,
        period="3mo",
        batch_size=100,
    )

    name_map = dict(
        zip(
            universe["Code"],
            universe["Name"],
        )
    )

    confirmed_rows = []

    target_date = pd.Timestamp(
        detection_date
    ).normalize()

    for code in codes:

        history = history_map.get(
            code
        )

        x = normalize_history(
            history
        )

        if x is None or x.empty:
            continue

        # Detection-date confirmed daily row must exist.
        today_mask = (
            x.index.normalize()
            == target_date
        )

        if not today_mask.any():
            continue

        # add_indicators() expects ordinary OHLCV columns.
        indicator_df = (
            x
            .reset_index()
            .rename(
                columns={
                    "index": "Date",
                }
            )
        )

        try:
            indicator_df = add_indicators(
                indicator_df
            )
        except Exception:
            continue

        if (
            indicator_df is None
            or indicator_df.empty
        ):
            continue

        indicator_df["Date"] = pd.to_datetime(
            indicator_df["Date"],
            errors="coerce",
        )

        confirmed_today = indicator_df[
            indicator_df["Date"].dt.normalize()
            == target_date
        ]

        if confirmed_today.empty:
            continue

        latest = confirmed_today.iloc[-1]

        base_price = pd.to_numeric(
            latest.get(
                "Close",
                pd.NA,
            ),
            errors="coerce",
        )

        change1 = pd.to_numeric(
            latest.get(
                "ChangePercent",
                pd.NA,
            ),
            errors="coerce",
        )

        volume_ratio = pd.to_numeric(
            latest.get(
                "VolumeRatio",
                pd.NA,
            ),
            errors="coerce",
        )

        breakout_signal = to_bool(
            latest.get(
                "BreakoutSignal",
                False,
            )
        )

        new30_high = to_bool(
            latest.get(
                "New30High",
                False,
            )
        )

        detection_volume_vs_pre5 = (
            calc_volume_vs_pre5(
                history,
                detection_date,
            )
        )

        if (
            pd.isna(base_price)
            or pd.isna(change1)
            or pd.isna(volume_ratio)
            or detection_volume_vs_pre5 is None
        ):
            continue

        confirmed_rows.append(
            {
                "Code": code,
                "Name": name_map.get(
                    code,
                    "",
                ),
                "BasePrice": float(
                    base_price
                ),
                "Change1": float(
                    change1
                ),
                "VolumeRatio": float(
                    volume_ratio
                ),
                "BreakoutSignal":
                    bool(breakout_signal),
                "New30High":
                    bool(new30_high),
                "DetectionVolumeVsPre5":
                    float(
                        detection_volume_vs_pre5
                    ),
            }
        )

    work = pd.DataFrame(
        confirmed_rows
    )

    if work.empty:
        print("J1 candidates     : 0")
        print("No confirmed Yahoo rows.")
        return

    final_mask = (
        (work["Change1"] >= 5.0)
        & (work["VolumeRatio"] < 3.0)
        & (~work["BreakoutSignal"])
        & (~work["New30High"])
        & (
            work["DetectionVolumeVsPre5"]
            >= 1.0
        )
    )

    j = work[
        final_mask
    ].copy()

    print(
        "Confirmed rows    :",
        len(work),
    )

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

        # Re-running today's confirmed-close validation must
        # replace today's J1 rows, not preserve stale intraday rows.
        if (
            "JVersion" in old.columns
            and "DetectionDate" in old.columns
        ):
            old = old[
                ~(
                    (
                        old["JVersion"]
                        .astype(str)
                        == J_VERSION
                    )
                    &
                    (
                        old["DetectionDate"]
                        .astype(str)
                        == detection_date
                    )
                )
            ].copy()

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
        keep="last",
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
