import pandas as pd

from services.yahoo_service import get_history
from indicators.technical import add_indicators



# ==========================
# 注目ポイント
# ==========================

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



    if latest["TrendEvaluation"]:

        comments.append(
            latest["TrendEvaluation"]
        )



    if latest["MAAlignment"]:

        comments.append(
            latest["MAAlignment"]
        )



    if latest["Change5Days"] >= 5:

        comments.append(
            f"5日上昇{latest['Change5Days']}%"
        )


    if latest["Change20Days"] >= 10:

        comments.append(
            f"20日上昇{latest['Change20Days']}%"
        )



    if latest["ConsecutiveUpDays"] > 0:

        comments.append(
            f"{latest['ConsecutiveUpDays']}日連続上昇"
        )



    return " / ".join(comments)





# ==========================
# スコア計算
# ==========================

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


    if latest["VolumeRatio"] >= 2:

        score += 1


    if latest["VolumeIncreaseDays"] >= 3:

        score += 1


    if latest["ConsecutiveUpDays"] >= 3:

        score += 1


    if latest["Change5Days"] >= 5:

        score += 1


    if latest["Change20Days"] >= 10:

        score += 1



    # Ver1.27 トレンド加点

    if latest["TrendEvaluation"] == "強い上昇":

        score += 2


    elif latest["TrendEvaluation"] == "上昇継続":

        score += 1



    return score





# ==========================
# ランク
# ==========================

def make_rank(score):

    if score >= 12:

        return "A"


    elif score >= 6:

        return "B"


    else:

        return "C"





# ==========================
# 株価位置
# ==========================

def make_price_position(distance):

    if pd.isna(distance):

        return ""


    if distance <= 5:

        return "高値圏"


    elif distance <= 15:

        return "上昇中"


    else:

        return "上昇余地あり"





# ==========================
# トレンド
# ==========================

def make_trend(value):

    if value:

        return "強い"

    else:

        return "弱い"





# ==========================
# 総合判定
# ==========================

def make_total_judgement(
        rank,
        score,
        short_trend,
        middle_trend,
        position):


    if (
        rank == "A"
        and score >= 10
        and short_trend == "強い"
        and middle_trend == "強い"
        and position != "高値圏"
    ):

        return "買い候補"



    elif rank in ["A", "B"]:

        return "監視継続"



    else:

        return "様子見"
    # ==========================
# 買い候補理由
# ==========================

def make_buy_reason(
        latest,
        score,
        rank,
        position,
        judgement):


    if judgement != "買い候補":

        return ""



    reasons = []


    reasons.append(
        f"{rank}ランク 強気度{score}点"
    )



    if latest["TrendEvaluation"]:

        reasons.append(
            latest["TrendEvaluation"]
        )



    if latest["MAAlignment"]:

        reasons.append(
            latest["MAAlignment"]
        )



    if latest["MACD_GC"]:

        reasons.append(
            "MACDゴールデンクロス"
        )



    if latest["New30High"]:

        reasons.append(
            "30日高値更新"
        )



    if latest["VolumeRatio"] >= 2:

        reasons.append(
            f"出来高{latest['VolumeRatio']}倍"
        )



    if latest["Change5Days"] >= 5:

        reasons.append(
            f"5日上昇{latest['Change5Days']}%"
        )



    if latest["Change20Days"] >= 10:

        reasons.append(
            f"20日上昇{latest['Change20Days']}%"
        )



    if latest["ConsecutiveUpDays"] >= 3:

        reasons.append(
            f"{latest['ConsecutiveUpDays']}日連続上昇"
        )



    if position:

        reasons.append(
            f"株価位置:{position}"
        )



    return " / ".join(reasons)





# ==========================
# 分析コメント
# ==========================

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
        latest["TrendEvaluation"]
    )


    comments.append(
        latest["MAAlignment"]
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



    if latest["Change5Days"]:

        comments.append(
            f"5日騰落率{latest['Change5Days']}%"
        )



    if latest["Change20Days"]:

        comments.append(
            f"20日騰落率{latest['Change20Days']}%"
        )



    comments.append(
        judgement
    )


    return " / ".join(comments)





# ==========================
# 銘柄分析
# ==========================

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



        "コード":
            code,


        "銘柄名":
            stock["銘柄名"],


        "市場":
            stock["市場・商品区分"],



        "終値":
            round(float(latest["Close"]),2),



        "前日比%":
            latest["ChangePercent"],



        "5日騰落率%":
            latest["Change5Days"],



        "20日騰落率%":
            latest["Change20Days"],



        "トレンド評価":
            latest["TrendEvaluation"],



        "MA並び":
            latest["MAAlignment"],



        "値動き評価":
            latest["PriceMovement"],



        "連続上昇日数":
            int(latest["ConsecutiveUpDays"]),



        "出来高増加日数":
            int(latest["VolumeIncreaseDays"]),



        "出来高倍率":
            latest["VolumeRatio"],



        "30日高値":
            latest["High30"],



        "30日高値までの距離%":
            latest["High30Distance"],



        "株価位置":
            position,



        "株価上昇":
            "○" if latest["PriceUp"] else "",



        "5日線上":
            "○" if latest["AboveMA5"] else "",



        "25日線上":
            "○" if latest["AboveMA25"] else "",



        "75日線上":
            "○" if latest["AboveMA75"] else "",



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



        "買い候補理由":
            make_buy_reason(
                latest,
                score,
                rank,
                position,
                judgement
            ),



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