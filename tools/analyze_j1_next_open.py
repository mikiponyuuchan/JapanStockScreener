import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "src")

from services.yahoo_service import _download_history_batch


TRACKING_PATH = Path(
    "data/tracking/j_type_tracking.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/j1_next_open_panel.csv"
)


def to_num(series):
    return pd.to_numeric(
        series,
        errors="coerce"
    )


def normalize_history(df):
    if df is None or df.empty:
        return None

    x = df.copy()

    if "Date" in x.columns:
        x["Date"] = pd.to_datetime(
            x["Date"],
            errors="coerce"
        ).dt.normalize()
    else:
        x = x.reset_index()

        date_col = x.columns[0]

        x = x.rename(
            columns={
                date_col: "Date"
            }
        )

        x["Date"] = pd.to_datetime(
            x["Date"],
            errors="coerce"
        ).dt.normalize()

    return x


def get_detection_ohlc(
    history,
    detection_date
):
    x = normalize_history(history)

    if x is None:
        return None

    target = pd.Timestamp(
        detection_date
    ).normalize()

    row = x[
        x["Date"] == target
    ]

    if row.empty:
        return None

    return row.iloc[-1]


def safe_pct(a, b):
    if pd.isna(a) or pd.isna(b):
        return np.nan

    if b == 0:
        return np.nan

    return (
        a / b - 1
    ) * 100


def build_candle_features(row):
    o = pd.to_numeric(
        row.get("Open"),
        errors="coerce"
    )
    h = pd.to_numeric(
        row.get("High"),
        errors="coerce"
    )
    l = pd.to_numeric(
        row.get("Low"),
        errors="coerce"
    )
    c = pd.to_numeric(
        row.get("Close"),
        errors="coerce"
    )

    result = {
        "DetectionOpen": o,
        "DetectionHigh": h,
        "DetectionLow": l,
        "DetectionClose": c,
        "DetectionBodyPct": np.nan,
        "DetectionRangePct": np.nan,
        "UpperWickRatio": np.nan,
        "LowerWickRatio": np.nan,
        "CloseLocation": np.nan,
    }

    if pd.notna(o) and o != 0:
        result["DetectionBodyPct"] = (
            c / o - 1
        ) * 100

        result["DetectionRangePct"] = (
            h / o - l / o
        ) * 100

    if (
        pd.notna(h)
        and pd.notna(l)
        and h > l
    ):
        price_range = h - l

        result["UpperWickRatio"] = (
            h - max(o, c)
        ) / price_range

        result["LowerWickRatio"] = (
            min(o, c) - l
        ) / price_range

        result["CloseLocation"] = (
            c - l
        ) / price_range

    return result


