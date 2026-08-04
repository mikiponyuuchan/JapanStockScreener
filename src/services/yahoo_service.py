import yfinance as yf


def get_price(code: str):
    """
    最新株価を取得
    """

    ticker = f"{code}.T"

    stock = yf.Ticker(ticker)

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


def get_history(code: str, period="30d"):
    """
    過去の株価履歴を取得

    Parameters
    ----------
    code : str
        銘柄コード（例: "7203")

    period : str
        取得期間（初期値30日）
    """

    ticker = f"{code}.T"

    stock = yf.Ticker(ticker)

    df = stock.history(period=period)

    if df.empty:
        return None

    df = df.reset_index()

    return df