import time
import yfinance as yf


RETRY_COUNT = 3
RETRY_WAIT = 1


def get_price(code: str):

    ticker = f"{code}.T"

    for attempt in range(RETRY_COUNT):

        try:

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

        except Exception:

            if attempt == RETRY_COUNT - 1:
                return None

            time.sleep(RETRY_WAIT)


def get_history(code: str, period="6mo"):

    ticker = f"{code}.T"

    for attempt in range(RETRY_COUNT):

        try:

            stock = yf.Ticker(ticker)

            df = stock.history(period=period)

            if df.empty:
                return None

            return df.reset_index()

        except Exception:

            if attempt == RETRY_COUNT - 1:
                return None

            time.sleep(RETRY_WAIT)