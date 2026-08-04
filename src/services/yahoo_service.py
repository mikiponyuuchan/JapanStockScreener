import yfinance as yf


def get_price(code: str):
    """
    1銘柄の株価を取得
    """

    ticker = f"{code}.T"

    stock = yf.Ticker(ticker)

    hist = stock.history(period="5d")

    if hist.empty:
        return None

    latest = hist.iloc[-1]

    return {
        "code": code,
        "close": latest["Close"],
        "high": latest["High"],
        "low": latest["Low"],
        "volume": latest["Volume"],
    }