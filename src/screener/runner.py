from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config
from screener.loader import load_stock_list
from screener.analyzer import analyze_stock


# ============================================================
# スクリーナー実行
#
# 初動スコア15点方式
#
# このrunnerでは
#
# ・強気度
# ・ランク
# ・総合判定
# ・watchlist
# ・buy_candidate
# ・前回強気度
# ・今回強気度
# ・強気度差
#
# は使用しない。
#
# 全銘柄を分析し、
# 「初動スコア」の高い順に並べる。
# ============================================================


def run_screener(start=0, limit=None):

    # ========================================================
    # 銘柄一覧取得
    # ========================================================

    stocks = load_stock_list(
        start,
        limit
    )

    results = []
    error_list = []

    total = len(stocks)


    # ========================================================
    # 並列処理
    # ========================================================

    MAX_WORKERS = 10

    completed = 0


    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(
                analyze_stock,
                stock
            ): stock
            for _, stock in stocks.iterrows()
        }


        for future in as_completed(futures):

            stock = futures[future]

            completed += 1


            print(
                f"[{completed}/{total}] "
                f"{stock['コード']} "
                f"{stock['銘柄名']}"
            )


            try:

                result = future.result()


                if result is not None:

                    results.append(result)


            except Exception as e:

                print(
                    f"ERROR "
                    f"{stock['コード']} : {e}"
                )


                error_list.append(
                    {
                        "コード":
                            stock["コード"],

                        "銘柄名":
                            stock["銘柄名"],

                        "エラー内容":
                            str(e)
                    }
                )


    # ========================================================
    # DataFrame化
    # ========================================================

    result_df = pd.DataFrame(
        results
    )


    # ========================================================
    # 結果なし
    # ========================================================

    if result_df.empty:

        print()

        print(
            "分析結果がありません。"
        )


        if error_list:

            error_df = pd.DataFrame(
                error_list
            )


            error_path = (
                Path(config.DATA_DIR)
                /
                "error_log.csv"
            )


            error_df.to_csv(
                error_path,
                index=False,
                encoding="utf-8-sig"
            )


            print(
                f"保存しました : "
                f"{error_path}"
            )


        return result_df


    # ========================================================
    # 初動スコアで並べ替え
    #
    # 15点満点
    # 高い順
    # ========================================================

    if "初動スコア" in result_df.columns:

        result_df["初動スコア"] = pd.to_numeric(
            result_df["初動スコア"],
            errors="coerce"
        ).fillna(0)


        result_df = result_df.sort_values(
            "初動スコア",
            ascending=False
        )


    # ========================================================
    # 全分析結果保存
    # ========================================================

    price_path = (
        Path(config.DATA_DIR)
        /
        "price_data.csv"
    )


    result_df.to_csv(
        price_path,
        index=False,
        encoding="utf-8-sig"
    )


    print(
        f"保存しました : "
        f"{price_path}"
    )


    # ========================================================
    # スクリーニング結果
    #
    # 初動スコア順に全銘柄を保存。
    #
    # ここでは勝手に点数の足切りをしない。
    # 「初動スコア15点」が唯一の評価軸。
    # ========================================================

    screening_df = result_df.copy()


    if "初動スコア" in screening_df.columns:

        screening_df = screening_df.sort_values(
            "初動スコア",
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


    print(
        f"保存しました : "
        f"{screening_path}"
    )


    # ========================================================
    # 初動スコア TOP20
    #
    # 旧watchlistではない。
    # 単純に初動スコア上位20銘柄。
    # ========================================================

    top20_df = screening_df.head(
        20
    ).copy()


    top20_path = (
        Path(config.DATA_DIR)
        /
        "initial_score_top20.csv"
    )


    top20_df.to_csv(
        top20_path,
        index=False,
        encoding="utf-8-sig"
    )


    print(
        f"保存しました : "
        f"{top20_path}"
    )


    # ========================================================
    # エラーログ
    # ========================================================

    if error_list:

        error_df = pd.DataFrame(
            error_list
        )


        error_path = (
            Path(config.DATA_DIR)
            /
            "error_log.csv"
        )


        error_df.to_csv(
            error_path,
            index=False,
            encoding="utf-8-sig"
        )


        print(
            f"保存しました : "
            f"{error_path}"
        )


        print(
            f"取得エラー : "
            f"{len(error_list)} 件"
        )


    # ========================================================
    # 本日の初動スコア TOP20表示
    # ========================================================

    print()

    print(
        "=== 本日の初動スコア TOP20 ==="
    )


    if top20_df.empty:

        print(
            "対象銘柄はありません。"
        )

    else:

        # 表示用に必要な列だけ選択
        display_columns = [
            "コード",
            "銘柄名",
            "株価",
            "前日比",
            "出来高倍率",
            "5MA上",
            "信用倍率",
            "売り残前週比",
            "初動スコア",
            "分析コメント"
        ]


        available_columns = [
            column
            for column in display_columns
            if column in top20_df.columns
        ]


        print(
            top20_df[
                available_columns
            ].to_string(
                index=False
            )
        )


    print()


    # ========================================================
    # 結果返却
    # ========================================================

    return result_df