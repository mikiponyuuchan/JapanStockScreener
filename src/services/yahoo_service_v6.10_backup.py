import time
import atexit
import threading

from datetime import datetime, time as dt_time
from pathlib import Path

import holidays
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
# Ver6.9 詳細計測
# ==========================

_stats_lock = threading.Lock()

_stats = {
    "total_calls": 0,
    "cache_hits": 0,
    "cache_updates": 0,
    "full_downloads": 0,

    "expected_date_time": 0.0,
    "cache_read_time": 0.0,
    "yahoo_download_time": 0.0,
    "cache_save_time": 0.0,
    "total_get_history_time": 0.0,

    "yahoo_10d_calls": 0,
    "yahoo_6mo_calls": 0,
}


def _add_stat(name, value):

    with _stats_lock:

        _stats[name] += value


def _add_count(name, value=1):

    with _stats_lock:

        _stats[name] += value


def print_yahoo_stats():

    with _stats_lock:

        stats = dict(_stats)

    print()
    print("==============================")
    print(" Ver6.9 Yahoo詳細計測")
    print("==============================")

    print(
        f"get_history呼出       : "
        f"{stats['total_calls']}"
    )

    print(
        f"キャッシュ利用        : "
        f"{stats['cache_hits']}"
    )

    print(
        f"キャッシュ更新        : "
        f"{stats['cache_updates']}"
    )

    print(
        f"初回Yahoo取得         : "
        f"{stats['full_downloads']}"
    )

    print()

    print(
        f"営業日判定時間        : "
        f"{stats['expected_date_time']:.2f} 秒"
    )

    print(
        f"キャッシュ読込時間    : "
        f"{stats['cache_read_time']:.2f} 秒"
    )

    print(
        f"Yahoo取得時間         : "
        f"{stats['yahoo_download_time']:.2f} 秒"
    )

    print(
        f"キャッシュ保存時間    : "
        f"{stats['cache_save_time']:.2f} 秒"
    )

    print(
        f"get_history実時間合計 : "
        f"{stats['total_get_history_time']:.2f} 秒"
    )

    print()

    print(
        f"Yahoo 10d取得回数     : "
        f"{stats['yahoo_10d_calls']}"
    )

    print(
        f"Yahoo 6mo取得回数     : "
        f"{stats['yahoo_6mo_calls']}"
    )

    print("==============================")
    print()


# プログラム終了時に集計表示
atexit.register(print_yahoo_stats)



# ==========================
# 最新の期待営業日
# ==========================

def get_expected_market_date():

    now = datetime.now()

    jp_holidays = holidays.Japan(
        years=[
            now.year,
            now.year - 1,
            now.year + 1
        ]
    )

    today = pd.Timestamp(
        now.date()
    ).normalize()

    # ==========================
    # 基準日を決める
    #
    # 平日15:30以降
    # → 当日
    #
    # それ以外
    # → 前日
    # ==========================

    if (
        now.weekday() < 5
        and now.time() >= dt_time(15, 30)
        and now.date() not in jp_holidays
    ):

        date = today

    else:

        date = (
            today
            - pd.Timedelta(days=1)
        )

    # ==========================
    # 土日・祝日を遡る
    # ==========================

    while (
        date.weekday() >= 5
        or date.date() in jp_holidays
    ):

        date = (
            date
            - pd.Timedelta(days=1)
        )

    return date.normalize()



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
# Yahoo履歴データ取得
# ==========================

def _download_history(
    code: str,
    period="6mo"
):

    start_time = time.time()

    ticker = f"{code}.T"

    if period == "10d":

        _add_count(
            "yahoo_10d_calls"
        )

    else:

        _add_count(
            "yahoo_6mo_calls"
        )

    for attempt in range(RETRY_COUNT):

        try:

            stock = yf.Ticker(
                ticker
            )

            df = stock.history(
                period=period
            )

            if df.empty:

                _add_stat(
                    "yahoo_download_time",
                    time.time() - start_time
                )

                return None

            df = df.reset_index()

            if "Date" not in df.columns:

                _add_stat(
                    "yahoo_download_time",
                    time.time() - start_time
                )

                return None

            df["Date"] = pd.to_datetime(
                df["Date"],
                errors="coerce"
            )

            df = (
                df
                .dropna(subset=["Date"])
                .sort_values("Date")
            )

            _add_stat(
                "yahoo_download_time",
                time.time() - start_time
            )

            return df

        except Exception:

            if (
                attempt
                ==
                RETRY_COUNT - 1
            ):

                _add_stat(
                    "yahoo_download_time",
                    time.time() - start_time
                )

                return None

            time.sleep(
                RETRY_WAIT
            )

    _add_stat(
        "yahoo_download_time",
        time.time() - start_time
    )

    return None


