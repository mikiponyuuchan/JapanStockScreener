from services.yahoo_service import get_history
from indicators.technical import add_indicators

print("=================================")
print(" 日本株スクリーナー Ver0.9")
print("=================================")
print()

df = get_history("7203")

df = add_indicators(df)

print(df.tail())