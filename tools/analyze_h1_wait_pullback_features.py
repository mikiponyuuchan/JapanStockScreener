from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# H1 MID_CXV
# WAIT / PULLBACK FEATURE ANALYSIS
#
# 目的:
#   09:30時点で
#   「そのまま入る銘柄」
#   「押し待ちに回した方がよい銘柄」
#   を判別できる特徴を探す
#
# ここではルールを決めず、
# TAKE / STOP / CLOSE の特徴差を観察する。
# ============================================================


MORNING_DIR = Path("data/analysis/morning")
TRACKING_FILE = Path(
    "data/analysis/h1_delayed_entry_detail.csv"
)

OUTPUT_FILE = Path(
    "data/analysis/h1_wait_pullback_features.csv"
)


# ============================================================
# Utility
# ============================================================

def normalize_code(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def to_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def safe_pct_change(old, new):
    """
    old -> new の変化率
    """
    if pd.isna(old) or pd.isna(new):
        return np.nan

    if old == 0:
        return np.nan

    return (new / old - 1.0) * 100.0


# ============================================================
# Morning panel search
# ============================================================

def get_panel_files():
    files = sorted(MORNING_DIR.glob("*_morning_panel.csv"))

    rows = []

    for path in files:
        name = path.name

        try:
            date_text = name[:10]

            # YYYY-MM-DD_HHMM_morning_panel.csv
            time_text = name.split("_")[1]

            if len(time_text) != 4:
                continue

            hour = int(time_text[:2])
            minute = int(time_text[2:])

            rows.append(
                {
                    "Path": path,
                    "Date": date_text,
                    "TimeText": time_text,
                    "Minutes": hour * 60 + minute,
                }
            )

        except Exception:
            continue

    return pd.DataFrame(rows)


def choose_panel(panel_index, date_text, mode):
    """
    mode = EARLY
        09:20に最も近いファイル
        09:18～09:25を許容

    mode = H1
        09:30に最も近いファイル
        09:28～09:35を許容
    """

    day = panel_index[
        panel_index["Date"] == date_text
    ].copy()

    if day.empty:
        return None

    if mode == "EARLY":
        target = 9 * 60 + 20
        low = 9 * 60 + 18
        high = 9 * 60 + 25

    elif mode == "H1":
        target = 9 * 60 + 30
        low = 9 * 60 + 28
        high = 9 * 60 + 35

    else:
        raise ValueError(mode)

    day = day[
        (day["Minutes"] >= low)
        & (day["Minutes"] <= high)
    ].copy()

    if day.empty:
        return None

    day["Distance"] = (
        day["Minutes"] - target
    ).abs()

    day = day.sort_values(
        ["Distance", "Minutes"]
    )

    return day.iloc[0]["Path"]


# ============================================================
# Panel reader
# ============================================================

def load_panel(path):
    if path is None:
        return None

    try:
        df = pd.read_csv(
            path,
            dtype={"Code": str},
            encoding="utf-8-sig",
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            path,
            dtype={"Code": str},
        )

    if "Code" not in df.columns:
        return None

    df["Code"] = df["Code"].apply(normalize_code)

    return df


def get_stock_row(df, code):
    if df is None:
        return None

    hit = df[
        df["Code"] == normalize_code(code)
    ]

    if hit.empty:
        return None

    return hit.iloc[0]


def value_from_row(row, column):
    if row is None:
        return np.nan

    if column not in row.index:
        return np.nan

    return pd.to_numeric(
        row[column],
        errors="coerce",
    )


# ============================================================
# Tracking data
# ============================================================

def load_tracking():
    if not TRACKING_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {TRACKING_FILE}"
        )

    df = pd.read_csv(
        TRACKING_FILE,
        dtype={"Code": str},
        encoding="utf-8-sig",
    )

    df["Code"] = df["Code"].apply(
        normalize_code
    )

    if "DetectionDate" not in df.columns:
        raise RuntimeError(
            "DetectionDate column not found"
        )

    if "EntryTime" not in df.columns:
        raise RuntimeError(
            "EntryTime column not found"
        )

    df["DetectionDate"] = pd.to_datetime(
        df["DetectionDate"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    # ------------------------------------------------
    # H1 MID_CXV original strategy:
    # use only the true 09:30 entry row.
    # ------------------------------------------------

    entry_time = (
        df["EntryTime"]
        .astype(str)
        .str.strip()
        .str[:5]
    )

    df = df[
        entry_time.eq("09:30")
    ].copy()

    # Same date / same code must be one trade only.
    df = (
        df.sort_values(
            ["DetectionDate", "Code"]
        )
        .drop_duplicates(
            ["DetectionDate", "Code"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return df

# ============================================================
# Feature creation
# ============================================================

def build_feature_row(
    trade,
    early_row,
    h1_row,
    early_path,
    h1_path,
):
    date_text = trade["DetectionDate"]
    code = normalize_code(trade["Code"])

    name = trade.get("Name", "")

    exit_type = trade.get(
        "OriginalExitType",
        np.nan,
    )

    return_pct = pd.to_numeric(
        trade.get(
            "OriginalReturnPct",
            np.nan,
        ),
        errors="coerce",
    )

    # --------------------------------------------------------
    # EARLY
    # --------------------------------------------------------

    change_early = value_from_row(
        early_row,
        "MorningChangePct",
    )

    volume_early = value_from_row(
        early_row,
        "MorningVolumeVsPrev5",
    )

    cxv_early = value_from_row(
        early_row,
        "CxV",
    )

    price_early = value_from_row(
        early_row,
        "MorningPrice",
    )

    # --------------------------------------------------------
    # 09:30
    # --------------------------------------------------------

    change_0930 = value_from_row(
        h1_row,
        "MorningChangePct",
    )

    volume_0930 = value_from_row(
        h1_row,
        "MorningVolumeVsPrev5",
    )

    cxv_0930 = value_from_row(
        h1_row,
        "CxV",
    )

    price_0930 = value_from_row(
        h1_row,
        "MorningPrice",
    )

    morning_open = value_from_row(
        h1_row,
        "MorningOpen",
    )

    morning_high = value_from_row(
        h1_row,
        "MorningHigh",
    )

    morning_low = value_from_row(
        h1_row,
        "MorningLow",
    )

    open_gap = value_from_row(
        h1_row,
        "OpenGapPct",
    )

    open_to_price = value_from_row(
        h1_row,
        "OpenToPricePct",
    )

    price_vs_20 = value_from_row(
        h1_row,
        "PriceVs20HighPct",
    )

    price_vs_30 = value_from_row(
        h1_row,
        "PriceVs30HighPct",
    )

    resistance_gap = value_from_row(
        h1_row,
        "ResistanceGapPct",
    )

    room_to_30 = value_from_row(
        h1_row,
        "RoomTo30HighPct",
    )

    # --------------------------------------------------------
    # 09:30時点 高値からの押し率
    # --------------------------------------------------------

    if (
        pd.notna(morning_high)
        and morning_high != 0
        and pd.notna(price_0930)
    ):
        high_pullback = (
            price_0930 / morning_high - 1.0
        ) * 100.0
    else:
        high_pullback = np.nan

    # --------------------------------------------------------
    # 09:30時点 安値からの戻り率
    # --------------------------------------------------------

    if (
        pd.notna(morning_low)
        and morning_low != 0
        and pd.notna(price_0930)
    ):
        low_recovery = (
            price_0930 / morning_low - 1.0
        ) * 100.0
    else:
        low_recovery = np.nan

    # --------------------------------------------------------
    # 09:20 -> 09:30
    # --------------------------------------------------------

    change_delta = (
        change_0930 - change_early
        if pd.notna(change_early)
        and pd.notna(change_0930)
        else np.nan
    )

    volume_growth = safe_pct_change(
        volume_early,
        volume_0930,
    )

    cxv_growth = safe_pct_change(
        cxv_early,
        cxv_0930,
    )

    price_change = safe_pct_change(
        price_early,
        price_0930,
    )

    # --------------------------------------------------------
    # Bullish
    # --------------------------------------------------------

    bullish = np.nan

    if (
        h1_row is not None
        and "MorningBullish" in h1_row.index
    ):
        bullish = h1_row["MorningBullish"]

    return {
        "DetectionDate": date_text,
        "Code": code,
        "Name": name,
        "OriginalExitType": exit_type,
        "OriginalReturnPct": return_pct,

        "EarlyPanel":
            early_path.name
            if early_path is not None
            else "",

        "H1Panel":
            h1_path.name
            if h1_path is not None
            else "",

        "ChangeEarly": change_early,
        "Change0930": change_0930,
        "ChangeDelta": change_delta,

        "VolumeRatioEarly": volume_early,
        "VolumeRatio0930": volume_0930,
        "VolumeRatioGrowthPct": volume_growth,

        "CxVEarly": cxv_early,
        "CxV0930": cxv_0930,
        "CxVGrowthPct": cxv_growth,

        "PriceEarly": price_early,
        "Price0930": price_0930,
        "PriceEarlyTo0930Pct": price_change,

        "MorningOpen0930": morning_open,
        "MorningHigh0930": morning_high,
        "MorningLow0930": morning_low,

        "OpenGapPct0930": open_gap,
        "OpenToPricePct0930": open_to_price,

        "HighPullbackPct0930": high_pullback,
        "LowRecoveryPct0930": low_recovery,

        "PriceVs20HighPct0930": price_vs_20,
        "PriceVs30HighPct0930": price_vs_30,
        "ResistanceGapPct0930": resistance_gap,
        "RoomTo30HighPct0930": room_to_30,

        "MorningBullish0930": bullish,
    }


# ============================================================
# Summary
# ============================================================

FEATURE_COLUMNS = [
    "ChangeEarly",
    "Change0930",
    "ChangeDelta",
    "VolumeRatioEarly",
    "VolumeRatio0930",
    "VolumeRatioGrowthPct",
    "CxVEarly",
    "CxV0930",
    "CxVGrowthPct",
    "PriceEarlyTo0930Pct",
    "OpenGapPct0930",
    "OpenToPricePct0930",
    "HighPullbackPct0930",
    "LowRecoveryPct0930",
    "PriceVs20HighPct0930",
    "PriceVs30HighPct0930",
    "ResistanceGapPct0930",
    "RoomTo30HighPct0930",
]


def print_group_summary(result):
    print()
    print("=" * 80)
    print("TAKE / STOP / CLOSE FEATURE MEDIAN")
    print("=" * 80)
    print()

    available = [
        c
        for c in FEATURE_COLUMNS
        if c in result.columns
    ]

    summary = (
        result.groupby(
            "OriginalExitType"
        )[available]
        .median(numeric_only=True)
        .T
    )

    preferred_order = [
        c
        for c in [
            "TAKE",
            "STOP",
            "CLOSE",
        ]
        if c in summary.columns
    ]

    other_columns = [
        c
        for c in summary.columns
        if c not in preferred_order
    ]

    summary = summary[
        preferred_order
        + other_columns
    ]

    print(
        summary.round(2).to_string()
    )


def print_stop_take_difference(result):
    print()
    print("=" * 80)
    print("STOP - TAKE MEDIAN DIFFERENCE")
    print("=" * 80)
    print()

    available = [
        c
        for c in FEATURE_COLUMNS
        if c in result.columns
    ]

    med = (
        result.groupby(
            "OriginalExitType"
        )[available]
        .median(numeric_only=True)
    )

    if (
        "STOP" not in med.index
        or "TAKE" not in med.index
    ):
        print(
            "TAKE / STOP comparison unavailable"
        )
        return

    diff = (
        med.loc["STOP"]
        - med.loc["TAKE"]
    )

    out = pd.DataFrame(
        {
            "TAKE_Median":
                med.loc["TAKE"],

            "STOP_Median":
                med.loc["STOP"],

            "STOP_minus_TAKE":
                diff,
        }
    )

    print(
        out.round(2).to_string()
    )


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 80)
    print(
        "H1 MID_CXV WAIT / PULLBACK FEATURE ANALYSIS"
    )
    print("=" * 80)
    print()

    panel_index = get_panel_files()

    print(
        f"Morning panel files : {len(panel_index)}"
    )

    tracking = load_tracking()

    print(
        f"Target trades       : {len(tracking)}"
    )

    print()

    rows = []

    panel_cache = {}

    for i, trade in tracking.iterrows():

        date_text = trade["DetectionDate"]
        code = normalize_code(
            trade["Code"]
        )

        name = trade.get(
            "Name",
            "",
        )

        print(
            f"[{i + 1}/{len(tracking)}] "
            f"{date_text} "
            f"{code} "
            f"{name}"
        )

        early_path = choose_panel(
            panel_index,
            date_text,
            "EARLY",
        )

        h1_path = choose_panel(
            panel_index,
            date_text,
            "H1",
        )

        # cache
        if early_path is not None:
            key = str(early_path)

            if key not in panel_cache:
                panel_cache[key] = load_panel(
                    early_path
                )

            early_df = panel_cache[key]

        else:
            early_df = None

        if h1_path is not None:
            key = str(h1_path)

            if key not in panel_cache:
                panel_cache[key] = load_panel(
                    h1_path
                )

            h1_df = panel_cache[key]

        else:
            h1_df = None

        early_row = get_stock_row(
            early_df,
            code,
        )

        h1_row = get_stock_row(
            h1_df,
            code,
        )

        rows.append(
            build_feature_row(
                trade,
                early_row,
                h1_row,
                early_path,
                h1_path,
            )
        )

    result = pd.DataFrame(rows)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 80)
    print("EXIT TYPE COUNTS")
    print("=" * 80)
    print()

    print(
        result[
            "OriginalExitType"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print_group_summary(result)

    print_stop_take_difference(result)

    print()
    print("=" * 80)
    print("INDIVIDUAL TRADES")
    print("=" * 80)
    print()

    display_columns = [
        "DetectionDate",
        "Code",
        "Name",
        "OriginalExitType",
        "OriginalReturnPct",
        "ChangeEarly",
        "Change0930",
        "ChangeDelta",
        "VolumeRatioEarly",
        "VolumeRatio0930",
        "CxVEarly",
        "CxV0930",
        "CxVGrowthPct",
        "OpenGapPct0930",
        "OpenToPricePct0930",
        "HighPullbackPct0930",
        "LowRecoveryPct0930",
    ]

    print(
        result[
            display_columns
        ]
        .round(2)
        .to_string(index=False)
    )

    print()
    print("=" * 80)
    print("SAVED")
    print("=" * 80)
    print()
    print(
        f"Feature file : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()