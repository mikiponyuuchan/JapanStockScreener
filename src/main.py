from services.yahoo_service import get_price

print("=================================")
print(" 日本株スクリーナー Ver0.4")
print("=================================")
print()

price = get_price("7203")

print(price)