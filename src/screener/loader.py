import pandas as pd
from pathlib import Path

import config


def load_stock_list(start=0, limit=None):
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
    df = df.reset_index(drop=True)

    total = len(df)

    if limit is None:

        print(f"普通株数 : {total}")
        print(f"対象 : 全銘柄")
        print()

        return df

    end = min(start + limit, total)

    print(f"普通株数 : {total}")
    print(f"対象 : {start + 1} ～ {end} 銘柄")
    print()

    return df.iloc[start:end].reset_index(drop=True)