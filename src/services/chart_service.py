from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import mplfinance as mpf

from services.yahoo_service import get_history


def save_chart(code):

    """
    ローソク足チャート画像保存
    """

    df = get_history(code)

    if df is None or df.empty:
        return None


    # ==========================
    # 移動平均計算
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
    # mplfinance用データ
    # ==========================

    chart_df = df.copy()

    chart_df = chart_df.set_index(
        "Date"
    )


    # ==========================
    # 保存フォルダ
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
            chart_df["MA5"],
            color="blue"
        ),

        mpf.make_addplot(
            chart_df["MA25"],
            color="red"
        )

    ]


    # ==========================
    # ローソク足作成
    # ==========================

    mpf.plot(
        chart_df,

        type="candle",

        volume=True,

        addplot=add_plots,

        figsize=(8, 6),

        style="yahoo",

        savefig=dict(
            fname=filename,
            dpi=120,
            bbox_inches="tight"
        )

    )


    return filename