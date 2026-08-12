import sys
import time

sys.path.insert(0, "src")

from screener.loader import load_stock_list
from screener.analyzer import analyze_stock
from services.yahoo_service import _download_history_batch


print("==============================")
print(" Ver6.15 Step2-2 TEST")
print("==============================")

stocks = load_stock_list(
    start=0,
    limit=10
)

codes = [
    str(code)
    for code in stocks["コード"]
]

print()
print(f"対象銘柄数 : {len(codes)}")
print(f"コード     : {codes}")

print()
print("Yahoo一括取得開始...")

start_time = time.time()

history_map = _download_history_batch(
    codes,
    period="10d",
    batch_size=100
)

batch_time = time.time() - start_time

print()
print(f"一括取得時間 : {batch_time:.2f} 秒")
print(f"取得銘柄数   : {len(history_map)}")

print()
print("analyze_stock 接続テスト開始...")

results = []
error_count = 0

for _, stock in stocks.iterrows():

    code = str(stock["コード"])

    history_df = history_map.get(code)

    if history_df is None or history_df.empty:

        print(
            f"SKIP {code} : 履歴データなし"
        )

        continue

    try:

        result = analyze_stock(
            stock,
            history_df=history_df
        )

        if result is not None:

            results.append(result)

            print(
                f"OK   {code} : "
                f"{result['終値']} / "
                f"強気度={result['強気度']}"
            )

        else:

            print(
                f"NONE {code}"
            )

    except Exception as e:

        error_count += 1

        print(
            f"ERROR {code} : {e}"
        )

print()
print("==============================")
print(" TEST RESULT")
print("==============================")

print(
    f"Yahoo取得銘柄数 : {len(history_map)}"
)

print(
    f"分析成功         : {len(results)}"
)

print(
    f"分析エラー       : {error_count}"
)

print(
    f"一括取得時間     : {batch_time:.2f} 秒"
)

print(
    f"分析結果          : {len(results)} 件"
)

if results:

    print()
    print("=== 分析結果 ===")

    for result in results:

        print(
            result["コード"],
            result["終値"],
            result["強気度"],
            result["監視ランク"]
        )
