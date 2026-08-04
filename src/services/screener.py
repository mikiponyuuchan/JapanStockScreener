from pathlib import Path

import pandas as pd

import config
from services.yahoo_service import get_price


def run(limit=10):
    """
    stocks.csv の先頭 limit 銘柄の株価を取得する
    """

    file_path = Path(config.DATA_DIR) / "stocks.csv"

    df = pd.read_csv(file_path)

    results = []

    for _, row in df.head(limit).iterrows():

        code = str(row["コード"])

        print(f"取得中 : {code}")

        price = get_price(code)

        if price is not None:
            results.append(price)

    return results