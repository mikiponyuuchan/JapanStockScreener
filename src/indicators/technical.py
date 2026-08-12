import pandas as pd
import numpy as np
import time


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    テクニカル指標を追加する
    Ver6.12

    Ver6.11までの判定ロジックを維持し、
    PythonループとDataFrame.apply(axis=1)を
    可能な範囲でベクトル演算へ変更。
    """

    start_time = time.time()

    df = df.copy()

    # =====================
    # 移動平均
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

    df["VolumeMA20"] = (
        df["Volume"]
        .rolling(20)
        .mean()
        .round()
    )

    df["VolumeRatio"] = (
        df["Volume"]
        / df["VolumeMA5"]
    ).round(2)

    df["VolumeRatio20"] = (
        df["Volume"]
        / df["VolumeMA20"]
    ).round(2)

    # =====================
    # 前日比
    # =====================

    previous_close = df["Close"].shift(1)

    df["PreviousClose"] = previous_close

    df["Change"] = (
        df["Close"]
        - previous_close
    ).round(2)

    df["ChangePercent"] = (
        df["Change"]
        / previous_close
        * 100
    ).round(2)

    # =====================
    # 騰落率
    # =====================

    close_5 = df["Close"].shift(5)
    close_20 = df["Close"].shift(20)

    df["Change5Days"] = (
        (
            df["Close"]
            - close_5
        )
        / close_5
        * 100
    ).round(2)

    df["Change20Days"] = (
        (
            df["Close"]
            - close_20
        )
        / close_20
        * 100
    ).round(2)

    # =====================
    # 株価位置
    # =====================

    df["PriceUp"] = (
        df["Close"] > previous_close
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
    # 連続上昇日数
    #
    # 元コードのPythonループと
    # 同じ結果になるように計算
    # =====================

    up_flag = (
        df["Close"] > previous_close
    )

    up_group = (
        (~up_flag)
        .cumsum()
    )

    df["ConsecutiveUpDays"] = (
        up_flag
        .groupby(up_group)
        .cumsum()
        .astype(int)
    )

    # =====================
    # 出来高増加日数
    # =====================

    volume_flag = (
        df["Volume"] > df["VolumeMA5"]
    )

    volume_group = (
        (~volume_flag)
        .cumsum()
    )

    df["VolumeIncreaseDays"] = (
        volume_flag
        .groupby(volume_group)
        .cumsum()
        .astype(int)
    )

    # =====================
    # MACD
    # =====================

    ema12 = (
        df["Close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["Close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = (
        ema12 - ema26
    )

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
        (
            df["MACD"].shift(1)
            <=
            df["Signal"].shift(1)
        )
    )

    # =====================
    # 30日高値
    # =====================

    df["High30"] = (
        df["High"]
        .rolling(30)
        .max()
        .round(2)
    )

    prev30high = (
        df["High"]
        .shift(1)
        .rolling(30)
        .max()
    )

    df["New30High"] = (
        df["High"] > prev30high
    )

    df["High30Distance"] = (
        (
            df["High30"]
            - df["Close"]
        )
        / df["Close"]
        * 100
    ).round(2)

    # =====================
    # 年初来高値
    # 250営業日
    # =====================

    df["YearHigh"] = (
        df["High"]
        .rolling(250)
        .max()
        .round(2)
    )

    df["NewYearHigh"] = (
        df["High"] >= df["YearHigh"]
    )

    # =====================
    # RSI 14日
    # =====================

    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = (
        gain
        .rolling(14)
        .mean()
    )

    avg_loss = (
        loss
        .rolling(14)
        .mean()
    )

    rs = avg_gain / avg_loss

    df["RSI"] = (
        100
        -
        (
            100
            /
            (1 + rs)
        )
    ).round(2)

    # =====================
    # ATR 14日
    # =====================

    high_low = (
        df["High"] - df["Low"]
    )

    high_close = (
        df["High"]
        - df["Close"].shift(1)
    ).abs()

    low_close = (
        df["Low"]
        - df["Close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    df["ATR"] = (
        true_range
        .rolling(14)
        .mean()
        .round(2)
    )

    # =====================
    # ブレイクアウト判定
    # =====================

    previous_high20 = (
        df["High"]
        .shift(1)
        .rolling(20)
        .max()
    )

    df["BreakoutSignal"] = (
        df["Close"] > previous_high20
    )

    # =====================
    # ブレイク初日
    # =====================

    previous_signal = (
        df["BreakoutSignal"]
        .shift(1)
        .fillna(False)
        .astype(bool)
    )

    df["BreakoutFirstDay"] = (
        df["BreakoutSignal"]
        &
        (~previous_signal)
    )

    # =====================
    # 値動き評価
    # =====================

    change = df["ChangePercent"]

    df["PriceMovement"] = np.select(
        [
            change >= 3,
            change >= 0.5,
            change >= -0.5
        ],
        [
            "急上昇",
            "上昇",
            "横ばい"
        ],
        default="下落"
    )

    df.loc[
        change.isna(),
        "PriceMovement"
    ] = ""

    # =====================
    # トレンド評価
    #
    # apply(axis=1)を廃止
    # =====================

    ma75_missing = df["MA75"].isna()

    strong_up = (
        (df["Close"] > df["MA5"])
        &
        (df["MA5"] > df["MA25"])
        &
        (df["MA25"] > df["MA75"])
    )

    up = (
        (df["Close"] > df["MA5"])
        &
        (df["MA5"] > df["MA25"])
    )

    middle = (
        df["Close"] > df["MA25"]
    )

    df["TrendEvaluation"] = np.select(
        [
            ma75_missing,
            strong_up,
            up,
            middle
        ],
        [
            "判定待ち",
            "強い上昇",
            "上昇継続",
            "中立"
        ],
        default="弱い"
    )

    # =====================
    # MA並び
    # =====================

    ma75_valid = ~df["MA75"].isna()

    ma_up = (
        (df["MA5"] > df["MA25"])
        &
        (df["MA25"] > df["MA75"])
    )

    ma_down = (
        (df["MA5"] < df["MA25"])
        &
        (df["MA25"] < df["MA75"])
    )

    df["MAAlignment"] = np.select(
        [
            ~ma75_valid,
            ma_up,
            ma_down
        ],
        [
            "",
            "上昇配列",
            "下降配列"
        ],
        default="混在"
    )

    # =====================
    # 25日乖離率
    # =====================

    df["MA25Deviation"] = (
        (
            df["Close"]
            - df["MA25"]
        )
        / df["MA25"]
        * 100
    ).round(2)

    # =====================
    # MA収束度
    # =====================

    df["MAConvergence"] = (
        (
            df["MA5"]
            - df["MA25"]
        ).abs()
        / df["MA25"]
        * 100
    ).round(2)

    # =====================
    # 初動シグナル
    # =====================

    df["InitialMoveSignal"] = (
        (df["Close"] > df["MA5"])
        &
        (df["MA5"] > df["MA25"])
        &
        (df["Change5Days"] > 0)
        &
        (df["MA25Deviation"] < 15)
    )

    # =====================
    # 押し目判定
    # =====================

    trend_ok = (
        df["TrendEvaluation"]
        .isin(
            [
                "強い上昇",
                "上昇継続"
            ]
        )
    )

    df["PullbackSignal"] = (
        trend_ok
        &
        (df["Close"] <= df["MA5"] * 1.02)
        &
        (df["Close"] >= df["MA25"])
    )

    # =====================
    # RSI判定
    # =====================

    df["RSI_Strong"] = (
        (df["RSI"] >= 50)
        &
        (df["RSI"] <= 70)
    )

    df["RSI_OverBought"] = (
        df["RSI"] >= 80
    )

    return df

