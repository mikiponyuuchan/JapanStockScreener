import pandas as pd

from services.yahoo_service import get_history
from indicators.technical import add_indicators



def make_comment(latest):

    comments = []

    if latest["PriceUp"]:
        comments.append("株価上昇")

    if latest["AboveMA5"]:
        comments.append("5日線上")

    if latest["AboveMA25"]:
        comments.append("25日線上")

    if latest["AboveMA75"]:
        comments.append("75日線上")

    if latest["MACD_GC"]:
        comments.append("MACD GC")

    if latest["New30High"]:
        comments.append("30日高値更新")


    if pd.notna(latest["VolumeRatio"]):

        if latest["VolumeRatio"] >= 2:
            comments.append("出来高急増")


    if latest["PriceMovement"]:
        comments.append(
            latest["PriceMovement"]
        )


    if latest["ConsecutiveUpDays"] > 0:

        comments.append(
            f"{latest['ConsecutiveUpDays']}日連続上昇"
        )


    if latest["VolumeIncreaseDays"] > 0:

        comments.append(
            f"出来高{latest['VolumeIncreaseDays']}日増加"
        )


    return " / ".join(comments)



def calculate_score(latest):

    score = 0


    if latest["PriceUp"]:
        score += 1


    if latest["AboveMA5"]:
        score += 1


    if latest["AboveMA25"]:
        score += 2


    if latest["AboveMA75"]:
        score += 2


    if latest["MACD_GC"]:
        score += 2


    if latest["New30High"]:
        score += 2



    if pd.notna(latest["VolumeRatio"]):

        if latest["VolumeRatio"] >= 2:
            score += 1



    # 出来高増加継続ボーナス

    if latest["VolumeIncreaseDays"] >= 3:
        score += 1


    return score



def make_rank(score):

    if score >= 8:
        return "A"

    elif score >= 5:
        return "B"

    else:
        return "C"



def make_price_position(distance):

    if pd.isna(distance):
        return ""


    if distance <= 5:
        return "高値圏"


    elif distance <= 15:
        return "上昇中"


    else:
        return "上昇余地あり"



def make_trend(value):

    if value:
        return "強い"

    else:
        return "弱い"



def make_total_judgement(
        rank,
        score,
        short_trend,
        middle_trend,
        position):


    if (
        rank == "A"
        and score >= 8
        and short_trend == "強い"
        and middle_trend == "強い"
        and position != "高値圏"
    ):

        return "買い候補"


    elif rank in ["A", "B"]:

        return "監視継続"


    else:

        return "様子見"



def make_analysis_comment(
        latest,
        score,
        rank,
        position,
        short_trend,
        middle_trend,
        long_trend,
        judgement):


    comments = []


    comments.append(
        f"{rank}ランク"
    )


    comments.append(
        f"強気度{score}点"
    )


    comments.append(
        f"短期{short_trend}"
    )


    comments.append(
        f"中期{middle_trend}"
    )


    comments.append(
        f"長期{long_trend}"
    )


    if pd.notna(latest["ChangePercent"]):

        comments.append(
            f"前日比{latest['ChangePercent']}%"
        )


    if latest["PriceMovement"]:

        comments.append(
            latest["PriceMovement"]
        )


    if latest["ConsecutiveUpDays"] > 0:

        comments.append(
            f"{latest['ConsecutiveUpDays']}日連続上昇"
        )


    if latest["VolumeIncreaseDays"] > 0:

        comments.append(
            f"出来高{latest['VolumeIncreaseDays']}日増加"
        )


    if latest["MACD_GC"]:

        comments.append("MACD GC")


    if latest["New30High"]:

        comments.append("30日高値更新")


    if pd.notna(latest["VolumeRatio"]):

        if latest["VolumeRatio"] >= 2:

            comments.append(
                f"出来高{round(float(latest['VolumeRatio']),2)}倍"
            )


    if position:

        comments.append(position)


    comments.append(
        judgement
    )


    return " / ".join(comments)
def analyze_stock(stock):

    code = stock["コード"]


    df = get_history(code)


    if df is None or df.empty:

        return None



    df = add_indicators(df)


    latest = df.iloc[-1]



    score = calculate_score(latest)


    rank = make_rank(score)



    position = make_price_position(
        latest["High30Distance"]
    )



    short_trend = make_trend(
        latest["AboveMA5"]
    )


    middle_trend = make_trend(
        latest["AboveMA25"]
    )


    long_trend = make_trend(
        latest["AboveMA75"]
    )



    judgement = make_total_judgement(
        rank,
        score,
        short_trend,
        middle_trend,
        position
    )



    return {


        "コード": code,


        "銘柄名": stock["銘柄名"],


        "市場": stock["市場・商品区分"],



        "終値": (
            round(float(latest["Close"]),2)
        ),



        "前日終値": (

            round(float(latest["PreviousClose"]),2)

            if pd.notna(latest["PreviousClose"])

            else None

        ),



        "前日比": (

            round(float(latest["Change"]),2)

            if pd.notna(latest["Change"])

            else None

        ),



        "前日比%": (

            round(float(latest["ChangePercent"]),2)

            if pd.notna(latest["ChangePercent"])

            else None

        ),



        "値動き評価":

            latest["PriceMovement"],



        "連続上昇日数":

            int(latest["ConsecutiveUpDays"]),



        "出来高増加日数":

            int(latest["VolumeIncreaseDays"]),



        "30日高値": (

            round(float(latest["High30"]),2)

            if pd.notna(latest["High30"])

            else None

        ),



        "30日高値までの距離%": (

            round(float(latest["High30Distance"]),2)

            if pd.notna(latest["High30Distance"])

            else None

        ),



        "株価位置":

            position,



        "5日線": (

            round(float(latest["MA5"]),2)

            if pd.notna(latest["MA5"])

            else None

        ),



        "25日線": (

            round(float(latest["MA25"]),2)

            if pd.notna(latest["MA25"])

            else None

        ),



        "75日線": (

            round(float(latest["MA75"]),2)

            if pd.notna(latest["MA75"])

            else None

        ),



        "出来高":

            int(latest["Volume"]),



        "出来高倍率": (

            round(float(latest["VolumeRatio"]),2)

            if pd.notna(latest["VolumeRatio"])

            else None

        ),



        "株価上昇":

            "○" if latest["PriceUp"] else "",



        "5日線上":

            "○" if latest["AboveMA5"] else "",



        "25日線上":

            "○" if latest["AboveMA25"] else "",



        "75日線上":

            "○" if latest["AboveMA75"] else "",



        "短期トレンド":

            short_trend,


        "中期トレンド":

            middle_trend,


        "長期トレンド":

            long_trend,



        "MACD GC":

            "○" if latest["MACD_GC"] else "",



        "30日高値更新":

            "○" if latest["New30High"] else "",



        "注目ポイント":

            make_comment(latest),



        "強気度":

            score,



        "監視ランク":

            rank,



        "総合判定":

            judgement,



        "分析コメント":

            make_analysis_comment(
                latest,
                score,
                rank,
                position,
                short_trend,
                middle_trend,
                long_trend,
                judgement
            ),

    }