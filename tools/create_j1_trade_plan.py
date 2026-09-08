
from pathlib import Path
from datetime import date

import pandas as pd


TRACKING_FILE = Path(
    "data/tracking/j_type_tracking.csv"
)

OUTPUT_DIR = Path(
    "data/trading"
)

CHANGE_MIN = 5.20
CHANGE_MAX = 5.50

TAKE_PROFIT_PCT = 3.0
STOP_LOSS_PCT = -5.0


def normalize_code(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def main():

    if not TRACKING_FILE.exists():
        print(
            "Tracking file not found:",
            TRACKING_FILE,
        )
        return

    df = pd.read_csv(
        TRACKING_FILE,
        dtype={"Code": str},
        encoding="utf-8-sig",
        low_memory=False,
    )

    required = [
        "JVersion",
        "DetectionDate",
        "Code",
        "Name",
        "BasePrice",
        "Change1",
        "VolumeRatio",
        "DetectionVolumeVsPre5",
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

    df["Change1"] = pd.to_numeric(
        df["Change1"],
        errors="coerce",
    )

    df["Code"] = (
        df["Code"]
        .map(normalize_code)
    )

    # Use the latest J1 detection date.
    j1 = df[
        df["JVersion"]
        .astype(str)
        .eq("J1")
    ].copy()

    if j1.empty:
        print("No J1 rows.")
        return

    detection_date = (
        j1["DetectionDate"]
        .astype(str)
        .max()
    )

    today_j1 = j1[
        j1["DetectionDate"]
        .astype(str)
        .eq(detection_date)
    ].copy()

    trade = today_j1[
        (today_j1["Change1"] >= CHANGE_MIN)
        & (today_j1["Change1"] < CHANGE_MAX)
    ].copy()

    trade = trade.sort_values(
        [
            "Change1",
            "DetectionVolumeVsPre5",
        ],
        ascending=[
            False,
            False,
        ],
    ).reset_index(drop=True)

    print("=" * 72)
    print("J1 TRADE PLAN Ver1")
    print("=" * 72)
    print(
        "Detection date :",
        detection_date,
    )
    print(
        "Candidates     :",
        len(trade),
    )
    print(
        "Rule           :",
        "Change1 5.20-5.49",
    )
    print(
        "Entry          :",
        "NEXT OPEN",
    )
    print(
        "Take profit    :",
        f"+{TAKE_PROFIT_PCT:.1f}%",
    )
    print(
        "Stop loss      :",
        f"{STOP_LOSS_PCT:.1f}%",
    )
    print(
        "Fallback exit  :",
        "CLOSE",
    )
    print()

    if trade.empty:
        print(
            "No J1 Trade Ver1 candidates."
        )
        return

    display_cols = [
        "Code",
        "Name",
        "BasePrice",
        "Change1",
        "DetectionVolumeVsPre5",
    ]

    print(
        trade[display_cols]
        .to_string(
            index=False,
            float_format=lambda v: f"{v:.2f}",
        )
    )

    out = trade[
        [
            "DetectionDate",
            "Code",
            "Name",
            "BasePrice",
            "Change1",
            "VolumeRatio",
            "DetectionVolumeVsPre5",
        ]
    ].copy()

    out.insert(
        0,
        "StrategyVersion",
        "J1-Trade-Ver1",
    )

    out["EntryRule"] = (
        "NEXT_OPEN"
    )

    out["TakeProfitPct"] = (
        TAKE_PROFIT_PCT
    )

    out["StopLossPct"] = (
        STOP_LOSS_PCT
    )

    out["FallbackExit"] = (
        "CLOSE"
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        OUTPUT_DIR
        / (
            f"{detection_date}"
            "_j1_trade_plan.csv"
        )
    )

    out.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "Saved          :",
        output_path,
    )


if __name__ == "__main__":
    main()
