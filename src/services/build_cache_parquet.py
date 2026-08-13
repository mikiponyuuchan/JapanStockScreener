from pathlib import Path
import os
import time

import pandas as pd


# ==========================
# Ver6.10 統合キャッシュ
# ==========================

CACHE_DIR = Path("data/cache")

PARQUET_FILE = (
    CACHE_DIR / "_all_cache.parquet"
)


def build_parquet_cache():

    start_time = time.time()

    print()
    print("==============================")
    print(" Ver6.10 統合キャッシュ作成")
    print("==============================")

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    csv_files = sorted(
        CACHE_DIR.glob("*.csv")
    )

    print(
        f"CSVファイル数 : {len(csv_files)}"
    )

    if not csv_files:

        print(
            "CSVキャッシュがありません。"
        )

        return False

    dfs = []

    read_start = time.time()

    for i, csv_file in enumerate(
        csv_files,
        start=1
    ):

        try:

            df = pd.read_csv(
                csv_file,
                parse_dates=["Date"]
            )

            if "Date" not in df.columns:
                continue

  
            df["_data_date"] = df["Date"].dt.strftime("%Y-%m-%d")

            code = (
                csv_file.stem
            )

            df["code"] = code

            dfs.append(df)


        except Exception as e:

            print(
                f"読み込み失敗: "
                f"{csv_file.name} "
                f"({e})"
            )

        if i % 500 == 0:

            print(
                f"読み込み: "
                f"{i}/{len(csv_files)}"
            )

    read_time = (
        time.time()
        - read_start
    )

    if not dfs:

        print(
            "有効なCSVデータがありません。"
        )

        return False

    print(
        f"CSV読み込み時間 : "
        f"{read_time:.2f} 秒"
    )

    # ==========================
    # 統合
    # ==========================

    concat_start = time.time()

    all_df = pd.concat(
        dfs,
        ignore_index=True
    )

    concat_time = (
        time.time()
        - concat_start
    )

    # ==========================
    # Date整理
    # ==========================

    all_df["Date"] = pd.to_datetime(
        all_df["Date"],
        errors="coerce"
    )

    all_df = (
        all_df
        .dropna(subset=["Date"])
        .sort_values(
            ["code", "Date"]
        )
        .drop_duplicates(
            subset=["code", "Date"],
            keep="last"
        )
        .reset_index(drop=True)
    )

    # ==========================
    # Parquet保存
    # ==========================

    save_start = time.time()

    all_df.to_parquet(
        PARQUET_FILE,
        index=False
    )

    save_time = (
        time.time()
        - save_start
    )

    total_time = (
        time.time()
        - start_time
    )

    file_size_mb = (
        os.path.getsize(
            PARQUET_FILE
        )
        / 1024
        / 1024
    )

    print()
    print(
        f"統合行数       : "
        f"{len(all_df):,}"
    )

    print(
        f"銘柄数         : "
        f"{all_df['code'].nunique():,}"
    )

    print(
        f"統合時間       : "
        f"{concat_time:.2f} 秒"
    )

    print(
        f"Parquet保存時間 : "
        f"{save_time:.2f} 秒"
    )
    
    print(
        f"ファイルサイズ : "
        f"{file_size_mb:.2f} MB"
    )

    print(
        f"合計時間       : "
        f"{total_time:.2f} 秒"
    )

    print()
    print(
        f"保存先 : {PARQUET_FILE}"
    )

    print("==============================")
    print()

    return True


if __name__ == "__main__":

    build_parquet_cache()