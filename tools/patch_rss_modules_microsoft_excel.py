from pathlib import Path


# ============================================================
# rss_live_board.py
# ============================================================

target = Path("src/intraday/rss_live_board.py")
backup = Path(
    "src/intraday/"
    "rss_live_board_before_microsoft_excel.py"
)

text = target.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

old_import = "import win32com.client as win32\n"
new_import = (
    "from rss_excel import get_microsoft_excel\n"
)

if old_import not in text:
    raise RuntimeError(
        "rss_live_board win32 import not found"
    )

text = text.replace(
    old_import,
    new_import,
    1,
)

old = '''            excel = win32.GetActiveObject(
                "Excel.Application"
            )

            book = excel.Workbooks(
                WORKBOOK_NAME
            )
'''

new = '''            excel = get_microsoft_excel(
                start_if_missing=True
            )

            book = excel.Workbooks(
                WORKBOOK_NAME
            )
'''

if old not in text:
    raise RuntimeError(
        "rss_live_board COM block not found"
    )

text = text.replace(
    old,
    new,
    1,
)

target.write_text(
    text,
    encoding="utf-8",
)

print("PATCH OK :", target)
print("BACKUP   :", backup)


# ============================================================
# rss_snapshot.py
# ============================================================

target = Path("src/intraday/rss_snapshot.py")
backup = Path(
    "src/intraday/"
    "rss_snapshot_before_microsoft_excel.py"
)

text = target.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

old_import = "import win32com.client as win32\n"

if old_import not in text:
    raise RuntimeError(
        "rss_snapshot win32 import not found"
    )

text = text.replace(
    old_import,
    "from rss_excel import get_microsoft_excel\n",
    1,
)

start = text.find("def get_excel():")
end = text.find(
    "\ndef get_test_sheet():",
    start,
)

if start == -1 or end == -1:
    raise RuntimeError(
        "rss_snapshot get_excel block not found"
    )

new_function = '''def get_excel():
    """
    Get the Microsoft Excel instance used by
    Rakuten RSS.

    WPS / Kingsoft is ignored by rss_excel.
    """
    try:
        return get_microsoft_excel(
            start_if_missing=True
        )

    except Exception as exc:
        raise RuntimeError(
            "Microsoft Excel RSS instance "
            "was not found."
        ) from exc

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
