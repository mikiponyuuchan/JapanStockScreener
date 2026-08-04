from services.yahoo_service import get_history
from indicators.technical import add_indicators


code = "6549"


df = get_history(code)

df = add_indicators(df)


latest = df.iloc[-1]


check_columns = [
    "RSI",
    "RSI_Strong",
    "RSI_OverBought",
    "ATR",
    "YearHigh",
    "NewYearHigh",
    "VolumeRatio20",
    "BreakoutSignal",
    "BreakoutFirstDay",
]


print("=== Ver3.0 指標確認 ===")


for col in check_columns:

    if col in latest.index:

        print(
            col,
            "OK :",
            latest[col]
        )

    else:

        print(
            col,
            "なし"
        )