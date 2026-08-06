import pandas as pd
import numpy as np
import time

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    テクニカル指標を追加する
    Ver3.0
    """

    start_time = time.time()

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


    df["VolumeMA20"] = (
        df["Volume"]
        .rolling(20)
        .mean()
        .round()
    )


    df["VolumeRatio"] = (
        df["Volume"]
        /
        df["VolumeMA5"]
    ).round(2)


    df["VolumeRatio20"] = (
        df["Volume"]
        /
        df["VolumeMA20"]
    ).round(2)


    # =====================
    # 前日比
    # =====================

    df["PreviousClose"] = (
        df["Close"]
        .shift(1)
    )


    df["Change"] = (
        df["Close"]
        -
        df["PreviousClose"]
    ).round(2)


    df["ChangePercent"] = (
        df["Change"]
        /
        df["PreviousClose"]
        *
        100
    ).round(2)


    # =====================
    # 騰落率
    # =====================

    df["Change5Days"] = (
        (
            df["Close"]
            -
            df["Close"].shift(5)
        )
        /
        df["Close"].shift(5)
        *
        100
    ).round(2)


    df["Change20Days"] = (
        (
            df["Close"]
            -
            df["Close"].shift(20)
        )
        /
        df["Close"].shift(20)
        *
        100
    ).round(2)


    # =====================
    # 株価位置
    # =====================

    df["PriceUp"] = (
        df["Close"]
        >
        df["Close"].shift(1)
    )


    df["AboveMA5"] = (
        df["Close"]
        >
        df["MA5"]
    )


    df["AboveMA25"] = (
        df["Close"]
        >
        df["MA25"]
    )


    df["AboveMA75"] = (
        df["Close"]
        >
        df["MA75"]
    )


    # =====================
    # 連続上昇日数
    # =====================

    up_flag = (
        df["Close"]
        >
        df["Close"].shift(1)
    )


    count = []

    current = 0


    for value in up_flag:

        if value:
            current += 1

        else:
            current = 0

        count.append(current)


    df["ConsecutiveUpDays"] = count


    # =====================
    # 出来高増加日数
    # =====================

    volume_flag = (
        df["Volume"]
        >
        df["VolumeMA5"]
    )


    volume_count = []

    current = 0


    for value in volume_flag:

        if value:
            current += 1

        else:
            current = 0

        volume_count.append(current)


    df["VolumeIncreaseDays"] = volume_count
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
        ema12
        -
        ema26
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
        (df["MACD"].shift(1)
         <=
         df["Signal"].shift(1))
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
        df["High"]
        >
        prev30high
    )


    df["High30Distance"] = (
        (
            df["High30"]
            -
            df["Close"]
        )
        /
        df["Close"]
        *
        100
    ).round(2)



    # =====================
    # 年初来高値（250営業日）
    # =====================

    df["YearHigh"] = (
        df["High"]
        .rolling(250)
        .max()
        .round(2)
    )


    df["NewYearHigh"] = (
        df["High"]
        >=
        df["YearHigh"]
    )



    # =====================
    # RSI 14日
    # =====================

    delta = (
        df["Close"]
        .diff()
    )


    gain = (
        delta
        .clip(lower=0)
    )


    loss = (
        -delta
        .clip(upper=0)
    )


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


    rs = (
        avg_gain
        /
        avg_loss
    )


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
    # ATR（14日）
    # =====================

    high_low = (
        df["High"]
        -
        df["Low"]
    )


    high_close = (
        abs(
            df["High"]
            -
            df["Close"].shift(1)
        )
    )


    low_close = (
        abs(
            df["Low"]
            -
            df["Close"].shift(1)
        )
    )


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
        df["Close"]
        >
        previous_high20
    )



    # =====================
    # ブレイク初日
    # =====================

    df["BreakoutFirstDay"] = (
        df["BreakoutSignal"]
        &
        (
            ~df["BreakoutSignal"]
            .shift(1)
            .fillna(False)
        )
    )
        # =====================
    # 値動き評価
    # =====================

    def judge_price_change(value):

        if pd.isna(value):

            return ""


        if value >= 3:

            return "急上昇"


        elif value >= 0.5:

            return "上昇"


        elif value >= -0.5:

            return "横ばい"


        else:

            return "下落"



    df["PriceMovement"] = (
        df["ChangePercent"]
        .apply(judge_price_change)
    )



    # =====================
    # トレンド評価
    # =====================

    def judge_trend(row):

        if pd.isna(row["MA75"]):

            return "判定待ち"



        if (
            row["Close"] > row["MA5"]
            and
            row["MA5"] > row["MA25"]
            and
            row["MA25"] > row["MA75"]
        ):

            return "強い上昇"



        elif (
            row["Close"] > row["MA5"]
            and
            row["MA5"] > row["MA25"]
        ):

            return "上昇継続"



        elif row["Close"] > row["MA25"]:

            return "中立"



        else:

            return "弱い"



    df["TrendEvaluation"] = (
        df.apply(
            judge_trend,
            axis=1
        )
    )



    # =====================
    # MA並び
    # =====================

    def make_ma_alignment(row):

        if pd.isna(row["MA75"]):

            return ""


        if (
            row["MA5"]
            >
            row["MA25"]
            >
            row["MA75"]
        ):

            return "上昇配列"


        elif (
            row["MA5"]
            <
            row["MA25"]
            <
            row["MA75"]
        ):

            return "下降配列"


        else:

            return "混在"



    df["MAAlignment"] = (
        df.apply(
            make_ma_alignment,
            axis=1
        )
    )



    # =====================
    # 25日線乖離率
    # =====================

    df["MA25Deviation"] = (
        (
            df["Close"]
            -
            df["MA25"]
        )
        /
        df["MA25"]
        *
        100
    ).round(2)



    # =====================
    # MA収束度
    # =====================

    df["MAConvergence"] = (
        abs(
            df["MA5"]
            -
            df["MA25"]
        )
        /
        df["MA25"]
        *
        100
    ).round(2)



    # =====================
    # 初動シグナル Ver3
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
    # 押し目判定 Ver3
    # =====================

    df["PullbackSignal"] = (

        df["TrendEvaluation"]
        .isin(
            [
                "強い上昇",
                "上昇継続"
            ]
        )

        &

        (
            df["Close"]
            <=
            df["MA5"] * 1.02
        )

        &

        (
            df["Close"]
            >=
            df["MA25"]
        )

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



    # =====================
    # return
    # =====================



    return df