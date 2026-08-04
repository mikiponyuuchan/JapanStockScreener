from services.screener import run

print("=================================")
print(" 日本株スクリーナー Ver0.6")
print("=================================")
print()

df = run(limit=10)

print()
print(df)