from pathlib import Path

import pandas as pd

import config
from services.yahoo_service import get_price


def run(limit=10):
    """
    stocks.csv の先頭 limit 銘柄の株価を取得し、
    price_data.csv に保存する
    """

    file_path = Path(config.DATA_DIR) / "stocks.csv"

    df = pd.read_csv(file_path)

    results = []

    for _, row in df.head(limit).iterrows():

        code = str(row["コード"])

        print(f"取得中 : {code}")

        price = get_price(code)

        if price is None:
            continue

        results.append(
            {
                "コード": code,
                "銘柄名": row["銘柄名"],
                "市場": row["市場・商品区分"],
                "33業種": row["33業種区分"],
                "17業種": row["17業種区分"],
                "規模": row["規模区分"],
                "終値": price["close"],
                "高値": price["high"],
                "安値": price["low"],
                "出来高": price["volume"],
            }
        )

    result_df = pd.DataFrame(results)

    save_path = Path(config.DATA_DIR) / "price_data.csv"

    result_df.to_csv(
        save_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(f"保存しました：{save_path}")

    return result_df