import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf


RETRY_COUNT = 3
RETRY_WAIT = 1

# ==========================
# キャッシュフォルダ
# ==========================

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


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

    start_time = time.time()

    cache_file = CACHE_DIR / f"{code}.csv"

    # ==========================
    # 今日のキャッシュがあれば利用
    # ==========================

    if cache_file.exists():

        try:

            cache_date = datetime.fromtimestamp(
                cache_file.stat().st_mtime
            ).date()

            today = datetime.now().date()

            if cache_date == today:

                df = pd.read_csv(
                    cache_file,
                    parse_dates=["Date"]
                )

                elapsed = time.time() - start_time

                print(
                    f"データ取得(Cache) : {elapsed:.2f} 秒"
                )

                return df

        except Exception:
            pass

    # ==========================
    # Yahooから取得
    # ==========================

    ticker = f"{code}.T"

    for attempt in range(RETRY_COUNT):

        try:

            stock = yf.Ticker(ticker)

            df = stock.history(period=period)

            if df.empty:
                return None

            df = df.reset_index()

            # ==========================
            # キャッシュ保存
            # ==========================

            try:

                df.to_csv(
                    cache_file,
                    index=False,
                    encoding="utf-8-sig"
                )

            except Exception:
                pass

            elapsed = time.time() - start_time

            print(
                f"データ取得(Yahoo) : {elapsed:.2f} 秒"
            )


            return df

        except Exception:

            if attempt == RETRY_COUNT - 1:
                return None

            time.sleep(RETRY_WAIT)

    return None