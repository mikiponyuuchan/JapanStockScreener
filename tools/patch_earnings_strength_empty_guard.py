from pathlib import Path

path = Path(
    "tools/analyze_earnings_strength.py"
)

text = path.read_text(
    encoding="utf-8"
)

backup = Path(
    "tools/analyze_earnings_strength_before_empty_guard.py"
)

backup.write_text(
    text,
    encoding="utf-8"
)

needle = '''    df = pd.read_excel(
        path
    )

    cols = {
'''

replacement = '''    df = pd.read_excel(
        path
    )

    if df.empty or len(df.columns) == 0:
        print(
            "=" * 78
        )
        print(
            "EARNINGS STRENGTH RANKING"
        )
        print(
            "=" * 78
        )
        print(
            "Date       :",
            args.date,
        )
        print(
            "Candidates : 0"
        )
        print()
        print(
            "No eligible earnings."
        )
        return

    cols = {
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
