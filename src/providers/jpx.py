from pathlib import Path

import pandas as pd
import requests

import config


def download_stock_list():
    """JPX上場銘柄一覧をダウンロードする"""

    Path(config.DATA_DIR).mkdir(exist_ok=True)

    save_path = Path(config.DATA_DIR) / "jpx_stock_list.xls"

    print("JPX銘柄一覧をダウンロード中...")

    response = requests.get(config.JPX_URL, timeout=30)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(response.content)

    print(f"保存しました：{save_path}")

    return save_path


def load_stock_list():
    """JPX上場銘柄一覧を読み込む"""

    file_path = Path(config.DATA_DIR) / "jpx_stock_list.xls"

    df = pd.read_excel(file_path)

    # 必要な列だけ残す
    df = df[
        [
            "コード",
            "銘柄名",
            "市場・商品区分",
            "33業種区分",
            "17業種区分",
            "規模区分",
        ]
    ]

    # コードを文字列にする
    df["コード"] = df["コード"].astype(str)

    return df


def save_stock_list(df):
    """銘柄一覧をCSV保存"""

    save_path = Path(config.DATA_DIR) / "stocks.csv"

    df.to_csv(
        save_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"CSV保存完了：{save_path}")