def main():
    if not TRACKING_PATH.exists():
        print(
            "Tracking file not found:"
        )
        print(TRACKING_PATH)
        return

    df = pd.read_csv(
        TRACKING_PATH,
        dtype={
            "Code": str
        }
    )

    if df.empty:
        print("No J1 rows.")
        return

    df = df[
        df["JVersion"].astype(str)
        == "J1"
    ].copy()

    if df.empty:
        print("No J1 rows.")
        return

    df["DetectionDate"] = (
        pd.to_datetime(
            df["DetectionDate"],
            errors="coerce"
        )
        .dt.strftime("%Y-%m-%d")
    )

    numeric_cols = [
        "BasePrice",
        "Change1",
        "VolumeRatio",
        "DetectionVolumeVsPre5",
        "Day1Open",
        "Day1High",
        "Day1Low",
        "Day1Close",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = to_num(df[col])

    codes = sorted(
        df["Code"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    print("=" * 72)
    print("J1 NEXT-OPEN PANEL")
    print("=" * 72)
    print(
        f"J1 rows       : {len(df)}"
    )
    print(
        f"Yahoo codes   : {len(codes)}"
    )
    print()

    history_map = (
        _download_history_batch(
            codes,
            period="3mo",
            batch_size=100
        )
    )

    print()
    print(
        f"Yahoo success : "
        f"{len(history_map)}"
    )

    rows = []

    missing_detection = 0

    for _, src in df.iterrows():
        code = str(src["Code"])
        detection_date = (
            src["DetectionDate"]
        )

        out = src.to_dict()

        hist = history_map.get(code)

        candle_row = (
            get_detection_ohlc(
                hist,
                detection_date
            )
        )

        if candle_row is None:
            missing_detection += 1

            candle = {
                "DetectionOpen": np.nan,
                "DetectionHigh": np.nan,
                "DetectionLow": np.nan,
                "DetectionClose": np.nan,
                "DetectionBodyPct": np.nan,
                "DetectionRangePct": np.nan,
                "UpperWickRatio": np.nan,
                "LowerWickRatio": np.nan,
                "CloseLocation": np.nan,
            }
        else:
            candle = (
                build_candle_features(
                    candle_row
                )
            )

        out.update(candle)

        base = out.get(
            "BasePrice",
            np.nan
        )

        entry = out.get(
            "Day1Open",
            np.nan
        )

        d1_high = out.get(
            "Day1High",
            np.nan
        )

        d1_low = out.get(
            "Day1Low",
            np.nan
        )

        d1_close = out.get(
            "Day1Close",
            np.nan
        )

        out["NextOpenGapPct"] = (
            safe_pct(
                entry,
                base
            )
        )

        out["EntryDayHighPct"] = (
            safe_pct(
                d1_high,
                entry
            )
        )

        out["EntryDayLowPct"] = (
            safe_pct(
                d1_low,
                entry
            )
        )

        out["EntryDayClosePct"] = (
            safe_pct(
                d1_close,
                entry
            )
        )

        high_pct = out[
            "EntryDayHighPct"
        ]

        if pd.isna(high_pct):
            out["EntryDayGroup"] = ""
        elif high_pct >= 10:
            out["EntryDayGroup"] = "BIG"
        elif high_pct >= 5:
            out["EntryDayGroup"] = "WIN"
        elif high_pct > 0:
            out["EntryDayGroup"] = "SMALL"
        else:
            out["EntryDayGroup"] = "FAIL"

        rows.append(out)

    panel = pd.DataFrame(rows)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    panel.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 72)
    print("RESULT")
    print("=" * 72)
    print(
        f"Panel rows     : "
        f"{len(panel)}"
    )
    print(
        f"Missing candle : "
        f"{missing_detection}"
    )
    print(
        f"Saved          : "
        f"{OUTPUT_PATH}"
    )

    confirmed = panel[
        pd.to_numeric(
            panel["Day1Open"],
            errors="coerce"
        ).notna()
    ].copy()

    print(
        f"Day1 confirmed : "
        f"{len(confirmed)}"
    )

    if confirmed.empty:
        return

    print()
    print("=" * 72)
    print("ENTRY-DAY GROUPS")
    print("=" * 72)

    print(
        confirmed[
            "EntryDayGroup"
        ]
        .value_counts()
        .reindex(
            [
                "BIG",
                "WIN",
                "SMALL",
                "FAIL",
            ],
            fill_value=0
        )
    )

    gu = confirmed[
        confirmed[
            "NextOpenGapPct"
        ] >= 0
    ].copy()

    print()
    print("=" * 72)
    print("NON-NEGATIVE GAP")
    print("=" * 72)
    print(
        f"N             : "
        f"{len(gu)}"
    )

    if len(gu) > 0:
        print(
            f"BIG           : "
            f"{int((gu['EntryDayGroup'] == 'BIG').sum())}"
        )

        print(
            f"BIG rate      : "
            f"{(gu['EntryDayGroup'] == 'BIG').mean() * 100:.1f}%"
        )

    show_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Change1",
        "VolumeRatio",
        "DetectionVolumeVsPre5",
        "DetectionBodyPct",
        "DetectionRangePct",
        "UpperWickRatio",
        "LowerWickRatio",
        "CloseLocation",
        "NextOpenGapPct",
        "EntryDayHighPct",
        "EntryDayLowPct",
        "EntryDayClosePct",
        "EntryDayGroup",
    ]

    show_cols = [
        col
        for col in show_cols
        if col in panel.columns
    ]

    print()
    print("=" * 72)
    print("GU DETAIL")
    print("=" * 72)

    if len(gu) > 0:
        print(
            gu[show_cols]
            .sort_values(
                "EntryDayHighPct",
                ascending=False
            )
            .to_string(
                index=False,
                float_format=(
                    lambda v: f"{v:.2f}"
                )
            )
        )


if __name__ == "__main__":
    main()
