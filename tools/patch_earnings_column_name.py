from pathlib import Path

path = Path(
    "tools/create_earnings_catalyst_batch.py"
)

text = path.read_text(
    encoding="utf-8"
)

old = r'"\u9285\u67c4\u540d"'
new = r'"\u9298\u67c4\u540d"'

count = text.count(old)

if count == 0:
    print("NOT FOUND")
else:
    text = text.replace(
        old,
        new,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "PATCHED :",
        count,
    )
