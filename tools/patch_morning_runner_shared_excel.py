from pathlib import Path

target = Path(
    "src/intraday/rss_morning_runner.py"
)

backup = Path(
    "src/intraday/"
    "rss_morning_runner_before_shared_excel.py"
)

text = target.read_text(
    encoding="utf-8"
)

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

# ----------------------------------------
# Remove temporary direct win32 dependency
# ----------------------------------------

text = text.replace(
    "import win32com.client as win32\n",
    "",
    1,
)

# ----------------------------------------
# Add shared Microsoft Excel helper
# ----------------------------------------

marker = """from rss_reader import read_rss_rows
"""

replacement = """from rss_reader import read_rss_rows
from rss_excel import ensure_rss_workbooks
"""

if marker not in text:
    raise RuntimeError(
        "rss_reader import marker not found"
    )

text = text.replace(
    marker,
    replacement,
    1,
)

# ----------------------------------------
# Replace temporary prepare implementation
# ----------------------------------------

start = text.find(
    "RSS_WORKBOOKS = ("
)

end_marker = """# ================================================
# 時刻生成
# ================================================
"""

end = text.find(
    end_marker,
    start,
)

if start == -1 or end == -1:
    raise RuntimeError(
        "prepare_rss_excel block not found"
    )

new_block = '''def prepare_rss_excel():
    """
    Prepare the dedicated Microsoft Excel instance
    and all Rakuten RSS workbooks.

    WPS / Kingsoft is ignored by rss_excel.
    """
    print()
    print("=" * 60)
    print(" MICROSOFT EXCEL PREPARE")
    print("=" * 60)

    excel, results = ensure_rss_workbooks()

    print(
        "Microsoft Excel COM       : OK"
    )
    print(
        f"Microsoft Excel Version   : "
        f"{excel.Version}"
    )
    print(
        f"Microsoft Excel Path      : "
        f"{excel.Path}"
    )

    for workbook_name, status in (
        results.items()
    ):
        print(
            f"{workbook_name:<34}: "
            f"{status}"
        )

    print(
        "RSS Excel preparation     : OK"
    )
    print("=" * 60)

    return excel


'''

text = (
    text[:start]
    + new_block
    + text[end:]
)

target.write_text(
    text,
    encoding="utf-8",
)

print("PATCH OK :", target)
print("BACKUP   :", backup)
