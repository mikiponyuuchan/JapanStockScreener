from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# H1 MID_CXV
# WAIT Threshold Boundary Analysis
#
# Purpose:
#   Investigate why WAIT threshold = 100% performed well.
#
# Focus:
#   Pullback = -0.50%
#
# Growth bands:
#   <75%
#   75-100%
#   100-125%
#   125-150%
#   150%+
# ============================================================


BASE_DIR = Path(__file__).resolve().parents[1]


FEATURE_FILE = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_wait_pullback_features.csv"
)

SENSITIVITY_DETAIL_FILE = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_hybrid_wait_sensitivity_detail.csv"
)

OUTPUT_DETAIL = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_wait_threshold_boundary_detail.csv"
)

OUTPUT_SUMMARY = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_wait_threshold_boundary_summary.csv"
)


TARGET_PULLBACK = -0.50


# ============================================================
# Utility
# ============================================================

def normalize_code(value):
    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    return code


def growth_band(value):

    if pd.isna(value):
        return "MISSING"

    value = float(value)

    if value < 75:
        return "<75%"

    if value < 100:
        return "75-100%"

    if value < 125:
        return "100-125%"

    if value < 150:
        return "125-150%"

    return "150%+"


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print("H1 MID_CXV WAIT THRESHOLD BOUNDARY ANALYSIS")
    print("=" * 80)
    print()

    # --------------------------------------------------------
    # Load feature data
    # --------------------------------------------------------

    if not FEATURE_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {FEATURE_FILE}"
        )

    features = pd.read_csv(
        FEATURE_FILE,
        dtype={"Code": str},
        encoding="utf-8-sig",
    )

    features["Code"] = features["Code"].apply(
        normalize_code
    )

    features["DetectionDate"] = pd.to_datetime(
        features["DetectionDate"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    features["VolumeRatioGrowthPct"] = pd.to_numeric(
        features["VolumeRatioGrowthPct"],
        errors="coerce",
    )

    features["OriginalReturnPct"] = pd.to_numeric(
        features["OriginalReturnPct"],
        errors="coerce",
    )

    features["GrowthBand"] = (
        features["VolumeRatioGrowthPct"]
        .apply(growth_band)
    )

    # --------------------------------------------------------
    # Load sensitivity detail
    # --------------------------------------------------------

    if not SENSITIVITY_DETAIL_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {SENSITIVITY_DETAIL_FILE}"
        )

    detail = pd.read_csv(
        SENSITIVITY_DETAIL_FILE,
        dtype={"Code": str},
        encoding="utf-8-sig",
    )

    detail["Code"] = detail["Code"].apply(
        normalize_code
    )

    detail["DetectionDate"] = pd.to_datetime(
        detail["DetectionDate"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    detail["PullbackLevel"] = pd.to_numeric(
        detail["PullbackLevel"],
        errors="coerce",
    )

    detail["WaitThreshold"] = pd.to_numeric(
        detail["WaitThreshold"],
        errors="coerce",
    )

    detail["HybridReturnPct"] = pd.to_numeric(
        detail["HybridReturnPct"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Use threshold = 100%, pullback = -0.50%
    #
    # This gives the actual strategy outcome at the current
    # best threshold.
    # --------------------------------------------------------

    target = detail[
        np.isclose(
            detail["WaitThreshold"],
            100.0,
        )
        &
        np.isclose(
            detail["PullbackLevel"],
            TARGET_PULLBACK,
        )
    ].copy()

    print(
        f"Target pullback : "
        f"{TARGET_PULLBACK:+.2f}%"
    )

    print(
        "Target WAIT threshold : 100%"
    )

    print(
        f"Rows matched : {len(target)}"
    )

    print()

    # --------------------------------------------------------
    # Keep only outcome columns from sensitivity result
    # --------------------------------------------------------

    outcome = target[
        [
            "DetectionDate",
            "Code",
            "Decision",
            "Status",
            "EntryTime",
            "EntryPrice",
            "ExitType",
            "HybridReturnPct",
        ]
    ].copy()

    outcome = outcome.rename(
        columns={
            "Decision":
                "DecisionAt100",
            "Status":
                "WaitStatus",
            "EntryTime":
                "WaitEntryTime",
            "EntryPrice":
                "WaitEntryPrice",
            "ExitType":
                "WaitExitType",
            "HybridReturnPct":
                "WaitReturnPct",
        }
    )

    # --------------------------------------------------------
    # Merge
    # --------------------------------------------------------

    result = features.merge(
        outcome,
        on=[
            "DetectionDate",
            "Code",
        ],
        how="left",
        validate="one_to_one",
    )

    # Difference between strategy result and original 09:30
    result["DifferencePct"] = (
        result["WaitReturnPct"]
        - result["OriginalReturnPct"]
    )

    # --------------------------------------------------------
    # Select useful columns
    # --------------------------------------------------------

    output_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "VolumeRatioGrowthPct",
        "GrowthBand",
        "DecisionAt100",
        "OriginalExitType",
        "OriginalReturnPct",
        "WaitStatus",
        "WaitEntryTime",
        "WaitEntryPrice",
        "WaitExitType",
        "WaitReturnPct",
        "DifferencePct",
    ]

    result = result[
        output_cols
    ].copy()

    result = result.sort_values(
        [
            "VolumeRatioGrowthPct",
            "DetectionDate",
            "Code",
        ],
        ascending=[
            True,
            True,
            True,
        ],
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # Band summary
    # --------------------------------------------------------

    band_order = [
        "<75%",
        "75-100%",
        "100-125%",
        "125-150%",
        "150%+",
        "MISSING",
    ]

    summary_rows = []

    for band in band_order:

        g = result[
            result["GrowthBand"] == band
        ].copy()

        if g.empty:
            continue

        original_total = (
            g["OriginalReturnPct"]
            .fillna(0.0)
            .sum()
        )

        strategy_total = (
            g["WaitReturnPct"]
            .fillna(0.0)
            .sum()
        )

        difference_total = (
            strategy_total
            - original_total
        )

        wait_count = int(
            (
                g["DecisionAt100"]
                == "WAIT"
            ).sum()
        )

        buy_count = int(
            (
                g["DecisionAt100"]
                == "BUY_0930"
            ).sum()
        )

        no_fill = int(
            (
                g["WaitStatus"]
                == "NO_FILL"
            ).sum()
        )

        executed = int(
            (
                g["WaitStatus"]
                == "EXECUTED"
            ).sum()
        )

        summary_rows.append(
            {
                "GrowthBand":
                    band,
                "Count":
                    len(g),
                "Buy0930":
                    buy_count,
                "Wait":
                    wait_count,
                "WaitExecuted":
                    executed,
                "WaitNoFill":
                    no_fill,
                "OriginalTotalReturnPct":
                    original_total,
                "StrategyTotalReturnPct":
                    strategy_total,
                "DifferencePct":
                    difference_total,
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUTPUT_DETAIL.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_DETAIL,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Display all 21 stocks
    # --------------------------------------------------------

    print("=" * 80)
    print("ALL STOCKS")
    print("=" * 80)
    print()

    display_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "VolumeRatioGrowthPct",
        "GrowthBand",
        "DecisionAt100",
        "OriginalExitType",
        "OriginalReturnPct",
        "WaitStatus",
        "WaitExitType",
        "WaitReturnPct",
        "DifferencePct",
    ]

    print(
        result[
            display_cols
        ].round(2).to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Important boundary: 100-125%
    # --------------------------------------------------------

    boundary = result[
        result["GrowthBand"]
        == "100-125%"
    ].copy()

    print()
    print("=" * 80)
    print("CRITICAL BOUNDARY : 100-125%")
    print("=" * 80)
    print()

    if boundary.empty:

        print(
            "No stocks in 100-125% band."
        )

    else:

        print(
            boundary[
                display_cols
            ].round(2).to_string(
                index=False
            )
        )

        print()

        original_total = (
            boundary[
                "OriginalReturnPct"
            ]
            .fillna(0.0)
            .sum()
        )

        wait_total = (
            boundary[
                "WaitReturnPct"
            ]
            .fillna(0.0)
            .sum()
        )

        print(
            "100-125% original total : "
            f"{original_total:+.2f}%"
        )

        print(
            "100-125% WAIT total     : "
            f"{wait_total:+.2f}%"
        )

        print(
            "100-125% difference     : "
            f"{wait_total - original_total:+.2f}%"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("GROWTH BAND SUMMARY")
    print("=" * 80)
    print()

    print(
        summary.round(2).to_string(
            index=False
        )
    )

    print()
    print("=" * 80)
    print("SAVED")
    print("=" * 80)
    print()

    print(
        f"Detail  : "
        f"{OUTPUT_DETAIL.relative_to(BASE_DIR)}"
    )

    print(
        f"Summary : "
        f"{OUTPUT_SUMMARY.relative_to(BASE_DIR)}"
    )


if __name__ == "__main__":
    main()