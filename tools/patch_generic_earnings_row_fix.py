from pathlib import Path

path = Path(
    "tools/test_generic_earnings_parser.py"
)

text = path.read_text(
    encoding="utf-8"
)

backup = Path(
    "tools/"
    "test_generic_earnings_parser_before_row_fix.py"
)

backup.write_text(
    text,
    encoding="utf-8"
)

start = text.index(
    "def find_performance_row(text):"
)

end = text.index(
    "\ndef extract_yoy(text):",
    start,
)

new_func = r'''def find_performance_row(text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    candidates = []

    for line in lines:
        #
        # Skip section headings and
        # explanatory date-range lines.
        #
        if (
            "\u9023\u7d50\u696d\u7e3e"
            in line
            or "\u696d\u7e3e\uff08"
            in line
            or "\u696d\u7e3e("
            in line
            or "\uff5e"
            in line
        ):
            continue

        #
        # A performance data row normally
        # starts with a fiscal period.
        #
        if not re.search(
            r"\d{4}\u5e74.*\u671f",
            line,
        ):
            continue

        numbers = re.findall(
            r"-?\d[\d,]*"
            r"(?:\.\d+)?",
            line,
        )

        #
        # Need at least:
        #
        # sales / yoy
        # operating / yoy
        # ordinary / yoy
        # net / yoy
        #
        if len(numbers) < 8:
            continue

        if (
            "\u914d\u5f53"
            in line
        ):
            continue

        tail = numbers[-8:]

        try:
            yoy_values = [
                float(
                    tail[1].replace(
                        ",",
                        "",
                    )
                ),
                float(
                    tail[3].replace(
                        ",",
                        "",
                    )
                ),
                float(
                    tail[5].replace(
                        ",",
                        "",
                    )
                ),
                float(
                    tail[7].replace(
                        ",",
                        "",
                    )
                ),
            ]
        except Exception:
            continue

        #
        # Reject obvious date/year values
        # accidentally parsed as YoY.
        #
        if any(
            abs(value) >= 1000
            for value in yoy_values
        ):
            continue

        candidates.append(
            (
                line,
                numbers,
            )
        )

    if not candidates:
        return None

    return candidates[0]

'''

text = (
    text[:start]
    + new_func
    + text[end:]
)

path.write_text(
    text,
    encoding="utf-8"
)

print("PATCHED :", path)
print("BACKUP  :", backup)
