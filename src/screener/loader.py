import pandas as pd
from pathlib import Path

import config


def load_stock_list(start=0, limit=10):
    """
    普通株のみ読み込む
    """

    file_path = Path(config.DATA_DIR) / "stocks.csv"

    df = pd.read_csv(file_path, dtype={"コード": str})

    normal_markets = [
        "プライム（内国株式）",
        "スタンダード（内国株式）",
        "グロース（内国株式）",
    ]

    df = df[df["市場・商品区分"].isin(normal_markets)]

    print(f"普通株数 : {len(df)}")
    print(f"対象 : {start + 1} ～ {start + limit} 銘柄")
    print()

    return df.iloc[start:start + limit].reset_index(drop=True)