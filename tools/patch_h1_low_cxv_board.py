from pathlib import Path

target = Path("src/intraday/h1_low_cxv_board.py")
text = target.read_text(encoding="utf-8")

marker = "def write_low_cxv_board(h1_candidates, enabled=False):"

if text.count(marker) != 1:
    raise SystemExit("PATCH ABORT: writer marker mismatch")

backup = Path(
    r"C:\JapanStockScreener_Backup\2026-10-21"
    r"\h1_low_cxv_board.py"
)

if not backup.is_file():
    raise SystemExit("PATCH ABORT: backup missing")

prefix = text[:text.index(marker)]

new_function = r'''def write_low_cxv_board(h1_candidates, enabled=False):
    """
    Write LOW-CxV without clearing board cells.

    Preferred rows: 12-14.
    Overflow rows: 15-21, empty rows only.

    Existing LOW-CxV rows may be updated.
    Other occupied rows are never overwritten.
    """

    from pathlib import Path
    from datetime import datetime

    selected = select_h1_low_cxv(h1_candidates)

    if not enabled:
        print("LOW-CxV Excel write: DISABLED")
        print("Selected:", len(selected))
        return selected

    from intraday.rss_live_board import get_live_board

    excel, book, sheet = get_live_board()

    if book.ReadOnly:
        raise RuntimeError(
            "LOW-CxV ABORT: Workbook is read-only"
        )

    # Verify the existing TOP10 before planning any writes.
    top10_before = {
        row: sheet.Cells(row, 1).Value
        for row in range(2, 12)
    }

    selected = preview_low_cxv_board(
        h1_candidates,
        top10_before,
    )

    # Read A/H for all possible LOW-CxV target rows.
    target_rows = list(range(12, 22))

    old_values = {
        (row, col): sheet.Cells(row, col).Value
        for row in target_rows
        for col in (1, 8)
    }

    # Existing LOW-CxV rows are reusable. Otherwise,
    # a row must be completely empty in both A and H.
    existing_low_rows = []
    empty_rows = []

    for row in target_rows:
        code = normalize_code(old_values[(row, 1)])
        label = str(
            old_values[(row, 8)] or ""
        ).strip()

        if bool(sheet.Cells(row, 1).HasFormula):
            if label.startswith("LOW-CxV #"):
                raise RuntimeError(
                    f"LOW-CxV ABORT: Formula in A{row}"
                )

        if bool(sheet.Cells(row, 8).HasFormula):
            if label.startswith("LOW-CxV #"):
                raise RuntimeError(
                    f"LOW-CxV ABORT: Formula in H{row}"
                )

        if label.startswith("LOW-CxV #"):
            existing_low_rows.append(row)
        elif not code and not label:
            empty_rows.append(row)

    # Preserve existing LOW-CxV positions first, then
    # prefer empty rows 12-14, then empty rows 15-21.
    preferred_empty = (
        [r for r in empty_rows if 12 <= r <= 14]
        + [r for r in empty_rows if 15 <= r <= 21]
    )

    available_rows = existing_low_rows + preferred_empty

    if len(available_rows) < len(selected):
        raise RuntimeError(
            "LOW-CxV ABORT: insufficient reusable or empty rows; "
            "no cells changed"
        )

    assignments = []

    for (_, item), row in zip(
        selected.iterrows(),
        available_rows,
    ):
        assignments.append((
            row,
            str(item["CodeX"]),
            f"LOW-CxV #{int(item['LowCxVRank'])}",
        ))

    if not assignments:
        print("LOW-CxV: no candidates to write")
        return selected

    # Create and verify a workbook backup before writing.
    backup_dir = Path(book.FullName).parent / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_path = backup_dir / (
        "rakuten_rss_morning_before_low_cxv_"
        + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        + ".xlsx"
    )

    book.SaveCopyAs(str(backup_path))

    if (
        not backup_path.is_file()
        or backup_path.stat().st_size == 0
    ):
        raise RuntimeError(
            "LOW-CxV ABORT: Backup verification failed"
        )

    # Recheck TOP10 and every target cell after backup.
    latest_top10 = {
        row: sheet.Cells(row, 1).Value
        for row in range(2, 12)
    }

    if latest_top10 != top10_before:
        raise RuntimeError(
            "LOW-CxV ABORT: TOP10 changed after backup"
        )

    for (row, col), old_value in old_values.items():
        if sheet.Cells(row, col).Value != old_value:
            raise RuntimeError(
                f"LOW-CxV ABORT: Cell changed after backup: "
                f"{row}, {col}"
            )

    changed_cells = []

    try:
        # No blanket clearing. Write only selected target cells.
        for row, code, label in assignments:
            for col, value in ((1, code), (8, label)):
                old_value = sheet.Cells(row, col).Value

                if old_value != value:
                    sheet.Cells(row, col).Value = value
                    changed_cells.append(
                        (row, col, old_value)
                    )

        excel.Calculate()
        book.Save()

    except Exception as write_error:
        restore_errors = []

        for row, col, old_value in reversed(changed_cells):
            try:
                sheet.Cells(row, col).Value = old_value
            except Exception as restore_error:
                restore_errors.append(
                    f"{row},{col}: {restore_error}"
                )

        if restore_errors:
            raise RuntimeError(
                "LOW-CxV WRITE/SAVE FAILED; rollback incomplete. "
                f"Backup: {backup_path}. "
                + "; ".join(restore_errors)
            ) from write_error

        raise RuntimeError(
            "LOW-CxV WRITE/SAVE FAILED; cell rollback attempted. "
            "Workbook save state may be uncertain. "
            f"Backup: {backup_path}. Do not retry automatically."
        ) from write_error

    print("LOW-CxV BOARD WRITE OK")
    print("Rows written:", [row for row, _, _ in assignments])
    print("Backup:", backup_path)

    return selected
'''

updated = prefix + new_function

compile(updated, str(target), "exec")
target.write_text(updated, encoding="utf-8", newline="")

print("PATCH OK:", target)
print("Blanket clearing removed")
print("Overflow allocation added")
print("Syntax: OK")
