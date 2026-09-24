from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_0931_filter.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_0931_band_sensitivity.csv"
)

LOWER_LIMITS = [
    -4.0,
    -3.5,
    -3.0,
    -2.5,
    -2.0,
]

UPPER_LIMITS = [
    0.0,
    0.5,
    1.0,
    1.5,
    2.0,
]

CURRENT_LOWER = -3.0
CURRENT_UPPER = 1.0


def main():
    print(
        "=" * 88
    )
    print(
        "H1 09:31 BAND SENSITIVITY -> 09:32 ENTRY"
    )
    print(
        "=" * 88
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

    print(
        "Entry       : 09:32 OPEN"
    )
    print(
        "Take profit : +10%"
    )
    print(
        "Stop loss   : -3%"
    )

    summaries = []
    detail_frames = []

    for lower in LOWER_LIMITS:
        for upper in UPPER_LIMITS:

            # Upper side is exclusive.
            # Current H1:
            # -3.0 <= Close0931Pct < +1.0
            mask = (
                (
                    usable["Close0931Pct"]
                    >= lower
                )
                & (
                    usable["Close0931Pct"]
                    < upper
                )
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

            is_current = (
                lower == CURRENT_LOWER
                and upper == CURRENT_UPPER
            )

            summaries.append(
                {
                    "LowerLimit": lower,
                    "UpperLimit": upper,
                    "CurrentH1": (
                        "YES"
                        if is_current
                        else ""
                    ),
                    "Trades": len(
                        selected
                    ),
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
                upper,
            )

            detail.insert(
                0,
                "LowerLimit",
                lower,
            )

            detail.insert(
                0,
                "CurrentH1",
                (
                    "YES"
                    if is_current
                    else ""
                ),
            )

            detail_frames.append(
                detail
            )

    summary_df = pd.DataFrame(
        summaries
    )

    print()
    print(
        "=" * 88
    )
    print(
        "25 BAND COMPARISON"
    )
    print(
        "=" * 88
    )

    if summary_df.empty:
        print(
            "No comparison rows."
        )
        return

    display = summary_df.copy()

    display["LowerLimit"] = (
        display["LowerLimit"]
        .map(
            lambda x:
            f"{x:+.1f}%"
        )
    )

    display["UpperLimit"] = (
        display["UpperLimit"]
        .map(
            lambda x:
            f"{x:+.1f}%"
        )
    )

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
    # Mean return matrix
    # ============================================

    print()
    print(
        "=" * 88
    )
    print(
        "MEAN RETURN MATRIX"
    )
    print(
        "=" * 88
    )

    mean_matrix = (
        summary_df.pivot(
            index="LowerLimit",
            columns="UpperLimit",
            values="MeanReturn",
        )
        .sort_index()
    )

    mean_display = (
        mean_matrix.map(
            lambda x:
            (
                f"{x:.2f}%"
                if pd.notna(x)
                else ""
            )
        )
    )

    print(
        mean_display.to_string()
    )

    # ============================================
    # Trade count matrix
    # ============================================

    print()
    print(
        "=" * 88
    )
    print(
        "TRADE COUNT MATRIX"
    )
    print(
        "=" * 88
    )

    trade_matrix = (
        summary_df.pivot(
            index="LowerLimit",
            columns="UpperLimit",
            values="Trades",
        )
        .sort_index()
    )

    print(
        trade_matrix.to_string()
    )

    # ============================================
    # Current H1 and neighbors
    # ============================================

    print()
    print(
        "=" * 88
    )
    print(
        "CURRENT H1"
    )
    print(
        "=" * 88
    )

    current = summary_df[
        (
            summary_df["LowerLimit"]
            == CURRENT_LOWER
        )
        & (
            summary_df["UpperLimit"]
            == CURRENT_UPPER
        )
    ]

    if not current.empty:
        current_display = (
            current.copy()
        )

        current_display[
            "MeanReturn"
        ] = (
            current_display[
                "MeanReturn"
            ].map(
                lambda x:
                f"{x:.2f}%"
            )
        )

        current_display[
            "Median"
        ] = (
            current_display[
                "Median"
            ].map(
                lambda x:
                f"{x:.2f}%"
            )
        )

        current_display[
            "WinRate"
        ] = (
            current_display[
                "WinRate"
            ].map(
                lambda x:
                f"{x:.1f}%"
            )
        )

        current_display[
            "TotalReturn"
        ] = (
            current_display[
                "TotalReturn"
            ].map(
                lambda x:
                f"{x:.2f}%"
            )
        )

        print(
            current_display.to_string(
                index=False
            )
        )

    # ============================================
    # Save
    # ============================================

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_path = (
        OUTPUT_PATH.parent
        / (
            OUTPUT_PATH.stem
            + "_summary.csv"
        )
    )

    summary_df.to_csv(
        summary_path,
        index=False,
        encoding="utf-8-sig",
    )

    if detail_frames:
        detail_df = pd.concat(
            detail_frames,
            ignore_index=True,
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
    print(
        f"Saved : {summary_path}"
    )


if __name__ == "__main__":
    main()