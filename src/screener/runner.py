from pathlib import Path

import pandas as pd

import config
from screener.loader import load_stock_list
from screener.analyzer import analyze_stock



def run_screener(start=0, limit=None):

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



    # ==========================
    # 1.20 候補履歴比較
    # ==========================

    previous_path = (
        Path(config.DATA_DIR)
        /
        "previous_buy_candidate.csv"
    )


    change_path = (
        Path(config.DATA_DIR)
        /
        "candidate_change.csv"
    )


    if previous_path.exists():

        previous_df = pd.read_csv(
            previous_path,
            encoding="utf-8-sig"
        )


        previous_codes = set(
            previous_df["コード"]
        )

        current_codes = set(
            buy_candidate_df["コード"]
        )


        change_results = []

        # 新規・継続・強化・弱化判定
        for _, row in buy_candidate_df.iterrows():

            if row["コード"] in previous_codes:

                old_row = previous_df[
                    previous_df["コード"] == row["コード"]
                ].iloc[0]


                old_score = old_row["強気度"]

                new_score = row["強気度"]


                if new_score > old_score:

                    status = "強化"


                elif new_score < old_score:

                    status = "弱化"


                else:

                    status = "継続候補"



            else:

                old_score = ""

                new_score = row["強気度"]

                status = "新規候補"



            change_results.append(
                {
                    "コード": row["コード"],
                    "銘柄名": row["銘柄名"],
                    "候補変化": status,
                    "前回強気度": old_score,
                    "今回強気度": new_score,
                    "強気度差":
                        (
                            new_score - old_score
                            if old_score != ""
                            else ""
                        ),
                    "総合判定": row["総合判定"]
                }
            )



        # 除外銘柄
        for _, row in previous_df.iterrows():

            if row["コード"] not in current_codes:

                change_results.append(
                    {
                        "コード": row["コード"],
                        "銘柄名": row["銘柄名"],
                        "候補変化": "除外銘柄",
                        "強気度": "",
                        "総合判定": ""
                    }
                )


        change_df = pd.DataFrame(
            change_results
        )


        change_df.to_csv(
            change_path,
            index=False,
            encoding="utf-8-sig"
        )


        print(
            f"保存しました : {change_path}"
        )


    else:

        print(
            "初回実行のため候補履歴を作成します。"
        )


    # 今日の候補を保存
    buy_candidate_df.to_csv(
        previous_path,
        index=False,
        encoding="utf-8-sig"
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