import yfinance as yf


def get_price(code: str):
    """
    1銘柄の最新株価を取得する

    Parameters
    ----------
    code : str
        銘柄コード（例: "7203"）

    Returns
    -------
    dict | None
        株価情報
    """

    ticker = f"{code}.T"

    stock = yf.Ticker(ticker)

    # 直近5営業日のデータを取得
    hist = stock.history(period="5d")

    if hist.empty:
        return None

    latest = hist.iloc[-1]

    return {
        "code": code,
        "close": round(float(latest["Close"]), 2),
        "high": round(float(latest["High"]), 2),
        "low": round(float(latest["Low"]), 2),
        "volume": int(latest["Volume"]),
    }