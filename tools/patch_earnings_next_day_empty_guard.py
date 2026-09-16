from pathlib import Path

path = Path(
    "tools/analyze_earnings_next_day.py"
)

text = path.read_text(
    encoding="utf-8"
)

backup = Path(
    "tools/analyze_earnings_next_day_before_empty_guard.py"
)

backup.write_text(
    text,
    encoding="utf-8"
)

needle = '''    df = pd.read_excel(
        input_path
    )

    #
    # Use column positions to avoid
'''

replacement = '''    df = pd.read_excel(
        input_path
    )

    if df.empty or len(df.columns) == 0:
        print(
            "=" * 74
        )
        print(
            "EARNINGS NEXT-DAY VALIDATION"
        )
        print(
            "=" * 74
        )
        print(
            "Detection date :",
            detection_date,
        )
        print(
            "Trade date     :",
            trade_date,
        )
        print(
            "Candidates     : 0"
        )
        print()
        print(
            "No eligible earnings."
        )
        return

    #
    # Use column positions to avoid
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

print(
    "PATCHED :",
    path,
)
print(
    "BACKUP  :",
    backup,
)
