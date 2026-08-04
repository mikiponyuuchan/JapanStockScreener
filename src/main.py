from services.yahoo_service import get_history

print("=================================")
print(" 日本株スクリーナー Ver0.8")
print("=================================")
print()

df = get_history("7203")

print(df)