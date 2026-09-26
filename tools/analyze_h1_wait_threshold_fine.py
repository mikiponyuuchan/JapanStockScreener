from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# H1 MID_CXV
# WAIT Threshold Fine Analysis
#
# Threshold:
#   80% - 130%, step 5%
#
# Pullback:
#   -0.50% fixed
#
# Purpose:
#   Check whether the strong result around 100% is a stable
#   zone or only a single-point optimum.
# ============================================================


BASE_DIR = Path(__file__).resolve().parents[1]

DETAIL_FILE = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_hybrid_wait_sensitivity_detail.csv"
)

OUTPUT_DETAIL = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_wait_threshold_fine_detail.csv"
)

OUTPUT_SUMMARY = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_wait_threshold_fine_summary.csv"
)


TARGET_PULLBACK = -0.50

THRESHOLDS = list(
    np.arange(
        80.0,
        130.0 + 0.1,
        5.0,
    )
)


# ============================================================
# Utility
# ============================================================

def normalize_code(value):
    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    return code


def safe_float(value):
    try:
        if pd.isna(value):
            return np.nan

        return float(value)

    except Exception:
        return np.nan


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print("H1 MID_CXV WAIT THRESHOLD FINE ANALYSIS")
    print("=" * 80)
    print()

    if not DETAIL_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {DETAIL_FILE}"
        )

    src = pd.read_csv(
        DETAIL_FILE,
        dtype={"Code": str},
        encoding="utf-8-sig",
    )

    src["Code"] = src["Code"].apply(
        normalize_code
    )

    src["DetectionDate"] = pd.to_datetime(
        src["DetectionDate"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    numeric_cols = [
        "WaitThreshold",
        "PullbackLevel",
        "VolumeRatioGrowthPct",
        "OriginalReturnPct",
        "HybridReturnPct",
    ]

    for col in numeric_cols:
        src[col] = pd.to_numeric(
            src[col],
            errors="coerce",
        )

    # --------------------------------------------------------
    # We only need the -0.50% result.
    #
    # The WAIT result itself is independent of the threshold.
    # Therefore, use one existing threshold as the source of
    # the -0.50% pullback simulation.
    # --------------------------------------------------------

    candidates = src[
        np.isclose(
            src["PullbackLevel"],
            TARGET_PULLBACK,
        )
    ].copy()

    if candidates.empty:
        raise RuntimeError(
            "No -0.50% pullback data found."
        )

    # Prefer threshold=100 because it is the current reference.
    base = candidates[
        np.isclose(
            candidates["WaitThreshold"],
            100.0,
        )
    ].copy()

    if base.empty:
        raise RuntimeError(
            "Threshold=100%, pullback=-0.50% "
            "reference data not found."
        )

    base = base.drop_duplicates(
        [
            "DetectionDate",
            "Code",
        ],
        keep="first",
    ).copy()

    print(
        f"Total trades : {len(base)}"
    )

    baseline_total = (
        base["OriginalReturnPct"]
        .fillna(0.0)
        .sum()
    )

    print(
        f"09:30 original total : "
        f"{baseline_total:+.2f}%"
    )

    print(
        f"Pullback fixed       : "
        f"{TARGET_PULLBACK:+.2f}%"
    )

    print()

    # --------------------------------------------------------
    # Important:
    #
    # At threshold=100, rows below 100 are BUY_0930, so their
    # HybridReturnPct is the original return.
    #
    # For fine thresholds below 100 we need actual WAIT results
    # for stocks in the 80-100 range.
    #
    # Those WAIT results are available from lower-threshold
    # simulations (50% or 75%).
    #
    # Build one actual -0.50% WAIT result per stock from any
    # threshold where that stock was classified WAIT.
    # --------------------------------------------------------

    wait_source = candidates[
        candidates["Decision"] == "WAIT"
    ].copy()

    wait_source = wait_source.sort_values(
        [
            "DetectionDate",
            "Code",
            "WaitThreshold",
        ]
    )

    wait_source = wait_source.drop_duplicates(
        [
            "DetectionDate",
            "Code",
        ],
        keep="first",
    )

    wait_cols = [
        "DetectionDate",
        "Code",
        "Status",
        "EntryTime",
        "EntryPrice",
        "ExitType",
        "HybridReturnPct",
    ]

    wait_source = wait_source[
        wait_cols
    ].copy()

    wait_source = wait_source.rename(
        columns={
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
    # Merge actual WAIT outcome onto baseline
    # --------------------------------------------------------

    data = base[
        [
            "DetectionDate",
            "Code",
            "Name",
            "VolumeRatioGrowthPct",
            "OriginalExitType",
            "OriginalReturnPct",
        ]
    ].copy()

    data = data.merge(
        wait_source,
        on=[
            "DetectionDate",
            "Code",
        ],
        how="left",
        validate="one_to_one",
    )

    # --------------------------------------------------------
    # Threshold simulations
    # --------------------------------------------------------

    detail_rows = []
    summary_rows = []

    for threshold in THRESHOLDS:

        buy_count = 0
        wait_count = 0
        wait_executed = 0
        wait_no_fill = 0
        wait_skip = 0

        strategy_returns = []

        for _, row in data.iterrows():

            growth = safe_float(
                row["VolumeRatioGrowthPct"]
            )

            original_return = safe_float(
                row["OriginalReturnPct"]
            )

            # Missing growth -> BUY_0930
            is_wait = (
                not np.isnan(growth)
                and growth >= threshold
            )

            if not is_wait:

                decision = "BUY_0930"
                status = "ORIGINAL"
                exit_type = row[
                    "OriginalExitType"
                ]
                strategy_return = (
                    original_return
                    if not np.isnan(original_return)
                    else 0.0
                )

                buy_count += 1

            else:

                decision = "WAIT"
                wait_count += 1

                status = row.get(
                    "WaitStatus",
                    np.nan,
                )

                exit_type = row.get(
                    "WaitExitType",
                    np.nan,
                )

                wait_return = safe_float(
                    row.get(
                        "WaitReturnPct",
                        np.nan,
                    )
                )

                if status == "EXECUTED":

                    wait_executed += 1

                    strategy_return = (
                        wait_return
                        if not np.isnan(wait_return)
                        else 0.0
                    )

                elif status == "NO_FILL":

                    wait_no_fill += 1
                    strategy_return = 0.0

                else:

                    wait_skip += 1
                    strategy_return = 0.0

            strategy_returns.append(
                strategy_return
            )

            detail_rows.append(
                {
                    "WaitThreshold":
                        threshold,
                    "PullbackLevel":
                        TARGET_PULLBACK,
                    "DetectionDate":
                        row["DetectionDate"],
                    "Code":
                        row["Code"],
                    "Name":
                        row["Name"],
                    "VolumeRatioGrowthPct":
                        growth,
                    "Decision":
                        decision,
                    "OriginalExitType":
                        row["OriginalExitType"],
                    "OriginalReturnPct":
                        original_return,
                    "WaitStatus":
                        row.get(
                            "WaitStatus",
                            np.nan,
                        ),
                    "WaitExitType":
                        row.get(
                            "WaitExitType",
                            np.nan,
                        ),
                    "WaitReturnPct":
                        safe_float(
                            row.get(
                                "WaitReturnPct",
                                np.nan,
                            )
                        ),
                    "StrategyReturnPct":
                        strategy_return,
                    "DifferencePct":
                        strategy_return
                        - (
                            original_return
                            if not np.isnan(
                                original_return
                            )
                            else 0.0
                        ),
                }
            )

        total_return = float(
            np.sum(strategy_returns)
        )

        mean_return = float(
            np.mean(strategy_returns)
        )

        summary_rows.append(
            {
                "WaitThreshold":
                    threshold,
                "PullbackLevel":
                    TARGET_PULLBACK,
                "Buy0930":
                    buy_count,
                "Wait":
                    wait_count,
                "WaitExecuted":
                    wait_executed,
                "WaitNoFill":
                    wait_no_fill,
                "WaitSkipData":
                    wait_skip,
                "HybridTotalReturnPct":
                    total_return,
                "HybridMeanReturnPct":
                    mean_return,
                "OriginalTotalReturnPct":
                    baseline_total,
                "DifferenceFrom0930Pct":
                    total_return
                    - baseline_total,
            }
        )

    # --------------------------------------------------------
    # DataFrames
    # --------------------------------------------------------

    detail = pd.DataFrame(
        detail_rows
    )

    summary = pd.DataFrame(
        summary_rows
    )

    summary = summary.sort_values(
        "WaitThreshold",
        ascending=True,
    ).reset_index(drop=True)

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

    summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print("=" * 80)
    print("FINE THRESHOLD SUMMARY")
    print("=" * 80)
    print()

    display_cols = [
        "WaitThreshold",
        "Buy0930",
        "Wait",
        "WaitExecuted",
        "WaitNoFill",
        "WaitSkipData",
        "HybridTotalReturnPct",
        "DifferenceFrom0930Pct",
    ]

    print(
        summary[
            display_cols
        ].round(2).to_string(
            index=False
        )
    )

    print()

    # --------------------------------------------------------
    # Best
    # --------------------------------------------------------

    best = summary.sort_values(
        "HybridTotalReturnPct",
        ascending=False,
    ).iloc[0]

    print("=" * 80)
    print("BEST FINE THRESHOLD")
    print("=" * 80)
    print()

    print(
        f"WAIT threshold : "
        f"{best['WaitThreshold']:.0f}%"
    )

    print(
        f"Pullback       : "
        f"{TARGET_PULLBACK:+.2f}%"
    )

    print(
        f"Hybrid return  : "
        f"{best['HybridTotalReturnPct']:+.2f}%"
    )

    print(
        f"09:30 original : "
        f"{baseline_total:+.2f}%"
    )

    print(
        f"Difference     : "
        f"{best['DifferenceFrom0930Pct']:+.2f}%"
    )

    print()

    # --------------------------------------------------------
    # Show changes between adjacent thresholds
    # --------------------------------------------------------

    summary["ChangeFromPrevious"] = (
        summary["HybridTotalReturnPct"]
        .diff()
    )

    print("=" * 80)
    print("THRESHOLD STEP CHANGES")
    print("=" * 80)
    print()

    print(
        summary[
            [
                "WaitThreshold",
                "HybridTotalReturnPct",
                "ChangeFromPrevious",
            ]
        ].round(2).to_string(
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