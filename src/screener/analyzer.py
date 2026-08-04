import pandas as pd

from services.yahoo_service import get_history
from indicators.technical import add_indicators


def analyze_stock(stock):
    """
    1銘柄を解析して結果(dict)を返す
    """

    code = stock["コード"]

    df = get_history(code)

    if df is None or df.empty:
        return None

    df = add_indicators(df)

    latest = df.iloc[-1]

    return {
        "コード": code,
        "銘柄名": stock["銘柄名"],
        "市場": stock["市場・商品区分"],

        "終値": round(float(latest["Close"]), 2),

        "5日線": round(float(latest["MA5"]), 2)
        if pd.notna(latest["MA5"]) else None,

        "25日線": round(float(latest["MA25"]), 2)
        if pd.notna(latest["MA25"]) else None,

        "出来高": int(latest["Volume"]),

        "出来高倍率": round(float(latest["VolumeRatio"]), 2)
        if pd.notna(latest["VolumeRatio"]) else None,

        # ○表示にする
        "株価上昇": "○" if latest["PriceUp"] else "",

        "5日線上": "○" if latest["AboveMA5"] else "",

        "MACD GC": "○" if latest["MACD_GC"] else "",

        "30日高値更新": "○" if latest["New30High"] else "",
    }