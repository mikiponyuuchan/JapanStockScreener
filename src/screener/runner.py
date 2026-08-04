from pathlib import Path

import pandas as pd

import config
from screener.loader import load_stock_list
from screener.analyzer import analyze_stock


def run_screener(start=0, limit=10):

    stocks = load_stock_list(start, limit)

    results = []

    total = len(stocks)

    for i, (_, stock) in enumerate(stocks.iterrows(), start=1):

        print(f"[{i}/{total}] {stock['コード']} {stock['銘柄名']}")

        result = analyze_stock(stock)

        if result is not None:
            results.append(result)

    # ==========================
    # DataFrame作成
    # ==========================

    result_df = pd.DataFrame(results)

    # ==========================
    # 全データ保存
    # ==========================

    price_path = Path(config.DATA_DIR) / "price_data.csv"

    result_df.to_csv(
        price_path,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(f"保存しました : {price_path}")

    # ==========================
    # スクリーニング
    # ==========================

    screening_df = result_df[
        (result_df["出来高倍率"] >= 2)
        & (result_df["株価上昇"] == "○")
        & (result_df["5日線上"] == "○")
    ].sort_values(
        "出来高倍率",
        ascending=False
    )

    # ==========================
    # 結果保存
    # ==========================

    screening_path = Path(config.DATA_DIR) / "screening_result.csv"

    screening_df.to_csv(
        screening_path,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"保存しました : {screening_path}")

    print()

    if screening_df.empty:
        print("条件に一致する銘柄はありませんでした。")
    else:
        print(screening_df)

    return screening_df