import yfinance as yf
import pandas as pd


checks = [
    ("264A", "Schoo", "2026-08-20"),
    ("3189", "ANAP", "2026-08-20"),
]


result = pd.read_csv(
    "results/2026-08-20_stock_result.csv",
    encoding="utf-8-sig",
    dtype={"コード": str},
)


for code, name, date_text in checks:

    matched = result[
        result["コード"].astype(str) == code
    ]

    print()
    print("=" * 60)
    print(code, name)
    print("=" * 60)

    if matched.empty:
        print("stock_result に銘柄がありません")
        continue

    saved = matched.iloc[0]

    df = yf.download(
        f"{code}.T",
        start="2026-08-20",
        end="2026-08-21",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df.empty:
        print("Yahoo取得なし")
        continue

    # yfinance MultiIndex対策
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    row = df.iloc[0]

    open_price = float(row["Open"])
    high_price = float(row["High"])
    low_price = float(row["Low"])
    close_price = float(row["Close"])

    saved_close = float(saved["終値"])

    print(f"始値             : {open_price:.2f}")
    print(f"高値             : {high_price:.2f}")
    print(f"安値             : {low_price:.2f}")
    print(f"Yahoo終値        : {close_price:.2f}")
    print(f"保存済み確定終値 : {saved_close:.2f}")
    print(
        "終値一致         :",
        abs(close_price - saved_close) < 0.01,
    )