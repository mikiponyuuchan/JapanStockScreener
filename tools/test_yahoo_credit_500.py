import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from services.yahoo_credit_service import get_credit_history


# ============================================================
# 設定
# ============================================================

STOCK_LIST = Path("data/jpx_stock_list.xls")

TEST_COUNT = 500


# ============================================================
# テスト対象コード取得
# ============================================================

def load_test_codes():

    df = pd.read_excel(
        STOCK_LIST
    )

    code_column = None

    for column in df.columns:

        if "コード" in str(column):

            code_column = column
            break

    if code_column is None:

        raise RuntimeError(
            "コード列が見つかりません"
        )

    print(
        f"コード列 : {code_column}"
    )

    codes = (
        df[code_column]
        .dropna()
        .astype(str)
        .str.replace(
            r"\.0$",
            "",
            regex=True
        )
        .str.strip()
        .tolist()
    )

    codes = [
        code
        for code in codes
        if len(code) == 4
        and code.isdigit()
    ]

    return codes[:TEST_COUNT]


# ============================================================
# メイン
# ============================================================

def main():

    print("=" * 60)
    print("Yahoo!ファイナンス 信用残 100銘柄テスト")
    print("=" * 60)
    print()

    codes = load_test_codes()

    print(
        f"テスト対象銘柄数 : {len(codes)}"
    )
    print()

    success = 0
    failed = 0
    credit_count = 0

    results = []

    start_all = time.perf_counter()

    for index, code in enumerate(
        codes,
        1
    ):

        start = time.perf_counter()

        print(
            f"[{index:3}/{len(codes)}] "
            f"{code} 取得中...",
            end=" ",
            flush=True
        )

        try:

            df = get_credit_history(
                code
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            if df is not None and not df.empty:

                success += 1
                credit_count += len(df)

                results.append(
                    df
                )

                print(
                    f"成功 {len(df)}件 "
                    f"({elapsed:.2f}秒)"
                )

            else:

                failed += 1

                print(
                    f"信用データなし "
                    f"({elapsed:.2f}秒)"
                )

        except Exception as e:

            failed += 1

            elapsed = (
                time.perf_counter()
                - start
            )

            print(
                f"エラー: {e} "
                f"({elapsed:.2f}秒)"
            )

    total_elapsed = (
        time.perf_counter()
        - start_all
    )

    # ========================================================
    # 結果表示
    # ========================================================

    print()
    print("=" * 60)
    print("テスト結果")
    print("=" * 60)

    print(
        f"対象銘柄数       : {len(codes)}"
    )

    print(
        f"信用データ取得成功: {success}"
    )

    print(
        f"信用データなし    : {failed}"
    )

    if codes:

        success_rate = (
            success
            / len(codes)
            * 100
        )

    else:

        success_rate = 0

    print(
        f"成功率            : "
        f"{success_rate:.1f}%"
    )

    print(
        f"合計時間          : "
        f"{total_elapsed:.1f} 秒"
    )

    print(
        f"平均時間          : "
        f"{total_elapsed / len(codes):.2f} 秒/銘柄"
        if codes
        else "平均時間          : 0 秒/銘柄"
    )

    print()

    # ========================================================
    # 結果保存
    # ========================================================

    if results:

        result_df = pd.concat(
            results,
            ignore_index=True
        )

        output_path = (
            Path("data/yahoo_credit")
            / "test_100_result.csv"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        result_df.to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig"
        )

        print(
            f"取得した信用残行数 : "
            f"{len(result_df)}"
        )

        print()

        print("取得例")
        print("-" * 60)

        print(
            result_df.head(10).to_string(
                index=False
            )
        )

        print()

        print(
            f"保存先 : {output_path}"
        )

    else:

        print(
            "信用データは1件も取得できませんでした。"
        )


# ============================================================
# 実行
# ============================================================

if __name__ == "__main__":
    main()