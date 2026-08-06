from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from services.yahoo_service import get_history


def save_chart(code):

    """
    株価チャート画像保存
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

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(8, 6),
        sharex=True,
        gridspec_kw={
            "height_ratios": [3, 1]
        }
    )


    # ==========================
    # 株価チャート
    # ==========================

    axes[0].plot(
        df["Date"],
        df["Close"],
        linewidth=2,
        label="Close"
    )


    axes[0].plot(
        df["Date"],
        df["MA5"],
        linewidth=1.5,
        label="MA5"
    )


    axes[0].plot(
        df["Date"],
        df["MA25"],
        linewidth=1.5,
        label="MA25"
    )


    axes[0].set_title(
        code
    )


    axes[0].legend()


    axes[0].grid(True)


    # ==========================
    # 出来高チャート
    # ==========================

    if "Volume" in df.columns:

        axes[1].bar(
            df["Date"],
            df["Volume"]
        )


    axes[1].set_ylabel(
        "Volume"
    )


    axes[1].grid(True)


    # ==========================
    # 保存
    # ==========================

    plt.tight_layout()


    plt.savefig(
        filename,
        dpi=120
    )


    plt.close()


    return filename