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

    folder = Path("results/charts")
    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = folder / f"{code}.png"

    plt.figure(figsize=(8, 4))

    plt.plot(
        df["Date"],
        df["Close"],
        linewidth=2
    )

    plt.title(code)

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        filename,
        dpi=120
    )

    plt.close()

    return filename