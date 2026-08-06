from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from services.yahoo_service import get_history


def save_chart(code):

    """
    チャート画像保存
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
    # 保存フォルダ
    # ==========================

    folder = Path("results/charts")

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
    # チャート作成
    # ==========================

    plt.figure(
        figsize=(8, 4)
    )


    plt.plot(
        df["Date"],
        df["Close"],
        linewidth=2,
        label="Close"
    )


    plt.plot(
        df["Date"],
        df["MA5"],
        linewidth=1.5,
        label="MA5"
    )


    plt.plot(
        df["Date"],
        df["MA25"],
        linewidth=1.5,
        label="MA25"
    )


    plt.title(
        code
    )


    plt.legend()


    plt.grid(True)


    plt.tight_layout()


    plt.savefig(
        filename,
        dpi=120
    )


    plt.close()


    return filename