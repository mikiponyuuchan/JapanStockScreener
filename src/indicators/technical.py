import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    テクニカル指標を追加する
    """

    df = df.copy()


    # =====================
    # 移動平均線
    # =====================

    df["MA5"] = (
        df["Close"]
        .rolling(5)
        .mean()
        .round(2)
    )

    df["MA25"] = (
        df["Close"]
        .rolling(25)
        .mean()
        .round(2)
    )

    df["MA75"] = (
        df["Close"]
        .rolling(75)
        .mean()
        .round(2)
    )


    # =====================
    # 出来高
    # =====================

    df["VolumeMA5"] = (
        df["Volume"]
        .rolling(5)
        .mean()
        .round()
    )

    df["VolumeRatio"] = (
        df["Volume"] / df["VolumeMA5"]
    ).round(2)



    # =====================
    # 株価判定
    # =====================

    df["PriceUp"] = (
        df["Close"] > df["Close"].shift(1)
    )

    df["AboveMA5"] = (
        df["Close"] > df["MA5"]
    )

    df["AboveMA25"] = (
        df["Close"] > df["MA25"]
    )

    df["AboveMA75"] = (
        df["Close"] > df["MA75"]
    )



    # =====================
    # MACD
    # =====================

    ema12 = df["Close"].ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = df["Close"].ewm(
        span=26,
        adjust=False
    ).mean()


    df["MACD"] = ema12 - ema26


    df["Signal"] = (
        df["MACD"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )


    df["MACD_GC"] = (
        (df["MACD"] > df["Signal"])
        &
        (df["MACD"].shift(1) <= df["Signal"].shift(1))
    )



    # =====================
    # 30営業日高値
    # =====================

    high30 = (
        df["High"]
        .rolling(30)
        .max()
    )


    df["High30"] = (
        high30
        .round(2)
    )


    # 高値更新判定
    prev30high = (
        df["High"]
        .shift(1)
        .rolling(30)
        .max()
    )


    df["New30High"] = (
        df["High"] > prev30high
    )



    # =====================
    # 1.15 高値余地
    # =====================

    df["High30Distance"] = (
        (
            (df["High30"] - df["Close"])
            /
            df["Close"]
            *
            100
        )
        .round(2)
    )


    return df