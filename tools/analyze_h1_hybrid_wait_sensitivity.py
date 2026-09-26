from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ============================================================
# Path
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================
# Reuse existing true-pullback logic
# ============================================================

from tools.analyze_h1_true_pullback_entry import (
    download_intraday,
    find_pullback_entry,
    simulate_exit,
    normalize_code,
    safe_float,
)


# ============================================================
# H1 MID_CXV
# Hybrid WAIT Strategy Sensitivity Analysis
#
# WAIT thresholds:
#   50 / 75 / 100 / 125 / 150 %
#
# Pullback levels:
#   -0.50 / -0.75 / -1.00 / -1.25 %
#
# BUY:
#   VolumeRatioGrowthPct < threshold
#       -> original 09:30 result
#
# WAIT:
#   VolumeRatioGrowthPct >= threshold
#       -> pullback limit order
#
# WAIT no-fill:
#       -> no trade / 0%
#
# Entry:
#   Uses tick-size-adjusted find_pullback_entry()
#
# Exit:
#   TAKE +10%
#   STOP -3%
#   otherwise day close
# ============================================================


FEATURE_FILE = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_wait_pullback_features.csv"
)

DELAYED_ENTRY_FILE = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_delayed_entry_detail.csv"
)

OUTPUT_DETAIL = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_hybrid_wait_sensitivity_detail.csv"
)

OUTPUT_SUMMARY = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_hybrid_wait_sensitivity_summary.csv"
)


WAIT_THRESHOLDS = [
    50.0,
    75.0,
    100.0,
    125.0,
    150.0,
]

PULLBACK_LEVELS = [
    -0.50,
    -0.75,
    -1.00,
    -1.25,
]


# ============================================================
# Utility
# ============================================================

