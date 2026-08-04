from services.screener import run

print("=================================")
print(" 日本株スクリーナー Ver0.5")
print("=================================")
print()

results = run(limit=10)

print()
print("取得結果")
print("---------------------------------")

for item in results:
    print(item)