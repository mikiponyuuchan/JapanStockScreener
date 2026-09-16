from pathlib import Path

path = Path(
    "tools/analyze_earnings_next_day.py"
)

text = path.read_text(
    encoding="utf-8"
)

backup = Path(
    "tools/"
    "analyze_earnings_next_day_before_future_guard.py"
)

backup.write_text(
    text,
    encoding="utf-8"
)

needle = '''    print(
        "Candidates     :",
        len(target),
    )

    results = []
'''

replacement = '''    print(
        "Candidates     :",
        len(target),
    )

    today = pd.Timestamp.now(
        tz="Asia/Tokyo"
    ).date()

    if trade_date > today:
        print()
        print(
            "NOT READY :",
            trade_date,
            "is a future trading day.",
        )
        print(
            "Run this tool after",
            trade_date,
            "market data becomes available.",
        )
        return

    results = []
'''

if needle not in text:
    raise RuntimeError(
        "Patch target not found"
    )

text = text.replace(
    needle,
    replacement,
    1,
)

path.write_text(
    text,
    encoding="utf-8"
)

print("PATCHED :", path)
print("BACKUP  :", backup)
