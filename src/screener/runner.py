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

        print(
            f"[{i}/{total}] {stock['コード']} {stock['銘柄名']}"
        )

        result = analyze_stock(stock)

        if result is not None:
            results.append(result)



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

    print(f"保存しました : {price_path}")



    # ==========================
    # 基本スクリーニング
    # ==========================

    screening_df = result_df[
        (result_df["出来高倍率"] >= 2)
        &
        (result_df["株価上昇"] == "○")
        &
        (result_df["5日線上"] == "○")
    ].sort_values(
        "出来高倍率",
        ascending=False
    )



    screening_path = (
        Path(config.DATA_DIR)
        /
        "screening_result.csv"
    )


    screening_df.to_csv(
        screening_path,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"保存しました : {screening_path}")



    # ==========================
    # watchlist
    # ==========================

    watchlist_df = result_df[
        (result_df["監視ランク"] == "A")
        |
        (result_df["MACD GC"] == "○")
        |
        (result_df["30日高値更新"] == "○")
    ]


    watchlist_df = watchlist_df.sort_values(
        [
            "強気度",
            "出来高倍率"
        ],
        ascending=[
            False,
            False
        ]
    )


    watchlist_path = (
        Path(config.DATA_DIR)
        /
        "watchlist.csv"
    )


    watchlist_df.to_csv(
        watchlist_path,
        index=False,
        encoding="utf-8-sig"
    )


    print(f"保存しました : {watchlist_path}")



    # ==========================
    # watchlist TOP20
    # ==========================

    watchlist_top_df = watchlist_df.head(20)


    watchlist_top_path = (
        Path(config.DATA_DIR)
        /
        "watchlist_top.csv"
    )


    watchlist_top_df.to_csv(
        watchlist_top_path,
        index=False,
        encoding="utf-8-sig"
    )


    print(f"保存しました : {watchlist_top_path}")



    # ==========================
    # 1.19 買い候補
    # ==========================

    buy_candidate_df = result_df[
        result_df["総合判定"] == "買い候補"
    ]


    buy_candidate_df = buy_candidate_df.sort_values(
        [
            "強気度",
            "出来高倍率"
        ],
        ascending=[
            False,
            False
        ]
    )


    buy_candidate_path = (
        Path(config.DATA_DIR)
        /
        "buy_candidate.csv"
    )


    buy_candidate_df.to_csv(
        buy_candidate_path,
        index=False,
        encoding="utf-8-sig"
    )


    print(
        f"保存しました : {buy_candidate_path}"
    )



    print()


    if watchlist_top_df.empty:

        print(
            "注目銘柄はありませんでした。"
        )

    else:

        print(
            "=== 本日の注目銘柄 TOP20 ==="
        )

        print(watchlist_top_df)



    if not buy_candidate_df.empty:

        print()

        print(
            "=== 買い候補 ==="
        )

        print(buy_candidate_df)



    return screening_df