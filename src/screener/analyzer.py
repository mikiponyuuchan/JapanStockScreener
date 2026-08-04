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

    return score



def make_rank(score):

    if score >= 8:
        return "A"

    elif score >= 5:
        return "B"

    else:
        return "C"



def make_price_position(distance):
    """
    株価位置判定
    """

    if pd.isna(distance):
        return ""

    if distance <= 5:
        return "高値圏"

    elif distance <= 15:
        return "上昇中"

    else:
        return "上昇余地あり"



def make_analysis_comment(latest, score, rank, position):

    comments = []

    comments.append(f"{rank}ランク")
    comments.append(f"強気度{score}点")

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
            comments.append(
                f"出来高{round(float(latest['VolumeRatio']),2)}倍"
            )

    if position:
        comments.append(position)

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


    return {

        "コード": code,

        "銘柄名": stock["銘柄名"],

        "市場": stock["市場・商品区分"],


        "終値": round(float(latest["Close"]), 2),


        "30日高値": (
            round(float(latest["High30"]), 2)
            if pd.notna(latest["High30"])
            else None
        ),


        "30日高値までの距離%": (
            round(float(latest["High30Distance"]), 2)
            if pd.notna(latest["High30Distance"])
            else None
        ),


        "株価位置": position,


        "5日線": (
            round(float(latest["MA5"]), 2)
            if pd.notna(latest["MA5"])
            else None
        ),

        "25日線": (
            round(float(latest["MA25"]), 2)
            if pd.notna(latest["MA25"])
            else None
        ),

        "75日線": (
            round(float(latest["MA75"]), 2)
            if pd.notna(latest["MA75"])
            else None
        ),


        "出来高": int(latest["Volume"]),

        "出来高倍率": (
            round(float(latest["VolumeRatio"]), 2)
            if pd.notna(latest["VolumeRatio"])
            else None
        ),


        "株価上昇": "○" if latest["PriceUp"] else "",

        "5日線上": "○" if latest["AboveMA5"] else "",

        "25日線上": "○" if latest["AboveMA25"] else "",

        "75日線上": "○" if latest["AboveMA75"] else "",


        "MACD GC": "○" if latest["MACD_GC"] else "",

        "30日高値更新": "○" if latest["New30High"] else "",


        "注目ポイント": make_comment(latest),

        "強気度": score,

        "監視ランク": rank,


        "分析コメント": make_analysis_comment(
            latest,
            score,
            rank,
            position
        ),
    }