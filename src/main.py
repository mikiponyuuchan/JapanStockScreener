import time

from screener.runner import run_screener

print("=================================")
print(" 日本株スクリーナー Ver1.6")
print("=================================")
print()

start_time = time.time()

run_screener(
    start=0,
    limit=100
)

elapsed = time.time() - start_time

print()
print(f"処理時間 : {elapsed:.1f} 秒")