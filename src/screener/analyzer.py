import pandas as pd
import time

from services.yahoo_service import get_history
from services.chart_service import save_chart
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


    if latest["TrendEvaluation"]:
        comments.append(
            latest["TrendEvaluation"]
        )


    if latest["MAAlignment"]:
        comments.append(
            latest["MAAlignment"]
        )


    if latest["InitialMoveSignal"]:
        comments.append(
            "初動シグナル"
        )


    if latest["PullbackSignal"]:
        comments.append(
            "押し目候補"
        )


    if latest["MACD_GC"]:
        comments.append(
            "MACD GC"
        )


    if latest["New30High"]:
        comments.append(
            "30日高値更新"
        )


    if latest["NewYearHigh"]:
        comments.append(
            "年初来高値更新"
        )


    if latest["BreakoutSignal"]:
        comments.append(
            "ブレイクアウト"
        )


    if latest["BreakoutFirstDay"]:
        comments.append(
            "ブレイク初日"
        )


    if pd.notna(latest["VolumeRatio"]):

        if latest["VolumeRatio"] >= 2:

            comments.append(
                "出来高急増"
            )


    if pd.notna(latest["VolumeRatio20"]):

        if latest["VolumeRatio20"] >= 2:

            comments.append(
                "20日平均出来高超"
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


    if pd.notna(latest["RSI"]):

        comments.append(
            f"RSI {latest['RSI']}"
        )


    return " / ".join(comments)





# ==========================
# スコア計算 Ver3.0
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


    if latest["NewYearHigh"]:
        score += 2


    if latest["BreakoutSignal"]:
        score += 2


    if latest["VolumeRatio"] >= 2:
        score += 1


    if latest["VolumeRatio20"] >= 2:
        score += 1


    if latest["VolumeIncreaseDays"] >= 3:
        score += 1


    if latest["ConsecutiveUpDays"] >= 3:
        score += 1


    if latest["Change5Days"] >= 5:
        score += 1


    if latest["Change20Days"] >= 10:
        score += 1


    if latest["RSI_Strong"]:
        score += 1



    # トレンド評価

    if latest["TrendEvaluation"] == "強い上昇":

        score += 2


    elif latest["TrendEvaluation"] == "上昇継続":

        score += 1



    # 初動

    if latest["InitialMoveSignal"]:

        score += 2



    if latest["PullbackSignal"]:

        score += 1



    return score
# ==========================
# ランク
# ==========================

def make_rank(score):

    if score >= 18:

        return "A"


    elif score >= 9:

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
        position,
        latest=None):


    # ==========================
    # 買い候補
    # ==========================

    if (
        rank == "A"
        and score >= 18
        and latest is not None
        and (
            latest["BreakoutSignal"]
            or
            latest["MACD_GC"]
            or
            latest["InitialMoveSignal"]
        )
        and latest["RSI"] >= 50
    ):

        return "買い候補"



    # ==========================
    # 監視強化
    # ==========================

    elif (
        rank == "A"
        and score >= 15
    ):

        return "監視強化"



    # ==========================
    # 通常監視
    # ==========================

    elif rank in ["A","B"]:

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


    if latest["InitialMoveSignal"]:

        reasons.append(
            "初動シグナル"
        )


    if latest["PullbackSignal"]:

        reasons.append(
            "押し目判定"
        )


    if latest["MACD_GC"]:

        reasons.append(
            "MACDゴールデンクロス"
        )


    if latest["New30High"]:

        reasons.append(
            "30日高値更新"
        )


    if latest["NewYearHigh"]:

        reasons.append(
            "年初来高値更新"
        )


    if latest["BreakoutSignal"]:

        reasons.append(
            "ブレイクアウト"
        )


    if latest["VolumeRatio"] >= 2:

        reasons.append(
            f"出来高{latest['VolumeRatio']}倍"
        )


    if latest["RSI_Strong"]:

        reasons.append(
            f"RSI良好({latest['RSI']})"
        )


    if latest["MA25Deviation"]:

        reasons.append(
            f"25日線乖離{latest['MA25Deviation']}%"
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


    if latest["TrendEvaluation"]:

        comments.append(
            latest["TrendEvaluation"]
        )


    if latest["MAAlignment"]:

        comments.append(
            latest["MAAlignment"]
        )


    if latest["InitialMoveSignal"]:

        comments.append(
            "初動検出"
        )


    if latest["PullbackSignal"]:

        comments.append(
            "押し目"
        )


    if latest["MACD_GC"]:

        comments.append(
            "MACD GC"
        )


    if latest["NewYearHigh"]:

        comments.append(
            "年初来高値"
        )


    if latest["BreakoutSignal"]:

        comments.append(
            "ブレイク"
        )


    if pd.notna(latest["RSI"]):

        comments.append(
            f"RSI{latest['RSI']}"
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


    # ==========================
    # データ取得計測
    # ==========================

    data_start = time.time()

    df = get_history(code)

    data_time = time.time() - data_start


    if df is None or df.empty:
        return None



    # ==========================
    # 指標計算計測
    # ==========================

    indicator_start = time.time()

    df = add_indicators(df)

    indicator_time = (
        time.time()
        -
        indicator_start
    )


    latest = df.iloc[-1]



    # ==========================
    # 判定作成計測
    # ==========================

    judge_start = time.time()


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
        position,
        latest
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

        "RSI":
            latest["RSI"],

        "ATR":
            latest["ATR"],

        "トレンド評価":
            latest["TrendEvaluation"],

        "MA並び":
            latest["MAAlignment"],

        "初動シグナル":
            "○" if latest["InitialMoveSignal"] else "",

        "押し目判定":
            "○" if latest["PullbackSignal"] else "",

        "MACD GC":
            "○" if latest["MACD_GC"] else "",

        "30日高値更新":
            "○" if latest["New30High"] else "",

        "年初来高値更新":
            "○" if latest["NewYearHigh"] else "",

        "ブレイク":
            "○" if latest["BreakoutSignal"] else "",

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


# ==========================
# Sprint2 計測データ
# ==========================

"_data_time":
    data_time,

"_indicator_time":
    indicator_time,

"_judge_time":
    time.time() - judge_start

}