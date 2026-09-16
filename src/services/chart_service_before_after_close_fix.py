from pathlib import Path
from datetime import datetime, time as dt_time

import holidays
import matplotlib
matplotlib.use("Agg")

import mplfinance as mpf
import pandas as pd
import yfinance as yf

from services.yahoo_service import get_history


def get_today_intraday_daily(code):
    """
    Yahooの1分足から、
    今日の未確定日足 OHLCV を作成する。

    TOP20チャート表示専用。
    スクリーナー本体のスコア計算には使用しない。
    """

    try:

        ticker = f"{code}.T"

        df = yf.Ticker(
            ticker
        ).history(
            period="1d",
            interval="1m",
            auto_adjust=False
        )

        if df is None or df.empty:
            return None

        # 必要列の確認
        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        for column in required_columns:

            if column not in df.columns:
                return None

        # 欠損行を除外
        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )

        if df.empty:
            return None

        # 今日の1分足を日足1本へ集計
        today_row = pd.DataFrame(
            [
                {
                    "Date": (
                        df.index[-1]
                        .tz_localize(None)
                        .normalize()
                    ),
                    "Open": float(
                        df["Open"].iloc[0]
                    ),
                    "High": float(
                        df["High"].max()
                    ),
                    "Low": float(
                        df["Low"].min()
                    ),
                    "Close": float(
                        df["Close"].iloc[-1]
                    ),
                    "Volume": float(
                        df["Volume"].sum()
                    ),
                }
            ]
        )

        return today_row

    except Exception as e:

        print(
            f"当日チャートデータ取得ERROR "
            f"{code} : {e}"
        )

        return None


def save_chart(code):

    """
    ローソク足 + 出来高 + MA5 + MA25 + 年初来高値

    確定日足に加えて、
    今日の1分足から作成した未確定日足を追加する。

    TOP20チャート表示専用。
    """

    # ==========================
    # 確定日足取得
    # ==========================

    df = get_history(
        code,
        period="1y"
    )

    if df is None or df.empty:
        return None

    df = df.copy()

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["Date"]
    )

    # タイムゾーンを除去
    if getattr(
        df["Date"].dt,
        "tz",
        None
    ) is not None:

        df["Date"] = (
            df["Date"]
            .dt.tz_localize(None)
        )

    # ==========================
    # 今日の未確定日足を追加
    # ==========================

    now = datetime.now()

    jp_holidays = holidays.Japan(
        years=[now.year]
    )

    is_market_hours = (
        now.weekday() < 5
        and now.date() not in jp_holidays
        and dt_time(9, 0) <= now.time() < dt_time(15, 30)
    )

    today_df = None

    if is_market_hours:
        today_df = get_today_intraday_daily(
            code
        )

    if (
        today_df is not None
        and not today_df.empty
    ):

        today_date = (
            today_df["Date"].iloc[0]
        )

        # 同じ日付が既にあれば削除して
        # イントラデイ版に置き換える
        df = df[
            df["Date"].dt.normalize()
            != today_date
        ].copy()

        # 必要列だけ揃える
        common_columns = [
            column
            for column in [
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]
            if column in df.columns
        ]

        df = df[
            common_columns
        ].copy()

        today_df = today_df[
            common_columns
        ].copy()

        df = pd.concat(
            [
                df,
                today_df
            ],
            ignore_index=True
        )

        df = (
            df
            .sort_values("Date")
            .reset_index(drop=True)
        )

    # ==========================
    # 指標計算
    # ==========================

    df["MA5"] = (
        df["Close"]
        .rolling(5)
        .mean()
    )

    df["MA25"] = (
        df["Close"]
        .rolling(25)
        .mean()
    )

    # ==========================
    # ブレイクライン
    # 前日までの20営業日高値
    # ==========================

    breakout_line = (
        df["High"]
        .shift(1)
        .rolling(20)
        .max()
        .iloc[-1]
    )

    # ==========================
    # 30日高値ライン
    # 前日までの30営業日高値
    # ==========================

    high30_line = (
        df["High"]
        .shift(1)
        .rolling(30)
        .max()
        .iloc[-1]
    )

    # ==========================
    # 直近60営業日に絞る
    # ==========================

    chart_df = (
        df
        .tail(60)
        .copy()
    )

    chart_df = chart_df.set_index(
        "Date"
    )

    # ==========================
    # 保存先
    # ==========================

    folder = Path(
        "results/charts"
    )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        folder
        /
        f"{code}.png"
    )

    # ==========================
    # 追加ライン
    # ==========================

    add_plots = [

        mpf.make_addplot(
            chart_df["MA5"]
        ),

        mpf.make_addplot(
            chart_df["MA25"]
        ),

         mpf.make_addplot(
            [high30_line] * len(chart_df),
            color="green",
            linestyle="--",
            secondary_y=False
        ),

        mpf.make_addplot(
            [breakout_line] * len(chart_df),
            color="purple",
            linestyle="--",
            secondary_y=False
        )       

    ]

    # ==========================
    # チャート作成
    # ==========================

    mpf.plot(

        chart_df,

        type="candle",

        style="yahoo",

        addplot=add_plots,

        volume=True,

        figsize=(10, 4),

        tight_layout=True,

        savefig=dict(
            fname=filename,
            dpi=120,
            bbox_inches="tight"
        )

    )

    return filename