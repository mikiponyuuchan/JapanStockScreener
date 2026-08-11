import time
import pandas as pd

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

from screener.loader import load_stock_list
from screener.analyzer import analyze_stock

from services.result_writer import save_result


def main():

    start_time = time.time()

    print("==============================")
    print(" 日本株スクリーナー Ver5.3 ")
    print("==============================")
    print()

    # ==========================
    # 銘柄取得
    # ==========================

    stocks = load_stock_list()

    total = len(stocks)

    results = []
    analysis_start = time.time()

    # ==========================
    # 並列分析開始
    # ==========================

    print(f"{total}銘柄を並列分析中...")
    print()

    completed = 0

    with ThreadPoolExecutor(max_workers=12) as executor:

        futures = {}

        for _, stock in stocks.iterrows():

            future = executor.submit(
                analyze_stock,
                stock
            )

            futures[future] = stock

        # ------- 続きは後半 -------

        for future in as_completed(futures):

            stock = futures[future]
            code = stock["コード"]

            completed += 1

            try:

                result = future.result()

                if result is not None:
                    results.append(result)

            except Exception as e:

                print(f"ERROR: {code} {e}")


            # --------------------------
            # 進捗表示（20銘柄ごと）
            # --------------------------

            percent = completed / total * 100

            elapsed = time.time() - start_time

            if completed > 0:

                remain = (
                    elapsed / completed
                ) * (total - completed)

            else:

                remain = 0

            if completed % 20 == 0 or completed == total:

                print(
                    f"[{completed}/{total}] "
                    f"{percent:5.1f}% "
                    f"残り約 {remain:5.0f} 秒",
                    end="\r"
                )

    print()
    print()

    if not results:

        print("分析結果なし")
        return
    analysis_end = time.time()

    analysis_time = (
        analysis_end
        - analysis_start
    )

    # ==========================
    # DataFrame
    # ==========================

    df = pd.DataFrame(results)

    df = df.sort_values(
        "強気度",
        ascending=False
    )

    # ==========================
    # 内部計測列を非表示
    # ==========================

    display_df = df.drop(
        columns=[
            "_data_time",
            "_indicator_time",
            "_judge_time"
        ],
        errors="ignore"
    )

    # ==========================
    # TOP20
    # ==========================

    top20 = display_df.head(20)


    # ==========================
    # 買い候補
    # ==========================

    buy_df = display_df[
        display_df["総合判定"] == "買い候補"
    ]


    # ==========================
    # 保存
    # ==========================

# ==========================
# 保存時間計測
# ==========================

    save_start = time.time()

    save_result(df)

    save_end = time.time()


    # ==========================
    # Sprint2 時間集計
    # ==========================

    data_total = (
        df["_data_time"]
        .sum()
    )


    indicator_total = (
        df["_indicator_time"]
        .sum()
    )


    judge_total = (
        df["_judge_time"]
        .sum()
    )


    total_time = (
        time.time()
        -
        start_time
    )


    print()

    print("==============================")
    print(" 処理時間内訳 ")
    print("==============================")

    print(
        f"データ取得      : {data_total:6.1f} 秒"
    )

    print(
        f"指標計算        : {indicator_total:6.1f} 秒"
    )

    print(
        f"判定作成        : {judge_total:6.1f} 秒"
    )

    print(
        f"保存            : {save_end - save_start:6.1f} 秒"
    )

    print(
        f"分析処理（実時間）: {analysis_time:6.1f} 秒"
    )

    print()

    print(
        f"合計            : {total_time:6.1f} 秒"
    )


if __name__ == "__main__":
    main()