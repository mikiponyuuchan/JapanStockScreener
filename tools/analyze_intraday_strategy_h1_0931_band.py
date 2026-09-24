from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_0931_filter.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_0931_band.csv"
)

LOWER_LIMIT = -3.0

UPPER_LIMITS = [
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
    8.0,
    10.0,
    None,
]


def fmt_upper(value):
    if value is None:
        return "NONE"

    return f"+{value:.1f}%"


def main():
    print(
        "=" * 76
    )
    print(
        "H1 09:31 BAND FILTER -> 09:32 ENTRY"
    )
    print(
        "=" * 76
    )

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input not found : {INPUT_PATH}"
        )

    df = pd.read_csv(
        INPUT_PATH,
        low_memory=False,
    )

    required = [
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

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing columns : "
            + ", ".join(missing)
        )

    numeric_cols = [
        "Rank",
        "Change",
        "VolumeRatio",
        "CxV",
        "Close0931Pct",
        "Entry0932Price",
        "ReturnPct0932",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    usable = df[
        df["Close0931Pct"].notna()
        & df["Entry0932Price"].notna()
        & df["ReturnPct0932"].notna()
    ].copy()

    print(
        f"Usable rows : {len(usable)}"
    )

    print()
    print(
        f"Lower limit : {LOWER_LIMIT:+.1f}%"
    )
    print(
        "Entry       : 09:32"
    )

    summaries = []
    detail_frames = []

    for upper in UPPER_LIMITS:
        mask = (
            usable["Close0931Pct"]
            >= LOWER_LIMIT
        )

        if upper is not None:
            mask &= (
                usable["Close0931Pct"]
                <= upper
            )

        selected = usable[
            mask
        ].copy()

        if selected.empty:
            continue

        returns = selected[
            "ReturnPct0932"
        ]

        exit_counts = (
            selected["ExitType0932"]
            .astype(str)
            .str.upper()
            .value_counts()
        )

        take_count = int(
            exit_counts.get(
                "TAKE",
                0,
            )
        )

        stop_count = int(
            exit_counts.get(
                "STOP",
                0,
            )
        )

        close_count = int(
            exit_counts.get(
                "CLOSE",
                0,
            )
        )

        label = fmt_upper(
            upper
        )

        summaries.append(
            {
                "UpperLimit": label,
                "Trades": len(selected),
                "MeanReturn":
                    returns.mean(),
                "Median":
                    returns.median(),
                "WinRate":
                    (
                        returns.gt(0).mean()
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
            }
        )

        detail = selected[
            [
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
        ].copy()

        detail.insert(
            0,
            "UpperLimit",
            label,
        )

        detail_frames.append(
            detail
        )

    summary_df = pd.DataFrame(
        summaries
    )

    print()
    print(
        "=" * 76
    )
    print(
        "UPPER LIMIT COMPARISON"
    )
    print(
        "=" * 76
    )

    if summary_df.empty:
        print(
            "No comparison rows."
        )
        return

    display = summary_df.copy()

    display["MeanReturn"] = (
        display["MeanReturn"]
        .map(
            lambda x:
            f"{x:.2f}%"
        )
    )

    display["Median"] = (
        display["Median"]
        .map(
            lambda x:
            f"{x:.2f}%"
        )
    )

    display["WinRate"] = (
        display["WinRate"]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    display["TotalReturn"] = (
        display["TotalReturn"]
        .map(
            lambda x:
            f"{x:.2f}%"
        )
    )

    print(
        display.to_string(
            index=False
        )
    )

    # ============================================
    # 上限超過銘柄
    # ============================================

    base = usable[
        usable["Close0931Pct"]
        >= LOWER_LIMIT
    ].copy()

    print()
    print(
        "=" * 76
    )
    print(
        "STOCKS ABOVE EACH UPPER LIMIT"
    )
    print(
        "=" * 76
    )

    for upper in UPPER_LIMITS:
        if upper is None:
            continue

        excluded = base[
            base["Close0931Pct"]
            > upper
        ].copy()

        print()
        print(
            f"[Upper {upper:+.1f}%]"
        )
        print(
            f"Excluded : {len(excluded)}"
        )

        if excluded.empty:
            print(
                "None"
            )
            continue

        cols = [
            "DetectionDate",
            "Code",
            "Name",
            "Rank",
            "Change",
            "CxV",
            "Close0931Pct",
            "ExitType0932",
            "ReturnPct0932",
        ]

        excluded = excluded.sort_values(
            "Close0931Pct",
            ascending=False,
        )

        print(
            excluded[
                cols
            ].to_string(
                index=False
            )
        )

    # ============================================
    # CSV保存
    # ============================================

    if detail_frames:
        detail_df = pd.concat(
            detail_frames,
            ignore_index=True,
        )

        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        detail_df.to_csv(
            OUTPUT_PATH,
            index=False,
            encoding="utf-8-sig",
        )

        print()
        print(
            f"Saved : {OUTPUT_PATH}"
        )


if __name__ == "__main__":
    main()