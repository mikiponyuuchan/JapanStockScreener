import time
import pandas as pd

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

from services.yahoo_service import get_history
from indicators.technical import add_indicators


PARQUET_FILE = "data/cache/_all_cache.parquet"

MAX_WORKERS = 12


def load_codes():

    df = pd.read_parquet(
        PARQUET_FILE,
        columns=["code"]
    )

    codes = (
        df["code"]
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    return codes


def analyze_one(code):

    total_start = time.time()

    # ==========================
    # データ取得
    # ==========================

    start = time.time()

    df = get_history(
        code,
        period="6mo"
    )

    data_time = (
        time.time()
        - start
    )

    if df is None or df.empty:

        return {
            "code": code,
            "success": False,
            "data_time": data_time,
            "indicator_time": 0.0,
            "total_time": time.time() - total_start
        }

    # ==========================
    # 指標計算
    # ==========================

    start = time.time()

    df = add_indicators(df)

    indicator_time = (
        time.time()
        - start
    )

    # ==========================
    # 最終行取得
    # ==========================

    latest = df.iloc[-1]

    # 最低限の参照
    # 本番analyzerで使用する代表的な列を確認
    _ = latest["Close"]
    _ = latest["MA5"]
    _ = latest["MA25"]
    _ = latest["RSI"]

    total_time = (
        time.time()
        - total_start
    )

    return {
        "code": code,
        "success": True,
        "data_time": data_time,
        "indicator_time": indicator_time,
        "total_time": total_time
    }


def main():

    print("==============================")
    print(" Ver6.13 Parquet 12スレッド")
    print(" 全銘柄 analyzer速度計測")
    print("==============================")
    print()

    # ==========================
    # 銘柄取得
    # ==========================

    start = time.time()

    codes = load_codes()

    load_time = (
        time.time()
        - start
    )

    print(
        f"対象銘柄数 : {len(codes)}"
    )

    print(
        f"銘柄読込時間 : {load_time:.4f} 秒"
    )

    print(
        f"スレッド数   : {MAX_WORKERS}"
    )

    print()

    # ==========================
    # 並列処理
    # ==========================

    results = []

    analysis_start = time.time()

    completed = 0
    total = len(codes)

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(
                analyze_one,
                code
            ): code
            for code in codes
        }

        for future in as_completed(
            futures
        ):

            code = futures[future]

            try:

                result = future.result()

                results.append(
                    result
                )

            except Exception as e:

                print(
                    f"ERROR: {code} / {e}"
                )

            completed += 1

            if (
                completed % 500 == 0
                or completed == total
            ):

                elapsed = (
                    time.time()
                    - analysis_start
                )

                print(
                    f"[{completed}/{total}] "
                    f"{completed / total * 100:5.1f}% "
                    f"経過 {elapsed:7.1f} 秒"
                )

    analysis_time = (
        time.time()
        - analysis_start
    )

    # ==========================
    # 集計
    # ==========================

    result_df = pd.DataFrame(
        results
    )

    success_df = result_df[
        result_df["success"]
    ]

    failed_df = result_df[
        ~result_df["success"]
    ]

    data_total = (
        success_df["data_time"]
        .sum()
    )

    indicator_total = (
        success_df["indicator_time"]
        .sum()
    )

    total_sum = (
        success_df["total_time"]
        .sum()
    )

    # ==========================
    # 結果
    # ==========================

    print()

    print("==============================")
    print(" 計測結果")
    print("==============================")

    print(
        f"対象銘柄数       : {total}"
    )

    print(
        f"成功銘柄数       : {len(success_df)}"
    )

    print(
        f"失敗銘柄数       : {len(failed_df)}"
    )

    print()

    print(
        f"get_history 累計 : "
        f"{data_total:.2f} 秒"
    )

    print(
        f"指標計算 累計    : "
        f"{indicator_total:.2f} 秒"
    )

    print(
        f"1銘柄処理時間累計: "
        f"{total_sum:.2f} 秒"
    )

    print()

    if len(success_df) > 0:

        print(
            f"get_history / 銘柄 : "
            f"{data_total / len(success_df):.5f} 秒"
        )

        print(
            f"指標計算 / 銘柄    : "
            f"{indicator_total / len(success_df):.5f} 秒"
        )

    print()

    print(
        f"実時間           : "
        f"{analysis_time:.2f} 秒"
    )

    print()

    print(
        "=============================="
    )

    print(
        " 重要：Yahoo取得回数"
    )

    print(
        "終了時のVer6.9統計を確認してください"
    )

    print(
        "=============================="
    )


if __name__ == "__main__":

    main()