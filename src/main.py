from services.screener import load_stock_list

print("=================================")
print(" 日本株スクリーナー Ver1.0")
print("=================================")
print()

stocks = load_stock_list()

print(stocks[["コード", "銘柄名", "市場・商品区分"]])