def fmt_time(value):
    if value is None:
        return ""

    try:
        return pd.Timestamp(value).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        return str(value)


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print("H1 MID_CXV HYBRID WAIT SENSITIVITY ANALYSIS")
    print("=" * 80)
    print()

    if not FEATURE_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {FEATURE_FILE}"
        )

    if not DELAYED_ENTRY_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {DELAYED_ENTRY_FILE}"
        )

    # --------------------------------------------------------
    # Feature data
    # --------------------------------------------------------

    src = pd.read_csv(
        FEATURE_FILE,
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

    # --------------------------------------------------------
    # OriginalEntryPrice
    # --------------------------------------------------------

    entry_src = pd.read_csv(
        DELAYED_ENTRY_FILE,
        dtype={"Code": str},
        encoding="utf-8-sig",
    )

    entry_src["Code"] = entry_src["Code"].apply(
        normalize_code
    )

    entry_src["DetectionDate"] = pd.to_datetime(
        entry_src["DetectionDate"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    if "OriginalEntryPrice" not in entry_src.columns:
        raise RuntimeError(
            "OriginalEntryPrice column not found "
            "in h1_delayed_entry_detail.csv"
        )

    entry_src["OriginalEntryPrice"] = pd.to_numeric(
        entry_src["OriginalEntryPrice"],
        errors="coerce",
    )

    entry_src = (
        entry_src[
            [
                "DetectionDate",
                "Code",
                "OriginalEntryPrice",
            ]
        ]
        .dropna(
            subset=["OriginalEntryPrice"]
        )
        .drop_duplicates(
            ["DetectionDate", "Code"],
            keep="first",
        )
    )

    src = src.merge(
        entry_src,
        on=[
            "DetectionDate",
            "Code",
        ],
        how="left",
        validate="one_to_one",
    )

    missing_entry_price = int(
        src["OriginalEntryPrice"].isna().sum()
    )

    print(
        "OriginalEntryPrice matched : "
        f"{len(src) - missing_entry_price}"
        f"/{len(src)}"
    )

    if missing_entry_price:
        print(
            "WARNING : OriginalEntryPrice missing : "
            f"{missing_entry_price}"
        )

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

    required = [
        "DetectionDate",
        "Code",
        "Name",
        "OriginalExitType",
        "OriginalReturnPct",
        "VolumeRatioGrowthPct",
    ]

    missing = [
        col
        for col in required
        if col not in src.columns
    ]

    if missing:
        raise RuntimeError(
            f"Missing columns : {missing}"
        )

    src["OriginalReturnPct"] = pd.to_numeric(
        src["OriginalReturnPct"],
        errors="coerce",
    )

    src["VolumeRatioGrowthPct"] = pd.to_numeric(
        src["VolumeRatioGrowthPct"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Original baseline
    # --------------------------------------------------------

    baseline_total = (
        src["OriginalReturnPct"]
        .fillna(0.0)
        .sum()
    )

    baseline_mean = (
        src["OriginalReturnPct"]
        .fillna(0.0)
        .mean()
    )

    print(f"Total trades : {len(src)}")
    print(
        f"09:30 original total : "
        f"{baseline_total:+.2f}%"
    )
    print(
        f"09:30 original mean  : "
        f"{baseline_mean:+.2f}%"
    )
    print()

    # --------------------------------------------------------
    # Download/cache intraday data once
    # --------------------------------------------------------

    intraday_cache = {}

    unique_keys = (
        src[
            [
                "DetectionDate",
                "Code",
            ]
        ]
        .drop_duplicates()
        .itertuples(
            index=False,
            name=None,
        )
    )

    unique_keys = list(unique_keys)

    print("=" * 80)
    print("INTRADAY DATA CACHE")
    print("=" * 80)
    print()

    for no, (detection_date, code) in enumerate(
        unique_keys,
        start=1,
    ):

        code = normalize_code(code)

        print(
            f"[{no}/{len(unique_keys)}] "
            f"{detection_date} {code}"
        )

        intraday_cache[
            (
                str(detection_date),
                code,
            )
        ] = download_intraday(
            code,
            str(detection_date),
        )

    # --------------------------------------------------------
    # Sensitivity simulation
    # --------------------------------------------------------

    detail_rows = []

    total_patterns = (
        len(WAIT_THRESHOLDS)
        * len(PULLBACK_LEVELS)
    )

    pattern_no = 0

    for threshold in WAIT_THRESHOLDS:

        for level in PULLBACK_LEVELS:

            pattern_no += 1

            wait_mask = (
                src["VolumeRatioGrowthPct"]
                >= threshold
            )

            wait_count = int(
                wait_mask.sum()
            )

            buy_count = int(
                (~wait_mask).sum()
            )

            print()
            print(
                f"[PATTERN "
                f"{pattern_no}/{total_patterns}] "
                f"threshold={threshold:.0f}% "
                f"pullback={level:+.2f}% "
                f"BUY={buy_count} "
                f"WAIT={wait_count}"
            )

            for _, row in src.iterrows():

                detection_date = str(
                    row["DetectionDate"]
                )

                code = normalize_code(
                    row["Code"]
                )

                name = row.get(
                    "Name",
                    "",
                )

                original_exit = row[
                    "OriginalExitType"
                ]

                original_return = safe_float(
                    row["OriginalReturnPct"]
                )

                growth = safe_float(
                    row["VolumeRatioGrowthPct"]
                )

                is_wait = (
                    not np.isnan(growth)
                    and growth >= threshold
                )

                # --------------------------------------------
                # BUY group
                # --------------------------------------------

                if not is_wait:

                    detail_rows.append(
                        {
                            "WaitThreshold":
                                threshold,
                            "PullbackLevel":
                                level,
                            "DetectionDate":
                                detection_date,
                            "Code":
                                code,
                            "Name":
                                name,
                            "Decision":
                                "BUY_0930",
                            "VolumeRatioGrowthPct":
                                growth,
                            "OriginalExitType":
                                original_exit,
                            "OriginalReturnPct":
                                original_return,
                            "Status":
                                "ORIGINAL",
                            "EntryTime":
                                "09:30",
                            "EntryPrice":
                                np.nan,
                            "ExitType":
                                original_exit,
                            "ReturnPct":
                                original_return,
                            "HybridReturnPct":
                                original_return,
                            "HitTakeTime":
                                "",
                            "HitStopTime":
                                "",
                            "SameBarBothHit":
                                False,
                        }
                    )

                    continue

                # --------------------------------------------
                # WAIT group
                # --------------------------------------------

                intraday = intraday_cache.get(
                    (
                        detection_date,
                        code,
                    )
                )

                if (
                    intraday is None
                    or intraday.empty
                ):

                    detail_rows.append(
                        {
                            "WaitThreshold":
                                threshold,
                            "PullbackLevel":
                                level,
                            "DetectionDate":
                                detection_date,
                            "Code":
                                code,
                            "Name":
                                name,
                            "Decision":
                                "WAIT",
                            "VolumeRatioGrowthPct":
                                growth,
                            "OriginalExitType":
                                original_exit,
                            "OriginalReturnPct":
                                original_return,
                            "Status":
                                "SKIP_DATA",
                            "EntryTime":
                                "",
                            "EntryPrice":
                                np.nan,
                            "ExitType":
                                "",
                            "ReturnPct":
                                np.nan,
                            "HybridReturnPct":
                                np.nan,
                            "HitTakeTime":
                                "",
                            "HitStopTime":
                                "",
                            "SameBarBothHit":
                                False,
                        }
                    )

                    continue

                base_price = safe_float(
                    row.get(
                        "OriginalEntryPrice",
                        np.nan,
                    )
                )

                if np.isnan(base_price):

                    detail_rows.append(
                        {
                            "WaitThreshold":
                                threshold,
                            "PullbackLevel":
                                level,
                            "DetectionDate":
                                detection_date,
                            "Code":
                                code,
                            "Name":
                                name,
                            "Decision":
                                "WAIT",
                            "VolumeRatioGrowthPct":
                                growth,
                            "OriginalExitType":
                                original_exit,
                            "OriginalReturnPct":
                                original_return,
                            "Status":
                                "SKIP_DATA",
                            "EntryTime":
                                "",
                            "EntryPrice":
                                np.nan,
                            "ExitType":
                                "",
                            "ReturnPct":
                                np.nan,
                            "HybridReturnPct":
                                np.nan,
                            "HitTakeTime":
                                "",
                            "HitStopTime":
                                "",
                            "SameBarBothHit":
                                False,
                        }
                    )

                    continue

                entry = find_pullback_entry(
                    intraday,
                    base_price,
                    level,
                )

                # --------------------------------------------
                # No fill = no trade = 0%
                # --------------------------------------------

                if entry is None:

                    detail_rows.append(
                        {
                            "WaitThreshold":
                                threshold,
                            "PullbackLevel":
                                level,
                            "DetectionDate":
                                detection_date,
                            "Code":
                                code,
                            "Name":
                                name,
                            "Decision":
                                "WAIT",
                            "VolumeRatioGrowthPct":
                                growth,
                            "OriginalExitType":
                                original_exit,
                            "OriginalReturnPct":
                                original_return,
                            "Status":
                                "NO_FILL",
                            "EntryTime":
                                "",
                            "EntryPrice":
                                np.nan,
                            "ExitType":
                                "NO_TRADE",
                            "ReturnPct":
                                0.0,
                            "HybridReturnPct":
                                0.0,
                            "HitTakeTime":
                                "",
                            "HitStopTime":
                                "",
                            "SameBarBothHit":
                                False,
                        }
                    )

                    continue

                entry_time = entry[
                    "EntryTime"
                ]

                entry_price = entry[
                    "EntryPrice"
                ]

                exit_result = simulate_exit(
                    intraday,
                    entry_time,
                    entry_price,
                )

                if exit_result is None:

                    hybrid_return = np.nan
                    exit_type = ""
                    return_pct = np.nan
                    hit_take = ""
                    hit_stop = ""
                    same_bar = False

                else:

                    hybrid_return = safe_float(
                        exit_result[
                            "ReturnPct"
                        ]
                    )

                    exit_type = exit_result[
                        "ExitType"
                    ]

                    return_pct = hybrid_return

                    hit_take = fmt_time(
                        exit_result.get(
                            "HitTakeTime"
                        )
                    )

                    hit_stop = fmt_time(
                        exit_result.get(
                            "HitStopTime"
                        )
                    )

                    same_bar = bool(
                        exit_result.get(
                            "SameBarBothHit",
                            False,
                        )
                    )

                detail_rows.append(
                    {
                        "WaitThreshold":
                            threshold,
                        "PullbackLevel":
                            level,
                        "DetectionDate":
                            detection_date,
                        "Code":
                            code,
                        "Name":
                            name,
                        "Decision":
                            "WAIT",
                        "VolumeRatioGrowthPct":
                            growth,
                        "OriginalExitType":
                            original_exit,
                        "OriginalReturnPct":
                            original_return,
                        "Status":
                            "EXECUTED",
                        "EntryTime":
                            fmt_time(
                                entry_time
                            ),
                        "EntryPrice":
                            entry_price,
                        "ExitType":
                            exit_type,
                        "ReturnPct":
                            return_pct,
                        "HybridReturnPct":
                            hybrid_return,
                        "HitTakeTime":
                            hit_take,
                        "HitStopTime":
                            hit_stop,
                        "SameBarBothHit":
                            same_bar,
                    }
                )

    # --------------------------------------------------------
    # Detail
    # --------------------------------------------------------

    detail = pd.DataFrame(
        detail_rows
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary_rows = []

    for threshold in WAIT_THRESHOLDS:

        for level in PULLBACK_LEVELS:

            g = detail[
                (
                    detail["WaitThreshold"]
                    == threshold
                )
                &
                (
                    detail["PullbackLevel"]
                    == level
                )
            ].copy()

            wait = g[
                g["Decision"] == "WAIT"
            ].copy()

            executed_wait = int(
                (
                    wait["Status"]
                    == "EXECUTED"
                ).sum()
            )

            no_fill = int(
                (
                    wait["Status"]
                    == "NO_FILL"
                ).sum()
            )

            skip_data = int(
                (
                    wait["Status"]
                    == "SKIP_DATA"
                ).sum()
            )

            take = int(
                (
                    g["ExitType"]
                    == "TAKE"
                ).sum()
            )

            stop = int(
                (
                    g["ExitType"]
                    == "STOP"
                ).sum()
            )

            close = int(
                (
                    g["ExitType"]
                    == "CLOSE"
                ).sum()
            )

            hybrid_total = (
                g["HybridReturnPct"]
                .fillna(0.0)
                .sum()
            )

            hybrid_mean = (
                g["HybridReturnPct"]
                .fillna(0.0)
                .mean()
            )

            difference = (
                hybrid_total
                - baseline_total
            )

            summary_rows.append(
                {
                    "WaitThreshold":
                        threshold,
                    "PullbackLevel":
                        level,
                    "TotalTrades":
                        len(g),
                    "Buy0930":
                        int(
                            (
                                g["Decision"]
                                == "BUY_0930"
                            ).sum()
                        ),
                    "Wait":
                        len(wait),
                    "WaitExecuted":
                        executed_wait,
                    "WaitNoFill":
                        no_fill,
                    "WaitSkipData":
                        skip_data,
                    "Take":
                        take,
                    "Stop":
                        stop,
                    "Close":
                        close,
                    "HybridTotalReturnPct":
                        hybrid_total,
                    "HybridMeanReturnPct":
                        hybrid_mean,
                    "OriginalTotalReturnPct":
                        baseline_total,
                    "DifferenceFrom0930Pct":
                        difference,
                }
            )

    summary = pd.DataFrame(
        summary_rows
    )

    summary = summary.sort_values(
        [
            "HybridTotalReturnPct",
            "WaitThreshold",
            "PullbackLevel",
        ],
        ascending=[
            False,
            True,
            False,
        ],
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

    print()
    print("=" * 80)
    print("SENSITIVITY SUMMARY")
    print("=" * 80)
    print()

    display_cols = [
        "WaitThreshold",
        "PullbackLevel",
        "Buy0930",
        "Wait",
        "WaitExecuted",
        "WaitNoFill",
        "WaitSkipData",
        "Take",
        "Stop",
        "Close",
        "HybridTotalReturnPct",
        "DifferenceFrom0930Pct",
    ]

    print(
        summary[
            display_cols
        ]
        .round(2)
        .to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Matrix
    # --------------------------------------------------------

    matrix = summary.pivot(
        index="WaitThreshold",
        columns="PullbackLevel",
        values="HybridTotalReturnPct",
    )

    matrix = matrix.reindex(
        WAIT_THRESHOLDS
    )

    matrix = matrix.reindex(
        columns=PULLBACK_LEVELS
    )

    print()
    print("=" * 80)
    print("HYBRID TOTAL RETURN MATRIX")
    print("=" * 80)
    print()

    print(
        matrix.round(2).to_string()
    )

    # --------------------------------------------------------
    # Best
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("BEST COMBINATION")
    print("=" * 80)
    print()

    if not summary.empty:

        best = summary.iloc[0]

        print(
            f"WAIT threshold : "
            f"{best['WaitThreshold']:.0f}%"
        )

        print(
            f"Pullback level : "
            f"{best['PullbackLevel']:+.2f}%"
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
