import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    テクニカル指標を追加する
    """

    df = df.copy()

    # 5日移動平均
    df["MA5"] = df["Close"].rolling(5).mean().round(2)

    # 25日移動平均
    df["MA25"] = df["Close"].rolling(25).mean().round(2)

    # 5日平均出来高
    df["VolumeMA5"] = (
        df["Volume"]
        .rolling(5)
        .mean()
        .round()
        .astype("Int64")
    )

    # 出来高倍率
    df["VolumeRatio"] = (
        df["Volume"] / df["VolumeMA5"]
    ).round(2)

    # 前日比で株価上昇
    df["PriceUp"] = (
        df["Close"] > df["Close"].shift(1)
    )

    # 5MAより上
    df["AboveMA5"] = (
        df["Close"] > df["MA5"]
    )

    return df