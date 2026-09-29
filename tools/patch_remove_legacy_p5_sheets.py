from pathlib import Path

path = Path("src/services/result_writer.py")

text = path.read_text(encoding="utf-8")
original = text

marker = """    # ======================================================
    # P5 sheets disabled
    # ======================================================

"""

replacement = """    # ======================================================
    # P5 sheets disabled
    # Remove legacy P5 sheets left in an existing workbook.
    # ======================================================

    for legacy_p5_sheet in [
        "P5早期候補",
        "P5追跡",
    ]:
        if legacy_p5_sheet in workbook.sheetnames:
            workbook.remove(
                workbook[legacy_p5_sheet]
            )

"""

if marker not in text:
    raise SystemExit(
        "ERROR : P5 disabled marker not found."
    )

text = text.replace(
    marker,
    replacement,
    1,
)

backup = path.with_name(
    "result_writer_before_remove_legacy_p5_sheets.py"
)

backup.write_text(
    original,
    encoding="utf-8",
)

path.write_text(
    text,
    encoding="utf-8",
)

print("PATCHED : remove legacy P5 Excel sheets")
print("BACKUP  :", backup)
print("PATCHED :", path)
print("COMPLETE")
