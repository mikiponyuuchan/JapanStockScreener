import time
import pandas as pd


from screener.loader import load_stock_list
from screener.analyzer import analyze_stock

from services.result_writer import save_result




def main():


    start_time = time.time()


    print("==============================")
    print(" 日本株スクリーナー Ver3.1 ")
    print("==============================")
    print()



    # ==========================
    # 銘柄取得
    # ==========================

    stocks = load_stock_list()



    results = []



    total = len(stocks)



    # ==========================
    # 分析
    # ==========================

    for i, (_, stock) in enumerate(
        stocks.iterrows(),
        start=1
    ):


        code = stock["コード"]


        print(
            f"[{i}/{total}] {code}"
        )



        try:

            result = analyze_stock(
                stock
            )


            if result is not None:

                results.append(
                    result
                )



        except Exception as e:

            print(
                "ERROR:",
                code,
                e
            )



    print()



    if not results:

        print(
            "分析結果なし"
        )

        return



    # ==========================
    # DataFrame
    # ==========================

    df = pd.DataFrame(
        results
    )



    # ==========================
    # 強気度順
    # ==========================

    df = (
        df
        .sort_values(
            "強気度",
            ascending=False
        )
    )



    # ==========================
    # TOP20
    # ==========================

    top20 = df.head(20)



    print(
        "=== 本日の注目銘柄 TOP20 ==="
    )


    print(
        top20
    )


    print()



    # ==========================
    # 買い候補
    # ==========================

    buy_df = df[
        df["総合判定"]
        ==
        "買い候補"
    ]



    print(
        "=== 買い候補 ==="
    )


    print(
        buy_df
    )


    print()



    # ==========================
    # 保存
    # ==========================

    save_result(
        df
    )



    elapsed = (
        time.time()
        -
        start_time
    )


    print(
        f"処理時間 : {elapsed:.1f} 秒"
    )




if __name__ == "__main__":

    main()