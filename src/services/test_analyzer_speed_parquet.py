import pandas as pd
import time
import importlib.util

from services.yahoo_service import get_history
from indicators.technical import add_indicators


def load_old_analyzer():

    spec = importlib.util.spec_from_file_location(
        "analyzer_v613",
        "src/screener/analyzer.py"
    )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    return module


def main():

    print("==============================")
    print(" Ver6.13 Parquet対象 analyzer速度計測")
    print("==============================")

    # ==========================
    # Parquetに実際に存在する銘柄を取得
    # ==========================

    parquet_file = (
        "data/cache/_all_cache.parquet"
    )

    codes = (
        pd.read_parquet(
            parquet_file,
            columns=["code"]
        )["code"]
        .astype(str)
        .drop_duplicates()
        .head(100)
        .tolist()
    )

    print(
        f"対象銘柄数: {len(codes)}"
    )

    print()

    # ==========================
    # analyzer読み込み
    # ==========================

    analyzer = load_old_analyzer()

    total_history = 0.0
    total_indicators = 0.0
    total_rest = 0.0

    success = 0

    # ==========================
    # 銘柄ごとに計測
    # ==========================

    for code in codes:

        try:

            # --------------------------
            # get_history
            # --------------------------

            t = time.time()

            df = get_history(
                code,
                period="6mo"
            )

            history_time = (
                time.time() - t
            )

            if df is None or df.empty:

                print(
                    f"取得失敗: {code}"
                )

                continue

            total_history += history_time

            # --------------------------
            # add_indicators
            # --------------------------

            t = time.time()

            df = add_indicators(df)

            indicator_time = (
                time.time() - t
            )

            total_indicators += indicator_time

            # --------------------------
            # 判定・コメント
            # --------------------------

            t = time.time()

            latest = df.iloc[-1]

            analyzer.calculate_initial_score(
                latest
            )

            analyzer.make_comment(
                latest
            )

            rest_time = (
                time.time() - t
            )

            total_rest += rest_time

            success += 1

        except Exception as e:

            print(
                f"ERROR: {code} / {e}"
            )

    # ==========================
    # 結果
    # ==========================

    print()

    print("------------------------------")
    print("計測結果")
    print("------------------------------")

    print(
        f"成功銘柄数 : {success}"
    )

    print(
        f"get_history 合計 : "
        f"{total_history:.4f} 秒"
    )

    print(
        f"add_indicators 合計 : "
        f"{total_indicators:.4f} 秒"
    )

    print(
        f"判定・コメント 合計 : "
        f"{total_rest:.4f} 秒"
    )

    print()

    if success > 0:

        print(
            f"get_history / 銘柄 : "
            f"{total_history / success:.5f} 秒"
        )

        print(
            f"add_indicators / 銘柄 : "
            f"{total_indicators / success:.5f} 秒"
        )

        print(
            f"判定・コメント / 銘柄 : "
            f"{total_rest / success:.5f} 秒"
        )

    print()

    print("==============================")
    print(" Yahoo取得回数は終了時の統計を確認")
    print("==============================")


if __name__ == "__main__":

    main()