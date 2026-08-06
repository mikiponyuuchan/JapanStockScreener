from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import mplfinance as mpf

from services.yahoo_service import get_history


def save_chart(code):

    """
    ローソク足 + 出来高 + MA + 年初来高値
    """

    df = get_history(
        code,
        period="1y"
    )

    if df is None or df.empty:
        return None


    # ==========================
    # 指標
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
    # mplfinance用
    # ==========================

    chart_df = df.copy()

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
    # チャート
    # ==========================

    mpf.plot(

        chart_df,

        type="candle",

        style="yahoo",

        addplot=add_plots,

        volume=True,

        figsize=(8,5),

        tight_layout=True,

        savefig=dict(
            fname=filename,
            dpi=120,
            bbox_inches="tight"
        )

    )


    return filename