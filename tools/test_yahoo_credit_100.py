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

TEST_COUNT = 100


# ============================================================
# 銘柄コード取得
# ============================================================

def load_test_codes():

    df = pd.read_excel(
        STOCK_LIST
    )

    # ========================================================
    # コード列を探す
    # 日本語の列名に依存しない
    # ========================================================

    code_column = None

    for column in df.columns:

        values = (
            df[column]
            .dropna()
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

        # 4桁コードが一定数含まれる列をコード列と判断
        valid_count = values.str.fullmatch(r"\d{4}").sum()

        if valid_count >= 100:

            code_column = column
            break

    if code_column is None:

        raise RuntimeError(
            "4桁の銘柄コード列が見つかりません"
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
    )

    codes = [
        code
        for code in codes
        if len(code) == 4 and code.isdigit()
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
        f"テスト銘柄数 : {len(codes)}"
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
                credit_count += 1

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
                f"エラー "
                f"({elapsed:.2f}秒)"
            )

            print(
                f"       {type(e).__name__}: {e}"
            )

    total_time = (
        time.perf_counter()
        - start_all
    )

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

    print(
        f"成功率            : "
        f"{success / len(codes) * 100:.1f}%"
    )

    print(
        f"合計時間          : "
        f"{total_time:.1f} 秒"
    )

    print(
        f"平均時間          : "
        f"{total_time / len(codes):.2f} 秒/銘柄"
    )

    print()

    if results:

        all_df = pd.concat(
            results,
            ignore_index=True
        )

        print(
            f"取得した信用残行数 : "
            f"{len(all_df)}"
        )

        print()

        print("取得例")
        print("-" * 60)

        print(
            all_df.head(10).to_string(
                index=False
            )
        )

        print()

        output = Path(
            "data/yahoo_credit/"
            "test_100_result.csv"
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        all_df.to_csv(
            output,
            index=False,
            encoding="utf-8-sig"
        )

        print(
            f"保存先 : {output}"
        )


if __name__ == "__main__":
    main()