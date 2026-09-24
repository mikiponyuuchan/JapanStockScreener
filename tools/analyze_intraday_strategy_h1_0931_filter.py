from pathlib import Path

import pandas as pd


SIGNAL_FILE = Path(
    "data/analysis/intraday_strategy_h1_0931_signal.csv"
)

ENTRY_FILE = Path(
    "data/analysis/intraday_strategy_h1_entry_timing.csv"
)

OUTPUT_FILE = Path(
    "data/analysis/intraday_strategy_h1_0931_filter.csv"
)


THRESHOLDS = [
    0.0,
    -1.0,
    -2.0,
    -3.0,
    -4.0,
]


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def main():

    print("=" * 76)
    print("H1 09:31 FILTER -> 09:32 ENTRY")
    print("=" * 76)

    if not SIGNAL_FILE.exists():
        raise RuntimeError(
            f"Not found : {SIGNAL_FILE}"
        )

    if not ENTRY_FILE.exists():
        raise RuntimeError(
            f"Not found : {ENTRY_FILE}"
        )

    signal = pd.read_csv(
        SIGNAL_FILE,
        dtype={"Code": str},
        low_memory=False,
    )

    entry = pd.read_csv(
        ENTRY_FILE,
        dtype={"Code": str},
        low_memory=False,
    )

    signal["Code"] = (
        signal["Code"]
        .map(normalize_code)
    )

    entry["Code"] = (
        entry["Code"]
        .map(normalize_code)
    )

    # ============================================
    # 09:32エントリー結果だけ取得
    # ============================================

    entry = entry[
        entry["Method"] == "T0932"
    ].copy()

    entry_cols = [
        "DetectionDate",
        "Code",
        "EntryPrice",
        "ExitType",
        "ReturnPct",
        "MaxHighPct",
        "MinLowPct",
        "ClosePct",
    ]

    entry = entry[
        entry_cols
    ].copy()

    entry = entry.rename(
        columns={
            "EntryPrice":
                "Entry0932Price",
            "ExitType":
                "ExitType0932",
            "ReturnPct":
                "ReturnPct0932",
            "MaxHighPct":
                "MaxHighPct0932",
            "MinLowPct":
                "MinLowPct0932",
            "ClosePct":
                "ClosePct0932",
        }
    )

    # ============================================
    # 09:31シグナルと09:32売買結果を結合
    # ============================================

    merged = signal.merge(
        entry,
        on=[
            "DetectionDate",
            "Code",
        ],
        how="inner",
    )

    merged["Close0931Pct"] = pd.to_numeric(
        merged["Close0931Pct"],
        errors="coerce",
    )

    merged["ReturnPct0932"] = pd.to_numeric(
        merged["ReturnPct0932"],
        errors="coerce",
    )

    merged = merged[
        merged["Close0931Pct"].notna()
        & merged["ReturnPct0932"].notna()
    ].copy()

    print(
        f"Usable rows : {len(merged)}"
    )

    print()
    print("=" * 76)
    print("THRESHOLD COMPARISON")
    print("=" * 76)

    summary_rows = []

    for threshold in THRESHOLDS:

        selected = merged[
            merged["Close0931Pct"]
            >= threshold
        ].copy()

        returns = pd.to_numeric(
            selected["ReturnPct0932"],
            errors="coerce",
        ).dropna()

        if returns.empty:

            summary_rows.append({
                "Threshold":
                    threshold,
                "Trades":
                    0,
                "MeanReturn":
                    pd.NA,
                "Median":
                    pd.NA,
                "WinRate":
                    pd.NA,
                "TotalReturn":
                    0.0,
                "TAKE":
                    0,
                "STOP":
                    0,
                "CLOSE":
                    0,
            })

            continue

        exits = (
            selected[
                "ExitType0932"
            ]
            .astype(str)
            .value_counts()
        )

        take_count = int(
            exits.get(
                "TAKE",
                0,
            )
        )

        stop_count = int(
            exits.get(
                "STOP",
                0,
            )
        )

        close_count = int(
            exits.get(
                "CLOSE",
                0,
            )
        )

        summary_rows.append({
            "Threshold":
                threshold,
            "Trades":
                len(returns),
            "MeanReturn":
                returns.mean(),
            "Median":
                returns.median(),
            "WinRate":
                (
                    (returns > 0).mean()
                    * 100
                ),
            "TotalReturn":
                returns.sum(),
            "TAKE":
                take_count,
            "STOP":
                stop_count,
            "CLOSE":
                close_count,
        })

    summary = pd.DataFrame(
        summary_rows
    )

    print(
        summary.to_string(
            index=False,
            formatters={
                "Threshold":
                    lambda x:
                    f"{x:+.1f}%",
                "MeanReturn":
                    lambda x:
                    f"{x:.2f}%"
                    if pd.notna(x)
                    else "",
                "Median":
                    lambda x:
                    f"{x:.2f}%"
                    if pd.notna(x)
                    else "",
                "WinRate":
                    lambda x:
                    f"{x:.1f}%"
                    if pd.notna(x)
                    else "",
                "TotalReturn":
                    lambda x:
                    f"{x:.2f}%"
                    if pd.notna(x)
                    else "",
            },
        )
    )

    # ============================================
    # 銘柄別
    # ============================================

    print()
    print("=" * 76)
    print("STOCK DETAIL")
    print("=" * 76)

    detail_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Change",
        "VolumeRatio",
        "CxV",
        "Close0931Pct",
        "Entry0932Price",
        "ExitType0932",
        "ReturnPct0932",
    ]

    detail = merged[
        detail_cols
    ].copy()

    detail = detail.sort_values(
        [
            "Close0931Pct",
            "ReturnPct0932",
        ],
        ascending=[
            False,
            False,
        ],
    )

    print(
        detail.to_string(
            index=False
        )
    )

    # ============================================
    # 各閾値を列として保存
    # ============================================

    for threshold in THRESHOLDS:

        label = str(
            abs(int(threshold))
        )

        if threshold == 0:
            col = "Pass_0"
        else:
            col = (
                f"Pass_Minus{label}"
            )

        merged[col] = (
            merged["Close0931Pct"]
            >= threshold
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    merged.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"Saved : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()