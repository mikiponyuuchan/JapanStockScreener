import pandas as pd

from services.yahoo_service import get_history
from indicators.technical import add_indicators


def make_comment(latest):
    """
    注目ポイントを文章化
    """

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

    if len(comments) == 0:
        return ""

    return " / ".join(comments)


def analyze_stock(stock):
    """
    1銘柄を解析して結果(dict)を返す
    """

    code = stock["コード"]

    df = get_history(code)

    if df is None or df.empty:
        return None

    # テクニカル指標追加
    df = add_indicators(df)

    latest = df.iloc[-1]

    return {
        "コード": code,
        "銘柄名": stock["銘柄名"],
        "市場": stock["市場・商品区分"],

        # 株価
        "終値": round(float(latest["Close"]), 2),

        # 移動平均
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

        # 出来高
        "出来高": int(latest["Volume"]),

        "出来高倍率": (
            round(float(latest["VolumeRatio"]), 2)
            if pd.notna(latest["VolumeRatio"])
            else None
        ),

        # トレンド
        "株価上昇": "○" if latest["PriceUp"] else "",

        "5日線上": "○" if latest["AboveMA5"] else "",

        "25日線上": "○" if latest["AboveMA25"] else "",

        "75日線上": "○" if latest["AboveMA75"] else "",


        # シグナル
        "MACD GC": "○" if latest["MACD_GC"] else "",

        "30日高値更新": "○" if latest["New30High"] else "",


        # 追加（1.9）
        "注目ポイント": make_comment(latest),
    }