import time
from pathlib import Path

import pandas as pd


CACHE_FILE = Path("data/cache/_all_cache.parquet")


def get_history_from_parquet(code: str):

    start = time.time()

    if not CACHE_FILE.exists():
        print("統合キャッシュがありません")
        return None

    df = pd.read_parquet(
        CACHE_FILE
    )

    read_time = time.time() - start

    code = str(code)

    if "code" not in df.columns:
        print("code列がありません")
        print("列:", list(df.columns))
        return None

    df["code"] = df["code"].astype(str)

    result = df[
        df["code"] == code
    ].copy()

    result = result.sort_values(
        "Date"
    )

    print(
        f"Parquet全体読込 : {read_time:.4f} 秒"
    )

    print(
        f"銘柄コード       : {code}"
    )

    print(
        f"取得行数         : {len(result)}"
    )

    if not result.empty:

        print(
            f"最古日           : "
            f"{result['Date'].min()}"
        )

        print(
            f"最新日           : "
            f"{result['Date'].max()}"
        )

    return result


if __name__ == "__main__":

    print("==============================")
    print(" Ver6.10 統合キャッシュ読込テスト")
    print("==============================")

    df = get_history_from_parquet(
        "1301"
    )

    if df is not None and not df.empty:

        print()
        print("テスト成功")

        print()
        print(df.tail())

    else:

        print()
        print("テスト失敗")
