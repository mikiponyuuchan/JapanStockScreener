import time
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
# 最新の期待営業日
# ==========================

def get_expected_market_date():

    now = datetime.now()

    # ==========================
    # 日本の祝日
    # ==========================

    jp_holidays = holidays.Japan(
        years=now.year
    )

    today = now.date()

    # ==========================
    # 休場日
    #
    # 土日・祝日
    # → 直前の営業日
    # ==========================

    if (
        now.weekday() >= 5
        or today in jp_holidays
    ):

        date = (
            pd.Timestamp(today)
            - pd.offsets.BDay(1)
        )

        # 祝日が連続する場合も考慮
        while (
            date.weekday() >= 5
            or date.date() in jp_holidays
        ):

            date = (
                date
                - pd.offsets.BDay(1)
            )

        return date.normalize()

    # ==========================
    # 平日
    #
    # 15:30以降
    # → 当日
    #
    # 15:30前
    # → 前営業日
    # ==========================

    if now.time() >= dt_time(15, 30):

        return pd.Timestamp(
            today
        ).normalize()

    return (
        pd.Timestamp(today)
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
# Yahoo履歴データ取得
# ==========================

def _download_history(
    code: str,
    period="6mo"
):

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

            df = df.reset_index()

            if "Date" not in df.columns:

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


# ==========================
# キャッシュ保存
# ==========================

def _save_cache(
    df,
    cache_file
):

    try:

        df.to_csv(
            cache_file,
            index=False,
            encoding="utf-8-sig"
        )

    except Exception:

        pass


# ==========================
# 履歴データ取得
# ==========================

def get_history(
    code: str,
    period="6mo"
):

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

                cached_df["Date"] = pd.to_datetime(
                    cached_df["Date"],
                    errors="coerce"
                )

                # キャッシュの日付にタイムゾーンがある場合は削除
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

                    # ==========================
                    # すでに最新営業日まである
                    # ==========================

                    if latest_cache_date >= expected_date:

                        elapsed = (
                            time.time()
                            - start_time
                        )

                        print(
                            f"キャッシュ利用 : "
                            f"{elapsed:.2f} 秒"
                        )

                        return cached_df

                    # ==========================
                    # キャッシュあり・更新が必要
                    #
                    # 6か月分を取り直さず
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

                        elapsed = (
                            time.time()
                            - start_time
                        )

                        print(
                            f"データ更新(Yahoo) : "
                            f"{elapsed:.2f} 秒"
                        )

                        return combined_df

        except Exception:

            # キャッシュが壊れている場合は
            # Yahooから再取得
            pass

    # ==========================
    # キャッシュがない場合
    #
    # 今まで通り6か月分取得
    # ==========================

    df = _download_history(
        code,
        period=period
    )

    if df is None or df.empty:

        return None

    # ==========================
    # キャッシュ保存
    # ==========================

    _save_cache(
        df,
        cache_file
    )

    elapsed = (
        time.time()
        - start_time
    )

    print(
        f"データ取得(Yahoo) : "
        f"{elapsed:.2f} 秒"
    )

    return df