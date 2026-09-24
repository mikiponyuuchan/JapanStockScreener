from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_0931_signal.csv"
)

FILTER_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_0931_filter.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_0931_candle.csv"
)

LOWER_LIMIT = -3.0
UPPER_LIMIT = 5.0


def print_result(title, df):
    print()
    print(
        "=" * 76
    )
    print(title)
    print(
        "=" * 76
    )

    if df.empty:
        print("No rows")
        return

    ret = pd.to_numeric(
        df["ReturnPct0932"],
        errors="coerce",
    ).dropna()

    if ret.empty:
        print("No valid returns")
        return

    exits = (
        df["ExitType0932"]
        .astype(str)
        .str.upper()
        .value_counts()
    )

    print(
        f"Trades      : {len(ret)}"
    )
    print(
        f"Mean return : {ret.mean():.2f}%"
    )
    print(
        f"Median      : {ret.median():.2f}%"
    )
    print(
        f"Win rate    : "
        f"{ret.gt(0).mean() * 100:.1f}%"
    )
    print(
        f"Total return: {ret.sum():.2f}%"
    )
    print(
        "TAKE / STOP / CLOSE : "
        f"{int(exits.get('TAKE', 0))} / "
        f"{int(exits.get('STOP', 0))} / "
        f"{int(exits.get('CLOSE', 0))}"
    )


