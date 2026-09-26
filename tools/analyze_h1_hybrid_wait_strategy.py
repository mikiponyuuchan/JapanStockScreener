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
    PULLBACK_LEVELS,
    download_intraday,
    find_pullback_entry,
    simulate_exit,
    normalize_code,
    safe_float,
)


# ============================================================
# H1 MID_CXV
# Hybrid WAIT Strategy Analysis
#
# BUY:
#   VolumeRatioGrowthPct < 100
#       -> original 09:30 entry
#
# WAIT:
#   VolumeRatioGrowthPct >= 100
#       -> pullback limit order
#
# WAIT no-fill:
#       -> no trade / 0% return
#
# Exit:
#   TAKE +10%
#   STOP -3%
#   otherwise day close
#
# Same-bar TAKE + STOP:
#   STOP priority
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
    / "h1_hybrid_wait_strategy_detail.csv"
)

OUTPUT_SUMMARY = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_hybrid_wait_strategy_summary.csv"
)


WAIT_GROWTH_THRESHOLD = 100.0


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
    print("H1 MID_CXV HYBRID WAIT STRATEGY ANALYSIS")
    print("=" * 80)
    print()

    if not FEATURE_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {FEATURE_FILE}"
        )

    src = pd.read_csv(
        FEATURE_FILE,
        dtype={"Code": str},
        encoding="utf-8-sig",
    )

    src["Code"] = src["Code"].apply(
        normalize_code
    )

    # --------------------------------------------------------
    # OriginalEntryPrice
    #
    # h1_wait_pullback_features.csv には元戦略のエントリー価格が
    # 含まれていないため、h1_delayed_entry_detail.csv から
    # DetectionDate + Code で取得する。
    # --------------------------------------------------------

    if not DELAYED_ENTRY_FILE.exists():
        raise FileNotFoundError(
            f"Not found : {DELAYED_ENTRY_FILE}"
        )

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
    # Original 09:30 baseline
    # --------------------------------------------------------

    baseline_total = (
        src["OriginalReturnPct"]
        .fillna(0.0)
        .sum()
    )

    baseline_mean = (
        src["OriginalReturnPct"]
        .mean()
    )

    baseline_take = int(
        (src["OriginalExitType"] == "TAKE").sum()
    )

    baseline_stop = int(
        (src["OriginalExitType"] == "STOP").sum()
    )

    baseline_close = int(
        (src["OriginalExitType"] == "CLOSE").sum()
    )

    print(f"Total trades : {len(src)}")
    print()

    print("09:30 ORIGINAL")
    print(
        f"TAKE={baseline_take} "
        f"STOP={baseline_stop} "
        f"CLOSE={baseline_close}"
    )
    print(
        f"Total return : {baseline_total:+.2f}%"
    )
    print(
        f"Mean return  : {baseline_mean:+.2f}%"
    )
    print()

    # --------------------------------------------------------
    # WAIT classification
    # --------------------------------------------------------

    wait_mask = (
        src["VolumeRatioGrowthPct"]
        >= WAIT_GROWTH_THRESHOLD
    )

    wait_count = int(wait_mask.sum())
    buy_count = int((~wait_mask).sum())

    print(
        f"WAIT rule : VolumeRatioGrowthPct "
        f">= {WAIT_GROWTH_THRESHOLD:.0f}%"
    )
    print(
        f"BUY  : {buy_count}"
    )
    print(
        f"WAIT : {wait_count}"
    )
    print()

    print("=" * 80)
    print("WAIT ORIGINAL OUTCOMES")
    print("=" * 80)
    print()

    wait_original = src[wait_mask].copy()

    print(
        wait_original[
            "OriginalExitType"
        ].value_counts(
            dropna=False
        )
    )

    print()

    # --------------------------------------------------------
    # Intraday cache
    # --------------------------------------------------------

    intraday_cache = {}

    detail_rows = []

    total_wait_simulations = (
        wait_count
        * len(PULLBACK_LEVELS)
    )

    simulation_no = 0

    # --------------------------------------------------------
    # Each pullback level
    # --------------------------------------------------------

    for level in PULLBACK_LEVELS:

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
                and growth
                >= WAIT_GROWTH_THRESHOLD
            )

            # ------------------------------------------------
            # BUY group:
            # use original 09:30 result unchanged
            # ------------------------------------------------

            if not is_wait:

                detail_rows.append(
                    {
                        "DetectionDate":
                            detection_date,
                        "Code":
                            code,
                        "Name":
                            name,
                        "PullbackLevel":
                            level,
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

            # ------------------------------------------------
            # WAIT group
            # ------------------------------------------------

            simulation_no += 1

            print(
                f"[{simulation_no}/"
                f"{total_wait_simulations}] "
                f"{detection_date} "
                f"{code} "
                f"{name} "
                f"{level:+.2f}%"
            )

            # We need the actual 09:30 reference price.
            #
            # The feature file does not contain it reliably,
            # so obtain the 09:30 minute bar and use its Close
            # as the reference only if available.
            #
            # This will be checked against the existing
            # pullback-analysis convention.

            key = (
                detection_date,
                code,
            )

            if key not in intraday_cache:
                intraday_cache[key] = (
                    download_intraday(
                        code,
                        detection_date,
                    )
                )

            intraday = intraday_cache[key]

            if (
                intraday is None
                or intraday.empty
            ):

                detail_rows.append(
                    {
                        "DetectionDate":
                            detection_date,
                        "Code":
                            code,
                        "Name":
                            name,
                        "PullbackLevel":
                            level,
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

            bar0930 = intraday.between_time(
                "09:30",
                "09:30",
                inclusive="both",
            )

            if bar0930.empty:

                detail_rows.append(
                    {
                        "DetectionDate":
                            detection_date,
                        "Code":
                            code,
                        "Name":
                            name,
                        "PullbackLevel":
                            level,
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

            # ------------------------------------------------
            # Pullback base price
            #
            # Yahoo 09:30 1-minute Close ではなく、
            # H1戦略で実際に使用した OriginalEntryPrice を基準にする。
            # これにより元戦略の09:30エントリー価格から
            # -0.50% ～ -3.00% の押し目を正しく検証できる。
            # ------------------------------------------------

            base_price = safe_float(
                row.get(
                    "OriginalEntryPrice",
                    np.nan,
                )
            )

            if np.isnan(base_price):

                detail_rows.append(
                    {
                        "DetectionDate":
                            detection_date,
                        "Code":
                            code,
                        "Name":
                            name,
                        "PullbackLevel":
                            level,
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

            # ------------------------------------------------
            # No fill = no trade = 0%
            # ------------------------------------------------

            if entry is None:

                detail_rows.append(
                    {
                        "DetectionDate":
                            detection_date,
                        "Code":
                            code,
                        "Name":
                            name,
                        "PullbackLevel":
                            level,
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

            entry_time = entry["EntryTime"]
            entry_price = entry["EntryPrice"]

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
                    exit_result["ReturnPct"]
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
                    "DetectionDate":
                        detection_date,
                    "Code":
                        code,
                    "Name":
                        name,
                    "PullbackLevel":
                        level,
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
                        fmt_time(entry_time),
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

    for level in PULLBACK_LEVELS:

        g = detail[
            detail["PullbackLevel"] == level
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
        "HybridTotalReturnPct",
        ascending=False,
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
    print("HYBRID STRATEGY SUMMARY")
    print("=" * 80)
    print()

    display_cols = [
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
        "OriginalTotalReturnPct",
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
    print("=" * 80)
    print("BEST HYBRID LEVEL")
    print("=" * 80)
    print()

    if not summary.empty:

        best = summary.iloc[0]

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