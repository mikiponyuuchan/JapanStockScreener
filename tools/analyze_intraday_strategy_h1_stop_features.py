from pathlib import Path

import pandas as pd


# ============================================================
# H1 STOP FEATURE ANALYSIS
# ============================================================

SOURCE_H1 = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

SOURCE_TAKE = Path(
    "data/analysis/intraday_strategy_h1_takeprofit.csv"
)

OUTPUT_DETAIL = Path(
    "data/analysis/intraday_strategy_h1_stop_features.csv"
)

OUTPUT_SUMMARY = Path(
    "data/analysis/intraday_strategy_h1_stop_features_summary.csv"
)

LOWER_LIMIT = -3.0
UPPER_LIMIT = 1.0
TAKE_PCT = 10.0


# ============================================================
# Utility
# ============================================================

def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def format_value(value, digits=2):
    if pd.isna(value):
        return ""

    return f"{value:.{digits}f}"


# ============================================================
# Summary
# ============================================================

def summarize_group(df, group_name):
    rows = []

    features = [
        "Change",
        "VolumeRatio",
        "CxV",
        "Rank",
        "Close0931Pct",
    ]

    for feature in features:
        x = pd.to_numeric(
            df[feature],
            errors="coerce",
        ).dropna()

        if x.empty:
            continue

        rows.append(
            {
                "Group": group_name,
                "Feature": feature,
                "Count": len(x),
                "Mean": x.mean(),
                "Median": x.median(),
                "Min": x.min(),
                "Max": x.max(),
            }
        )

    return rows


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 80)
    print("H1 STOP FEATURE ANALYSIS")
    print("=" * 80)

    if not SOURCE_H1.exists():
        print(
            f"NOT FOUND : {SOURCE_H1}"
        )
        return

    if not SOURCE_TAKE.exists():
        print(
            f"NOT FOUND : {SOURCE_TAKE}"
        )
        return

    # --------------------------------------------------------
    # Original H1 data
    # --------------------------------------------------------

    h1 = pd.read_csv(
        SOURCE_H1,
        low_memory=False,
    )

    if "DataType" in h1.columns:
        h1 = h1[
            h1["DataType"]
            .astype(str)
            .str.upper()
            .eq("FORWARD")
        ].copy()

    h1["Code"] = h1["Code"].map(
        normalize_code
    )

    # --------------------------------------------------------
    # +10% take-profit analysis
    # --------------------------------------------------------

    take = pd.read_csv(
        SOURCE_TAKE,
        low_memory=False,
    )

    take["Code"] = take["Code"].map(
        normalize_code
    )

    take["TakePct"] = pd.to_numeric(
        take["TakePct"],
        errors="coerce",
    )

    take["Close0931Pct"] = pd.to_numeric(
        take["Close0931Pct"],
        errors="coerce",
    )

    target = take[
        (
            take["TakePct"]
            == TAKE_PCT
        )
        & (
            take["Close0931Pct"]
            >= LOWER_LIMIT
        )
        & (
            take["Close0931Pct"]
            < UPPER_LIMIT
        )
    ].copy()

    # --------------------------------------------------------
    # Merge original 09:30 features
    # --------------------------------------------------------

    original_cols = [
        "DetectionDate",
        "Code",
        "Change",
        "VolumeRatio",
        "CxV",
    ]

    original = h1[
        original_cols
    ].copy()

    original = original.drop_duplicates(
        subset=[
            "DetectionDate",
            "Code",
        ],
        keep="last",
    )

    # CxV already exists in take CSV.
    # Keep the original value separately for checking.
    original = original.rename(
        columns={
            "CxV": "OriginalCxV",
        }
    )

    detail = target.merge(
        original,
        on=[
            "DetectionDate",
            "Code",
        ],
        how="left",
    )

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    numeric_cols = [
        "Rank",
        "Change",
        "VolumeRatio",
        "CxV",
        "OriginalCxV",
        "Close0931Pct",
        "ReturnPct",
    ]

    for col in numeric_cols:
        if col in detail.columns:
            detail[col] = pd.to_numeric(
                detail[col],
                errors="coerce",
            )

    # --------------------------------------------------------
    # STOP / NON-STOP label
    # --------------------------------------------------------

    detail["StopGroup"] = detail[
        "ExitType"
    ].map(
        lambda x:
            "STOP"
            if str(x).upper() == "STOP"
            else "NON_STOP"
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    detail = detail.sort_values(
        [
            "StopGroup",
            "DetectionDate",
            "Rank",
        ],
        ascending=[
            False,
            True,
            True,
        ],
    ).reset_index(
        drop=True
    )

    print()
    print(f"Target rows : {len(detail)}")

    stop_count = (
        detail["StopGroup"]
        .eq("STOP")
        .sum()
    )

    non_stop_count = (
        detail["StopGroup"]
        .eq("NON_STOP")
        .sum()
    )

    print(
        f"STOP        : {stop_count}"
    )
    print(
        f"NON_STOP    : {non_stop_count}"
    )

    # --------------------------------------------------------
    # STOP vs NON_STOP
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("STOP vs NON_STOP")
    print("=" * 80)

    compare_rows = []

    for group_name in [
        "STOP",
        "NON_STOP",
    ]:
        x = detail[
            detail["StopGroup"]
            == group_name
        ]

        compare_rows.extend(
            summarize_group(
                x,
                group_name,
            )
        )

    compare = pd.DataFrame(
        compare_rows
    )

    pivot_mean = compare.pivot(
        index="Feature",
        columns="Group",
        values="Mean",
    )

    pivot_median = compare.pivot(
        index="Feature",
        columns="Group",
        values="Median",
    )

    print()
    print("MEAN")
    print(
        pivot_mean.to_string(
            float_format=lambda x:
                f"{x:.2f}"
        )
    )

    print()
    print("MEDIAN")
    print(
        pivot_median.to_string(
            float_format=lambda x:
                f"{x:.2f}"
        )
    )

    # --------------------------------------------------------
    # TAKE / CLOSE / STOP
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("TAKE / CLOSE / STOP")
    print("=" * 80)

    exit_rows = []

    for exit_type in [
        "TAKE",
        "CLOSE",
        "STOP",
    ]:
        x = detail[
            detail["ExitType"]
            .astype(str)
            .str.upper()
            .eq(exit_type)
        ]

        if x.empty:
            continue

        exit_rows.extend(
            summarize_group(
                x,
                exit_type,
            )
        )

    exit_summary = pd.DataFrame(
        exit_rows
    )

    exit_mean = exit_summary.pivot(
        index="Feature",
        columns="Group",
        values="Mean",
    )

    exit_median = exit_summary.pivot(
        index="Feature",
        columns="Group",
        values="Median",
    )

    print()
    print("MEAN")
    print(
        exit_mean.to_string(
            float_format=lambda x:
                f"{x:.2f}"
        )
    )

    print()
    print("MEDIAN")
    print(
        exit_median.to_string(
            float_format=lambda x:
                f"{x:.2f}"
        )
    )

    # --------------------------------------------------------
    # Rank comparison
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("RANK x RESULT")
    print("=" * 80)

    rank_table = pd.crosstab(
        detail["Rank"],
        detail["ExitType"],
        margins=True,
    )

    print(
        rank_table.to_string()
    )

    # --------------------------------------------------------
    # STOP detail
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("STOP DETAIL")
    print("=" * 80)

    stop_detail = detail[
        detail["StopGroup"]
        == "STOP"
    ].copy()

    show_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Change",
        "VolumeRatio",
        "CxV",
        "Close0931Pct",
        "EntryPrice",
        "ReturnPct",
    ]

    print(
        stop_detail[
            show_cols
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # NON-STOP detail
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("NON-STOP DETAIL")
    print("=" * 80)

    non_stop_detail = detail[
        detail["StopGroup"]
        == "NON_STOP"
    ].copy()

    show_cols_non = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Change",
        "VolumeRatio",
        "CxV",
        "Close0931Pct",
        "ExitType",
        "ReturnPct",
    ]

    print(
        non_stop_detail[
            show_cols_non
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUTPUT_DETAIL.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    detail.to_csv(
        OUTPUT_DETAIL,
        index=False,
        encoding="utf-8-sig",
    )

    all_summary = pd.concat(
        [
            compare.assign(
                Analysis="STOP_vs_NON_STOP"
            ),
            exit_summary.assign(
                Analysis="EXIT_TYPE"
            ),
        ],
        ignore_index=True,
    )

    all_summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"Saved : {OUTPUT_DETAIL}"
    )
    print(
        f"Saved : {OUTPUT_SUMMARY}"
    )


if __name__ == "__main__":
    main()