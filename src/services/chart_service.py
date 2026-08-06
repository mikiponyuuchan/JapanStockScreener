from pathlib import Path

import matplotlib.pyplot as plt

from services.yahoo_service import get_history


def save_chart(code):

    """
    TOP20用チャート保存
    """

    # --------------------------
    # 株価取得
    # --------------------------

    df = get_history(code)

    if df is None or df.empty:
        return None

    # --------------------------
    # 保存フォルダ
    # --------------------------

    folder = Path("results/charts")
    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------
    # チャート作成
    # --------------------------

    plt.figure(
        figsize=(8, 4)
    )

    plt.plot(
        df["Date"],
        df["Close"],
        linewidth=2
    )

    plt.title(code)

    plt.grid(True)

    plt.tight_layout()

    filename = folder / f"{code}.png"

    plt.savefig(
        filename,
        dpi=120
    )

    plt.close()

    return filename