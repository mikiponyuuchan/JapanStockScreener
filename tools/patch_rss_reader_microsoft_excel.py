from pathlib import Path

target = Path(
    "src/intraday/rss_reader.py"
)

backup = Path(
    "src/intraday/"
    "rss_reader_before_microsoft_excel.py"
)

text = target.read_text(
    encoding="utf-8"
)

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

old_import = """import win32com.client as win32
"""

new_import = """from rss_excel import get_microsoft_excel
"""

if old_import not in text:
    raise RuntimeError(
        "win32 import not found"
    )

text = text.replace(
    old_import,
    new_import,
    1,
)

start = text.find(
    "def get_excel_app():"
)

end = text.find(
    "\ndef get_rss_sheet():",
    start,
)

if start == -1 or end == -1:
    raise RuntimeError(
        "get_excel_app block not found"
    )

new_function = '''def get_excel_app():
    """
    Get the Microsoft Excel instance that owns
    the Rakuten RSS H1 workbook.

    WPS / Kingsoft is ignored by rss_excel.
    """
    retry_count = 5
    retry_wait = 0.5
    last_error = None

    for attempt in range(
        1,
        retry_count + 1,
    ):
        try:
            return get_microsoft_excel(
                start_if_missing=True
            )

        except Exception as exc:
            last_error = exc

            if attempt < retry_count:
                time.sleep(
                    retry_wait
                )

    raise RuntimeError(
        "Microsoft Excel RSS connection "
        "failed after "
        f"{retry_count} attempts: "
        f"{last_error}"
    ) from last_error

'''

text = (
    text[:start]
    + new_function
    + text[end + 1:]
)

target.write_text(
    text,
    encoding="utf-8",
)

print("PATCH OK :", target)
print("BACKUP   :", backup)
