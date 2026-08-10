import time
from datetime import datetime, time as dt_time
from pathlib import Path

import pandas as pd
import yfinance as yf


RETRY_COUNT = 3
RETRY_WAIT = 1


# ==========================
# キャッシュフォルダ
# ==========================

CACHE_DIR = Path("data/cache")

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================
# 最新の期待営業日
# ==========================

def get_expected_market_date():

    now = datetime.now()

    # ==========================
    # 土曜日
    # ==========================

    if now.weekday() == 5:

        return (
            pd.Timestamp(
                now.date()
            )
            - pd.offsets.BDay(1)
        ).normalize()


    # ==========================
    # 日曜日
    # ==========================

    if now.weekday() == 6:

        return (
            pd.Timestamp(
                now.date()
            )
            - pd.offsets.BDay(1)
        ).normalize()


    # ==========================
    # 平日
    #
    # 15:30以降
    # → 当日の株価を期待
    #
    # 15:30前
    # → 前営業日を期待
    # ==========================

    if now.time() >= dt_time(15, 30):

        return pd.Timestamp(
            now.date()
        ).normalize()

    else:

        return (
            pd.Timestamp(
                now.date()
            )
            - pd.offsets.BDay(1)
        ).normalize()


# ==========================
# 最新株価
# ==========================

def get_price(code: str):

    ticker = f"{code}.T"

    for attempt in range(RETRY_COUNT):

        try:

            stock = yf.Ticker(
                ticker
            )

            hist = stock.history(
                period="5d"
            )

            if hist.empty:

                return None

            latest = hist.iloc[-1]

            return {

                "code":
                    code,

                "close":
                    round(
                        float(
                            latest["Close"]
                        ),
                        2
                    ),

                "high":
                    round(
                        float(
                            latest["High"]
                        ),
                        2
                    ),

                "low":
                    round(
                        float(
                            latest["Low"]
                        ),
                        2
                    ),

                "volume":
                    int(
                        latest["Volume"]
                    ),
            }

        except Exception:

            if (
                attempt
                ==
                RETRY_COUNT - 1
            ):

                return None

            time.sleep(
                RETRY_WAIT
            )


# ==========================
# 履歴データ取得
# ==========================

def get_history(
        code: str,
        period="6mo"):

    start_time = time.time()

    cache_file = (
        CACHE_DIR
        /
        f"{code}.csv"
    )

    expected_date = (
        get_expected_market_date()
    )


    # ==========================
    # キャッシュ確認
    # ==========================

    if cache_file.exists():

        try:

            cached_df = pd.read_csv(
                cache_file,
                parse_dates=["Date"]
            )


            if "Date" in cached_df.columns:

                cached_df["Date"] = (
                    pd.to_datetime(
                        cached_df["Date"],
                        errors="coerce"
                    )
                )

                cached_df = (
                    cached_df
                    .dropna(
                        subset=["Date"]
                    )
                    .sort_values("Date")
                )


                if not cached_df.empty:

                    latest_cache_date = (
                        cached_df["Date"]
                        .dt.normalize()
                        .max()
                    )


                    # ==========================
                    # 最新営業日まで取得済み
                    # ==========================

                    if (
                        latest_cache_date
                        >=
                        expected_date
                    ):

                        return cached_df


        except Exception:

            # キャッシュが壊れている場合は
            # Yahooから再取得
            pass


    # ==========================
    # Yahooから取得
    # ==========================

    ticker = f"{code}.T"


    for attempt in range(RETRY_COUNT):

        try:

            stock = yf.Ticker(
                ticker
            )

            df = stock.history(
                period=period
            )


            if df.empty:

                return None


            # ==========================
            # Date列を作成
            # ==========================

            df = df.reset_index()


            if "Date" not in df.columns:

                return None


            df["Date"] = (
                pd.to_datetime(
                    df["Date"],
                    errors="coerce"
                )
            )


            df = (
                df
                .dropna(
                    subset=["Date"]
                )
                .sort_values("Date")
            )


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


            elapsed = (
                time.time()
                -
                start_time
            )


            print(
                f"データ取得(Yahoo) : "
                f"{elapsed:.2f} 秒"
            )


            # ==========================
            # 重要
            #
            # Date列を残したまま返す
            #
            # chart_service.py
            # tracking_service.py
            # analyzer.py
            # が従来通り使える
            # ==========================

            return df


        except Exception:

            if (
                attempt
                ==
                RETRY_COUNT - 1
            ):

                return None


            time.sleep(
                RETRY_WAIT
            )


    return None