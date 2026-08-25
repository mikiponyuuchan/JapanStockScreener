import time
import pandas as pd

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

from screener.loader import load_stock_list
from screener.analyzer import analyze_stock

from services.yahoo_service import _download_history_batch
from services.yahoo_credit_service import load_latest_credit_data
from services.result_writer import save_result


# ==========================================================
# 日本株スクリーナー
# 初動スコア一本化版
#
# ・強気度は使用しない
# ・初動スコアを唯一のランキング軸とする
# ・高騰の初動を捕まえることを目的とする
# ==========================================================


MAX_WORKERS = 12
BATCH_SIZE = 100


def main():

    start_time = time.time()

    print("==============================")
    print(" 日本株スクリーナー")
    print(" 初動スコア一本化版")
    print("==============================")
    print()

    # ==================================================
    # 銘柄一覧取得
    # ==================================================

    stocks = load_stock_list()

    total = len(stocks)

    print(
        f"普通株銘柄数 : {total}"
    )

    print()

    if total == 0:

        print(
            "対象銘柄がありません。"
        )

        return

    # ==================================================
    # コード一覧
    # ==================================================

    codes = [
        str(code)
        for code in stocks["コード"]
    ]

    print(
        f"対象銘柄数 : {len(codes)}"
    )

    # ==================================================
    # Yahoo一括取得
    # ==================================================

    print()
    print(
        "Yahoo一括取得開始..."
    )
    print()

    batch_start = time.time()

    history_map = _download_history_batch(
        codes,
        period="6mo",
        batch_size=BATCH_SIZE
    )

    batch_time = (
        time.time()
        - batch_start
    )

    print()

    print(
        f"一括取得時間 : "
        f"{batch_time:.2f} 秒"
    )

    print(
        f"取得成功銘柄数 : "
        f"{len(history_map)}"
    )

    # ==================================================
    # Yahoo信用データ
    # ==================================================

    print()
    print(
        "Yahoo信用データ読み込み開始..."
    )
    print()

    # ????????????????
    # ?????TOP20????
    # result_writer.py ?????????????
    credit_map = {}

    print(
        f"Yahoo信用データ : "
        f"{len(credit_map)}銘柄"
    )

    # ==================================================
    # 分析開始
    # ==================================================

    print()
    print(
        "分析開始..."
    )
    print()

    analysis_start = time.time()

    results = []

    error_count = 0
    skip_count = 0
    completed = 0

    # ==================================================
    # 並列分析
    # ==================================================

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {}

        for _, stock in stocks.iterrows():

            code = str(
                stock["コード"]
            )

            history_df = (
                history_map.get(code)
            )

            # ------------------------------------------
            # 履歴データなし
            # ------------------------------------------

            if (
                history_df is None
                or history_df.empty
            ):

                skip_count += 1

                print(
                    f"SKIP {code} : "
                    f"履歴データなし"
                )

                continue

            # ------------------------------------------
            # 信用データ
            # ------------------------------------------

            credit_row = credit_map.get(
                code
            )

            future = executor.submit(
                analyze_stock,
                stock,
                history_df=history_df,
                credit_row=credit_row
            )

            futures[future] = stock

        # ==================================================
        # 分析結果回収
        # ==================================================

        for future in as_completed(
            futures
        ):

            stock = futures[future]

            code = str(
                stock["コード"]
            )

            completed += 1

            try:

                result = future.result()

                if result is not None:

                    results.append(
                        result
                    )

                    
            except Exception as e:

                error_count += 1

                print(
                    f"[{completed}/"
                    f"{len(futures)}] "
                    f"ERROR {code} : {e}"
                )

            if (
                completed % 1000 == 0
                or completed == len(futures)
            ):
                print(
                    f"進捗 : {completed} / {len(futures)}"
                )

    analysis_time = (
        time.time()
        - analysis_start
    )

    print()

    # ==================================================
    # 分析結果なし
    # ==================================================

    if not results:

        print(
            "分析結果がありません。"
        )

        return

    # ==================================================
    # DataFrame
    # ==================================================

    df = pd.DataFrame(
        results
    )

    # ==================================================
    # 初動スコア確認
    # ==================================================

    if "初動スコア" not in df.columns:

        print()
        print(
            "=============================================="
        )
        print(
            "ERROR : 初動スコア列がありません"
        )
        print(
            "analyzer.py の戻り値を確認してください。"
        )
        print(
            "=============================================="
        )
        print()

        print(
            "現在の列:"
        )

        print(
            list(df.columns)
        )

        return

    # ==================================================
    # 初動スコア順
    #
    # 今回からランキング軸は初動スコア一本
    # ==================================================

    df["初動スコア"] = pd.to_numeric(
        df["初動スコア"],
        errors="coerce"
    ).fillna(0)

    sort_columns = [
        "初動スコア"
    ]

    ascending = [
        False
    ]

    # コードが存在する場合は同点時の並びに使用
    if "コード" in df.columns:

        sort_columns.append(
            "コード"
        )

        ascending.append(
            True
        )

    df = df.sort_values(
        sort_columns,
        ascending=ascending
    ).reset_index(
        drop=True
    )

    # ==================================================
    # 内部計測列を非表示
    # ==================================================

    display_df = df.drop(
        columns=[
            "_data_time",
            "_indicator_time",
            "_judge_time"
        ],
        errors="ignore"
    )

    # ==================================================
    # TOP20
    # ==================================================

    top20 = (
        display_df
        .head(20)
        .copy()
    )

    # ==================================================
    # 再発監視
    # ==================================================

    close_nan_count = 0

    if "終値" in df.columns:

        close_nan_count = (
            pd.to_numeric(
                df["終値"],
                errors="coerce"
            )
            .isna()
            .sum()
        )

    print()
    print(
        "=============================="
    )
    print(
        " 再発監視"
    )
    print(
        "=============================="
    )

    print(
        f"終値欠損銘柄数 : "
        f"{close_nan_count}"
    )

    if close_nan_count > 0:

        print(
            "WARNING : "
            "終値が欠損している銘柄があります。"
        )

    else:

        print(
            "終値データ正常"
        )

    print(
        "=============================="
    )
    print()

    # ==================================================
    # 保存
    # ==================================================

    save_start = time.time()

    save_result(
        df
    )

    save_time = (
        time.time()
        - save_start
    )

    # ==================================================
    # Sprint計測
    # ==================================================

    data_total = (
        df["_data_time"]
        .sum()
        if "_data_time" in df.columns
        else 0
    )

    indicator_total = (
        df["_indicator_time"]
        .sum()
        if "_indicator_time" in df.columns
        else 0
    )

    judge_total = (
        df["_judge_time"]
        .sum()
        if "_judge_time" in df.columns
        else 0
    )

    total_time = (
        time.time()
        - start_time
    )

    # ==================================================
    # 結果表示
    # ==================================================

    print()
    print("==============================")
    print(" RESULT")
    print("==============================")

    print(
        f"対象銘柄数           : "
        f"{total}"
    )

    print(
        f"Yahoo取得成功銘柄数 : "
        f"{len(history_map)}"
    )

    print(
        f"分析対象銘柄数       : "
        f"{len(futures)}"
    )

    print(
        f"分析成功             : "
        f"{len(results)}"
    )

    print(
        f"分析スキップ         : "
        f"{skip_count}"
    )

    print(
        f"分析エラー           : "
        f"{error_count}"
    )

    print()

    print(
        f"Yahoo一括取得        : "
        f"{batch_time:.1f} 秒"
    )

    print(
        f"データ取得時間       : "
        f"{data_total:.1f} 秒"
    )

    print(
        f"指標計算時間         : "
        f"{indicator_total:.1f} 秒"
    )

    print(
        f"判定時間             : "
        f"{judge_total:.1f} 秒"
    )

    print(
        f"保存時間             : "
        f"{save_time:.1f} 秒"
    )

    print(
        f"分析時間             : "
        f"{analysis_time:.1f} 秒"
    )

    print(
        f"合計時間             : "
        f"{total_time:.1f} 秒"
    )

    print()

    print(
        f"初動スコアTOP20      : "
        f"{len(top20)} 銘柄"
    )

    print()

    # ==================================================
    # 初動スコア分布
    # ==================================================

    if not top20.empty:

        max_score = top20[
            "初動スコア"
        ].max()

        min_score = top20[
            "初動スコア"
        ].min()

        print(
            f"TOP20最高初動スコア : "
            f"{max_score}"
        )

        print(
            f"TOP20最低初動スコア : "
            f"{min_score}"
        )

    print()

    print("==============================")
    print(" 完了")
    print("==============================")


if __name__ == "__main__":
    main()