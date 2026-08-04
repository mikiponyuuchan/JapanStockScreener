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
        df["Volume"]
        /
        df["VolumeMA5"]
    ).round(2)



    # =====================
    # 前日比
    # =====================

    df["PreviousClose"] = (
        df["Close"]
        .shift(1)
        .round(2)
    )


    df["Change"] = (
        df["Close"]
        -
        df["PreviousClose"]
    ).round(2)


    df["ChangePercent"] = (
        (
            df["Change"]
            /
            df["PreviousClose"]
            *
            100
        )
        .round(2)
    )




    # =====================
    # 1.26 騰落率
    # =====================

    df["Change5Days"] = (
        (
            (
                df["Close"]
                -
                df["Close"].shift(5)
            )
            /
            df["Close"].shift(5)
            *
            100
        )
        .round(2)
    )


    df["Change20Days"] = (
        (
            (
                df["Close"]
                -
                df["Close"].shift(20)
            )
            /
            df["Close"].shift(20)
            *
            100
        )
        .round(2)
    )




    # =====================
    # 株価判定
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




    # =====================
    # 高値余地
    # =====================

    df["High30Distance"] = (
        (
            (
                df["High30"]
                -
                df["Close"]
            )
            /
            df["Close"]
            *
            100
        )
        .round(2)
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



    return df