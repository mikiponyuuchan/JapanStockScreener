from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import mplfinance as mpf

from services.yahoo_service import get_history


def save_chart(code):

    """
    ローソク足 + 出来高 + MA5 + MA25 + 年初来高値
    直近60営業日を横長で表示
    """

    df = get_history(
        code,
        period="1y"
    )

    if df is None or df.empty:
        return None

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

    year_high = (
        df["High"]
        .max()
    )

    # ==========================
    # 直近60営業日に絞る
    # ==========================

    chart_df = df.tail(60).copy()

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
            [year_high] * len(chart_df),
            linestyle="--"
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

        # 横長化
        figsize=(10, 4),

        tight_layout=True,

        savefig=dict(
            fname=filename,
            dpi=120,
            bbox_inches="tight"
        )

    )

    return filename