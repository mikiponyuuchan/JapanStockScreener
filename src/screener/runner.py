from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import config
from screener.loader import load_stock_list
from screener.analyzer import analyze_stock
from services.yahoo_credit_service import load_latest_credit_data

from services.tracking_service import (
    load_tracking,
    update_tracking_results,
    record_initial_move,
)

# ============================================================
# スクリーナー実行
#
# 初動スコア Ver4
#
# コア4条件:
# ・前日比+5%以上       +3
# ・出来高3倍以上       +2
# ・ブレイク            +1
# ・30日高値更新        +1
#
# RSI:
# ・85～89.99           -1
# ・90～94.99           -2
# ・95以上              -3
#
# コア最大7点。
# RSI減点後の「初動スコア」を唯一の評価軸とする。
#
# 強気度は使用しない。
# ============================================================


def run_screener(start=0, limit=None):

    # ========================================================
    # 銘柄一覧取得
    # ========================================================

    stocks = load_stock_list(
        start,
        limit
    )

    # ========================================================
    # 最新Yahoo信用データ読込
    # ========================================================

    credit_map = load_latest_credit_data(
        codes=stocks["コード"].tolist()
    )

    print(
        f"Yahoo信用データ読込 : "
        f"{len(credit_map)}銘柄"
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

        futures = {}

        for _, stock in stocks.iterrows():

            code = str(
                stock["コード"]
            ).replace(
                ".0",
                ""
            ).strip()

            credit_row = credit_map.get(
                code
            )

            futures[
                executor.submit(
                    analyze_stock,
                    stock,
                    None,
                    credit_row
                )
            ] = stock


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

    # ========================================================
    # 初動スコア追跡 Ver2
    # ========================================================

    try:

        tracking_df = load_tracking()

        # 過去の追跡銘柄を更新
        tracking_df = update_tracking_results(
            tracking_df
        )

        # 本日の初動スコアTOP20を登録
        tracking_df = record_initial_move(
            result_df
        )

    except Exception as e:

        print(
            "初動追跡処理 ERROR :",
            e
        )

        return result_df


    # ========================================================
    # 初動スコアで並べ替え
    #
    # Ver4初動スコア
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
    # 「初動スコア7点＋RSI減点」が唯一の評価軸。
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
    # 結果返却
    # ========================================================

    return result_df