def main():
    print(
        "=" * 76
    )
    print(
        "H1 09:31 CANDLE ANALYSIS"
    )
    print(
        "=" * 76
    )

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input not found : {INPUT_PATH}"
        )

    if not FILTER_PATH.exists():
        raise FileNotFoundError(
            f"Input not found : {FILTER_PATH}"
        )

    signal = pd.read_csv(
        INPUT_PATH,
        low_memory=False,
        dtype={
            "Code": str,
        },
    )

    result = pd.read_csv(
        FILTER_PATH,
        low_memory=False,
        dtype={
            "Code": str,
        },
    )

    signal["DetectionDate"] = (
        signal["DetectionDate"]
        .astype(str)
    )

    result["DetectionDate"] = (
        result["DetectionDate"]
        .astype(str)
    )

    signal["Code"] = (
        signal["Code"]
        .astype(str)
        .str.strip()
    )

    result["Code"] = (
        result["Code"]
        .astype(str)
        .str.strip()
    )

    signal_cols = [
        "DetectionDate",
        "Code",
        "Open0931Pct",
        "High0931Pct",
        "Low0931Pct",
        "Close0931Pct",
        "Body0931Pct",
    ]

    missing_signal = [
        col
        for col in signal_cols
        if col not in signal.columns
    ]

    if missing_signal:
        raise ValueError(
            "Missing signal columns : "
            + ", ".join(missing_signal)
        )

    result_cols = [
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

    missing_result = [
        col
        for col in result_cols
        if col not in result.columns
    ]

    if missing_result:
        raise ValueError(
            "Missing result columns : "
            + ", ".join(missing_result)
        )

    # Close0931Pct は signal 側を使用するため、
    # result 側では重複を避ける。
    result_base = result[
        [
            col
            for col in result_cols
            if col != "Close0931Pct"
        ]
    ].copy()

    df = result_base.merge(
        signal[signal_cols],
        on=[
            "DetectionDate",
            "Code",
        ],
        how="inner",
    )

    numeric_cols = [
        "Rank",
        "Change",
        "VolumeRatio",
        "CxV",
        "Entry0932Price",
        "ReturnPct0932",
        "Open0931Pct",
        "High0931Pct",
        "Low0931Pct",
        "Close0931Pct",
        "Body0931Pct",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df[
        df["Close0931Pct"].notna()
        & df["Open0931Pct"].notna()
        & df["High0931Pct"].notna()
        & df["Low0931Pct"].notna()
        & df["ReturnPct0932"].notna()
    ].copy()

    # ============================================
    # 有力バンド
    # -3% <= 09:31終値 <= +5%
    # ============================================

    df = df[
        (
            df["Close0931Pct"]
            >= LOWER_LIMIT
        )
        & (
            df["Close0931Pct"]
            <= UPPER_LIMIT
        )
    ].copy()

    print(
        f"Band        : "
        f"{LOWER_LIMIT:+.1f}% "
        f"to {UPPER_LIMIT:+.1f}%"
    )
    print(
        f"Usable rows : {len(df)}"
    )

    # ============================================
    # ローソク足分類
    # ============================================

    df["CandleType"] = "FLAT"

    df.loc[
        df["Close0931Pct"]
        > df["Open0931Pct"],
        "CandleType",
    ] = "BULL"

    df.loc[
        df["Close0931Pct"]
        < df["Open0931Pct"],
        "CandleType",
    ] = "BEAR"

    # 09:31足の値幅
    df["Range0931Pct"] = (
        df["High0931Pct"]
        - df["Low0931Pct"]
    )

    # 安値から終値まで何％ポイント戻したか
    df["RecoveryFromLowPct"] = (
        df["Close0931Pct"]
        - df["Low0931Pct"]
    )

    # ローソク足レンジ内の終値位置
    #
    # 0   = 安値引け
    # 0.5 = 値幅中央
    # 1   = 高値引け
    df["ClosePosition"] = pd.NA

    valid_range = (
        df["Range0931Pct"] > 0
    )

    df.loc[
        valid_range,
        "ClosePosition",
    ] = (
        (
            df.loc[
                valid_range,
                "Close0931Pct",
            ]
            - df.loc[
                valid_range,
                "Low0931Pct",
            ]
        )
        / df.loc[
            valid_range,
            "Range0931Pct",
        ]
    )

    df["ClosePosition"] = pd.to_numeric(
        df["ClosePosition"],
        errors="coerce",
    )

    # ============================================
    # 全体
    # ============================================

    print_result(
        "BAND ALL",
        df,
    )

    # ============================================
    # 陽線 / 陰線 / 同値
    # ============================================

    for candle in [
        "BULL",
        "BEAR",
        "FLAT",
    ]:
        print_result(
            f"CANDLE = {candle}",
            df[
                df["CandleType"]
                == candle
            ],
        )

    # ============================================
    # 安値からの戻り幅
    # ============================================

    recovery_thresholds = [
        0.0,
        0.25,
        0.5,
        1.0,
        2.0,
    ]

    print()
    print(
        "=" * 76
    )
    print(
        "RECOVERY FROM LOW"
    )
    print(
        "=" * 76
    )

    rows = []

    for threshold in recovery_thresholds:
        x = df[
            df["RecoveryFromLowPct"]
            >= threshold
        ].copy()

        if x.empty:
            continue

        ret = x[
            "ReturnPct0932"
        ]

        exits = (
            x["ExitType0932"]
            .astype(str)
            .str.upper()
            .value_counts()
        )

        rows.append(
            {
                "RecoveryMin":
                    threshold,
                "Trades":
                    len(x),
                "MeanReturn":
                    ret.mean(),
                "Median":
                    ret.median(),
                "WinRate":
                    ret.gt(0).mean() * 100,
                "TotalReturn":
                    ret.sum(),
                "TAKE":
                    int(
                        exits.get(
                            "TAKE",
                            0,
                        )
                    ),
                "STOP":
                    int(
                        exits.get(
                            "STOP",
                            0,
                        )
                    ),
                "CLOSE":
                    int(
                        exits.get(
                            "CLOSE",
                            0,
                        )
                    ),
            }
        )

    recovery_df = pd.DataFrame(
        rows
    )

    if not recovery_df.empty:
        display = recovery_df.copy()

        display["RecoveryMin"] = (
            display["RecoveryMin"]
            .map(
                lambda x:
                f"{x:.2f}%"
            )
        )

        for col in [
            "MeanReturn",
            "Median",
            "WinRate",
            "TotalReturn",
        ]:
            display[col] = (
                display[col]
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
    # 終値位置
    # ============================================

    position_thresholds = [
        0.25,
        0.50,
        0.75,
    ]

    print()
    print(
        "=" * 76
    )
    print(
        "CLOSE POSITION IN 09:31 RANGE"
    )
    print(
        "=" * 76
    )

    rows = []

    for threshold in position_thresholds:
        x = df[
            df["ClosePosition"]
            >= threshold
        ].copy()

        if x.empty:
            continue

        ret = x[
            "ReturnPct0932"
        ]

        exits = (
            x["ExitType0932"]
            .astype(str)
            .str.upper()
            .value_counts()
        )

        rows.append(
            {
                "ClosePositionMin":
                    threshold,
                "Trades":
                    len(x),
                "MeanReturn":
                    ret.mean(),
                "Median":
                    ret.median(),
                "WinRate":
                    ret.gt(0).mean() * 100,
                "TotalReturn":
                    ret.sum(),
                "TAKE":
                    int(
                        exits.get(
                            "TAKE",
                            0,
                        )
                    ),
                "STOP":
                    int(
                        exits.get(
                            "STOP",
                            0,
                        )
                    ),
                "CLOSE":
                    int(
                        exits.get(
                            "CLOSE",
                            0,
                        )
                    ),
            }
        )

    position_df = pd.DataFrame(
        rows
    )

    if not position_df.empty:
        display = position_df.copy()

        display[
            "ClosePositionMin"
        ] = (
            display[
                "ClosePositionMin"
            ]
            .map(
                lambda x:
                f"{x:.2f}"
            )
        )

        for col in [
            "MeanReturn",
            "Median",
            "WinRate",
            "TotalReturn",
        ]:
            display[col] = (
                display[col]
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
    # 銘柄明細
    # ============================================

    print()
    print(
        "=" * 76
    )
    print(
        "STOCK DETAIL"
    )
    print(
        "=" * 76
    )

    detail_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Change",
        "CxV",
        "Open0931Pct",
        "High0931Pct",
        "Low0931Pct",
        "Close0931Pct",
        "CandleType",
        "RecoveryFromLowPct",
        "ClosePosition",
        "ExitType0932",
        "ReturnPct0932",
    ]

    print(
        df[
            detail_cols
        ]
        .sort_values(
            "ReturnPct0932",
            ascending=False,
        )
        .to_string(
            index=False
        )
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
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