import time
import pandas as pd
import yfinance as yf


PARQUET_FILE = "data/cache/_all_cache.parquet"

TEST_COUNT = 100


def load_codes():

    df = pd.read_parquet(
        PARQUET_FILE,
        columns=["code"]
    )

    return (
        df["code"]
        .astype(str)
        .drop_duplicates()
        .head(TEST_COUNT)
        .tolist()
    )


def convert_one_ticker(
    raw_df,
    code
):

    ticker = f"{code}.T"

    if raw_df is None or raw_df.empty:
        return None

    try:

        # MultiIndex:
        # (ticker, field)
        if isinstance(
            raw_df.columns,
            pd.MultiIndex
        ):

            if ticker not in raw_df.columns.get_level_values(0):
                return None

            df = raw_df[ticker].copy()

        else:

            df = raw_df.copy()

        if df.empty:
            return None

        df = df.reset_index()

        # Date
        if "Date" not in df.columns:
            return None

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        if getattr(
            df["Date"].dt,
            "tz",
            None
        ) is not None:

            df["Date"] = (
                df["Date"]
                .dt.tz_localize(None)
            )

        df = df.dropna(
            subset=["Date"]
        )

        # 現在のParquetと同じ9列へ変換
        result = pd.DataFrame()

        result["Date"] = df["Date"]

        for column in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]:

            if column in df.columns:
                result[column] = df[column]

            else:
                result[column] = pd.NA

        # 現在のParquet構造を維持
        result["Dividends"] = 0.0
        result["Stock Splits"] = 0.0
        result["code"] = str(code)

        result = result[
            [
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "Dividends",
                "Stock Splits",
                "code"
            ]
        ]

        return result

    except Exception as e:

        print(
            f"変換ERROR: {code} / {e}"
        )

        return None


def main():

    print("==============================")
    print(" Ver6.15 Yahoo 10d一括取得テスト")
    print("==============================")

    codes = load_codes()

    tickers = [
        f"{code}.T"
        for code in codes
    ]

    print(
        f"対象銘柄数: {len(codes)}"
    )

    print()

    # ==========================
    # Yahoo一括取得
    # ==========================

    start_time = time.time()

    raw_df = yf.download(
        tickers=tickers,
        period="10d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True
    )

    yahoo_time = (
        time.time()
        - start_time
    )

    print(
        f"Yahoo一括取得時間: "
        f"{yahoo_time:.4f} 秒"
    )

    print(
        f"取得行数: {len(raw_df)}"
    )

    print(
        f"取得列数: {len(raw_df.columns)}"
    )

    print()

    # ==========================
    # 銘柄ごとに変換
    # ==========================

    start_time = time.time()

    results = []

    for code in codes:

        df = convert_one_ticker(
            raw_df,
            code
        )

        if (
            df is not None
            and not df.empty
        ):

            results.append(df)

    convert_time = (
        time.time()
        - start_time
    )

    # ==========================
    # 結果確認
    # ==========================

    if results:

        result_df = pd.concat(
            results,
            ignore_index=True
        )

    else:

        result_df = pd.DataFrame()

    success_codes = (
        result_df["code"]
        .astype(str)
        .nunique()
        if not result_df.empty
        else 0
    )

    print()
    print("------------------------------")
    print("変換結果")
    print("------------------------------")

    print(
        f"成功銘柄数 : {success_codes}"
    )

    print(
        f"失敗銘柄数 : "
        f"{len(codes) - success_codes}"
    )

    print(
        f"変換時間   : "
        f"{convert_time:.4f} 秒"
    )

    print(
        f"変換後行数 : "
        f"{len(result_df)}"
    )

    print(
        f"変換後列数 : "
        f"{len(result_df.columns)}"
    )

    if not result_df.empty:

        print(
            f"列: {result_df.columns.tolist()}"
        )

        print()

        print(
            "先頭5行:"
        )

        print(
            result_df.head()
        )

        print()

        print(
            "最新日:"
        )

        print(
            result_df["Date"].max()
        )

    print()
    print("==============================")
    print(" ※ Parquetへの保存はしていません")
    print("==============================")


if __name__ == "__main__":

    main()