# ==========================
# キャッシュ保存
# ==========================

def _save_cache(
    df,
    cache_file
):

    start_time = time.time()

    try:

        df.to_csv(
            cache_file,
            index=False,
            encoding="utf-8-sig"
        )

    except Exception:

        pass

    finally:

        _add_stat(
            "cache_save_time",
            time.time() - start_time
        )


# ==========================
# 履歴データ取得
# ==========================

def get_history(
    code: str,
    period="6mo"
):

    start_time = time.time()

    _add_count(
        "total_calls"
    )

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

        cache_read_start = time.time()

        try:

            cached_df = pd.read_csv(
                cache_file,
                parse_dates=["Date"]
            )

            if "Date" in cached_df.columns:

                cached_df["Date"] = pd.to_datetime(
                    cached_df["Date"],
                    errors="coerce"
                )

                # タイムゾーンを除去
                if cached_df["Date"].dt.tz is not None:

                    cached_df["Date"] = (
                        cached_df["Date"]
                        .dt.tz_localize(None)
                    )

                cached_df = (
                    cached_df
                    .dropna(subset=["Date"])
                    .sort_values("Date")
                )

                if not cached_df.empty:

                    latest_cache_date = (
                        cached_df["Date"]
                        .dt.normalize()
                        .max()
                    )

                    _add_stat(
                        "cache_read_time",
                        time.time() - cache_read_start
                    )

                    # ==========================
                    # 最新営業日まで存在
                    # ==========================

                    if (
                        latest_cache_date
                        >=
                        expected_date
                    ):

                        _add_count(
                            "cache_hits"
                        )

                        elapsed = (
                            time.time()
                            - start_time
                        )

                        _add_stat(
                            "total_get_history_time",
                            elapsed
                        )

                        print(
                            f"キャッシュ利用 : "
                            f"{elapsed:.2f} 秒"
                        )

                        return cached_df

                    # ==========================
                    # キャッシュあり・更新必要
                    #
                    # 直近10営業日程度だけ取得
                    # ==========================

                    update_df = _download_history(
                        code,
                        period="10d"
                    )

                    if (
                        update_df is not None
                        and not update_df.empty
                    ):

                        combined_df = pd.concat(
                            [
                                cached_df,
                                update_df
                            ],
                            ignore_index=True
                        )

                        combined_df["Date"] = pd.to_datetime(
                            combined_df["Date"],
                            errors="coerce"
                        )

                        combined_df = (
                            combined_df
                            .dropna(subset=["Date"])
                            .sort_values("Date")
                            .drop_duplicates(
                                subset=["Date"],
                                keep="last"
                            )
                        )

                        _save_cache(
                            combined_df,
                            cache_file
                        )

                        _add_count(
                            "cache_updates"
                        )

                        elapsed = (
                            time.time()
                            - start_time
                        )

                        _add_stat(
                            "total_get_history_time",
                            elapsed
                        )

                        print(
                            f"データ更新(Yahoo) : "
                            f"{elapsed:.2f} 秒"
                        )

                        return combined_df

        except Exception:

            _add_stat(
                "cache_read_time",
                time.time() - cache_read_start
            )

            # キャッシュが壊れている場合は
            # Yahooから再取得
            pass

    # ==========================
    # キャッシュがない場合
    #
    # 6か月分取得
    # ==========================

    df = _download_history(
        code,
        period=period
    )

    if df is None or df.empty:

        elapsed = (
            time.time()
            - start_time
        )

        _add_stat(
            "total_get_history_time",
            elapsed
        )

        return None

    # ==========================
    # キャッシュ保存
    # ==========================

    _save_cache(
        df,
        cache_file
    )

    _add_count(
        "full_downloads"
    )

    elapsed = (
        time.time()
        - start_time
    )

    _add_stat(
        "total_get_history_time",
        elapsed
    )

    print(
        f"データ取得(Yahoo) : "
        f"{elapsed:.2f} 秒"
    )

    return df