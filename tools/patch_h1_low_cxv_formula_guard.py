from pathlib import Path

target = Path("src/intraday/h1_low_cxv_board.py")
text = target.read_text(encoding="utf-8")

old = '''        if bool(sheet.Cells(row, 1).HasFormula):
            if label.startswith("LOW-CxV #"):
                raise RuntimeError(
                    f"LOW-CxV ABORT: Formula in A{row}"
                )

        if bool(sheet.Cells(row, 8).HasFormula):
            if label.startswith("LOW-CxV #"):
                raise RuntimeError(
                    f"LOW-CxV ABORT: Formula in H{row}"
                )
'''

new = '''        if bool(sheet.Cells(row, 1).HasFormula):
            raise RuntimeError(
                f"LOW-CxV ABORT: Formula in A{row}; "
                "no cells changed"
            )

        if bool(sheet.Cells(row, 8).HasFormula):
            raise RuntimeError(
                f"LOW-CxV ABORT: Formula in H{row}; "
                "no cells changed"
            )
'''

if text.count(old) != 1:
    raise SystemExit(
        "PATCH ABORT: formula guard block mismatch"
    )

backup = Path(
    r"C:\JapanStockScreener_Backup\2026-10-21"
    r"\h1_low_cxv_board.py"
)

if not backup.is_file():
    raise SystemExit("PATCH ABORT: backup missing")

updated = text.replace(old, new, 1)
compile(updated, str(target), "exec")
target.write_text(updated, encoding="utf-8", newline="")

print("PATCH OK:", target)
print("Formula guard: A12:H21 target cells protected")
print("Syntax: OK")
