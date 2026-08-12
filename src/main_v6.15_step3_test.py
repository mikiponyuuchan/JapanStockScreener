import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

from screener.loader import load_stock_list
from screener.analyzer import analyze_stock
from services.yahoo_service import _download_history_batch


# ==========================
# Ver6.15 Step3 TEST
# ==========================

TEST_LIMIT = 10
BATCH_SIZE = 100
MAX_WORKERS = 12


def main():

    start_time = time.time()

    print("==============================")
    print(" 日本株スクリーナー Ver6.15 Step3 TEST")
    print("==============================")
    print()

    # ==========================
    # 銘柄一覧
    # ==========================

    stocks = load_stock_list(
        start=0,
        limit=TEST_LIMIT
    )

    total = len(stocks)

    print(
        f"対象銘柄数 : {total}"
    )

    if total == 0:

        print(
            "対象銘柄がありません。"
        )

        return

    codes = [
        str(code)
        for code in stocks["コード"]
    ]

    print(
        f"コード : {codes}"
    )

    print()

    # ==========================
    # Yahoo一括取得
    # ==========================

    print(
        "Yahoo一括取得開始..."
    )

    batch_start = time.time()

    history_map = _download_history_batch(
        codes,
        period="10d",
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
        f"取得銘柄数   : "
        f"{len(history_map)}"
    )

    # ==========================
    # 分析
    # ==========================

    print()
    print(
        "分析開始..."
    )
    print()

    analysis_start = time.time()

    results = []

    completed = 0
    error_count = 0

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

            if (
                history_df is None
                or history_df.empty
            ):

                print(
                    f"SKIP {code} : "
                    "履歴データなし"
                )

                continue

            future = executor.submit(
                analyze_stock,
                stock,
                history_df
            )

            futures[future] = stock

        # ==========================
        # 分析結果回収
        # ==========================

        for future in as_completed(
            futures
        ):

            stock = futures[future]

            code = str(
                stock["コード"]
            )

            completed += 1

            try:

                result = (
                    future.result()
                )

                if result is not None:

                    results.append(
                        result
                    )

                    print(
                        f"[{completed}/"
                        f"{len(futures)}] "
                        f"OK {code} : "
                        f"終値={result['終値']} "
                        f"強気度={result['強気度']}"
                    )

                else:

                    print(
                        f"[{completed}/"
                        f"{len(futures)}] "
                        f"NONE {code}"
                    )

            except Exception as e:

                error_count += 1

                print(
                    f"[{completed}/"
                    f"{len(futures)}] "
                    f"ERROR {code} : {e}"
                )

    analysis_time = (
        time.time()
        - analysis_start
    )

    total_time = (
        time.time()
        - start_time
    )

    # ==========================
    # 結果
    # ==========================

    print()
    print("==============================")
    print(" Ver6.15 Step3 TEST RESULT")
    print("==============================")

    print(
        f"対象銘柄数       : {total}"
    )

    print(
        f"Yahoo取得銘柄数  : "
        f"{len(history_map)}"
    )

    print(
        f"分析対象銘柄数   : "
        f"{len(futures)}"
    )

    print(
        f"分析成功         : "
        f"{len(results)}"
    )

    print(
        f"分析エラー       : "
        f"{error_count}"
    )

    print(
        f"Yahoo一括取得    : "
        f"{batch_time:.2f} 秒"
    )

    print(
        f"分析時間         : "
        f"{analysis_time:.2f} 秒"
    )

    print(
        f"合計時間         : "
        f"{total_time:.2f} 秒"
    )

    # ==========================
    # 結果一覧
    # ==========================

    if results:

        print()
        print(
            "=== 分析結果 ==="
        )

        for result in results:

            print(
                result["コード"],
                result["終値"],
                result["強気度"],
                result["監視ランク"]
            )


if __name__ == "__main__":
    main()