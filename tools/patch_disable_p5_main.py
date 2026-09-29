from pathlib import Path

path = Path("src/services/result_writer.py")

text = path.read_text(encoding="utf-8")
original = text

# 1. P5 import
old = """from services.p5_tracking_service import (
    load_p5_tracking,
    record_p5_candidates,
    update_p5_tracking,
)

"""

if old in text:
    text = text.replace(old, "", 1)
    print("PATCHED : P5 import")
else:
    print("SKIP    : P5 import")

# 2. P5 detection / tracking load
start_marker = """    # ======================================================
    # P5早期候補
    # ======================================================
"""

end_marker = """    news_data = {}
"""

start = text.find(start_marker)

if start != -1:
    end = text.find(end_marker, start)

    if end != -1:
        replacement = """    # ======================================================
    # P5 disabled in main screener
    # ======================================================

"""
        text = text[:start] + replacement + text[end:]
        print("PATCHED : P5 detection/tracking")
    else:
        print("SKIP    : P5 detection end")
else:
    print("SKIP    : P5 detection start")

# 3. P5 Excel sheets
start_marker = """    # ======================================================
    # P5早期候補
    # ======================================================

    if "P5早期候補" in workbook.sheetnames:
"""

end_marker = """    # ======================================================
    # 全銘柄
    # ======================================================
"""

start = text.find(start_marker)

if start != -1:
    end = text.find(end_marker, start)

    if end != -1:
        replacement = """    # ======================================================
    # P5 sheets disabled
    # ======================================================

"""
        text = text[:start] + replacement + text[end:]
        print("PATCHED : P5 Excel sheets")
    else:
        print("SKIP    : P5 Excel end")
else:
    print("SKIP    : P5 Excel start")

# 4. Sheet-order comment
old = """    # 最新TOP20
    # P5早期候補
    # P5追跡
    # 過去TOP20（新しい順）
    # 全銘柄
    # 初動追跡
"""

new = """    # 最新TOP20
    # 過去TOP20（新しい順）
    # 全銘柄
    # 初動追跡
"""

if old in text:
    text = text.replace(old, new, 1)
    print("PATCHED : sheet order comment")
else:
    print("SKIP    : sheet order comment")

# 5. Sheet order
old = """        [
            top20_sheet_name,
            "P5早期候補",
            "P5追跡",
        ]
"""

new = """        [
            top20_sheet_name,
        ]
"""

if old in text:
    text = text.replace(old, new, 1)
    print("PATCHED : sheet order")
else:
    print("SKIP    : sheet order")

if text == original:
    raise SystemExit("ERROR : No changes were made.")

backup = path.with_name(
    "result_writer_before_disable_p5_main.py"
)

backup.write_text(
    original,
    encoding="utf-8",
)

path.write_text(
    text,
    encoding="utf-8",
)

print()
print("BACKUP :", backup)
print("PATCHED :", path)
print("COMPLETE")
