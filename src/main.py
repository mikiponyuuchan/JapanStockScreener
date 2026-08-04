from services.screener import run_screener

print("=================================")
print(" 日本株スクリーナー Ver1.3")
print("=================================")
print()

# 1～10番目
run_screener(start=0, limit=10)

# 例えば101～200番目なら
# run_screener(start=100, limit=100)