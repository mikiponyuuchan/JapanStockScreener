from intraday.h1_low_cxv_selector import select_h1_low_cxv


def normalize_code(value):
    if value is None:
        return ""
    code = str(value).strip()
    return code[:-2] if code.endswith(".0") else code


def preview_low_cxv_board(h1_candidates, board_rows):
    """
    DRY RUN ONLY.
    No Excel connection or writes.
    """

    expected = [
        normalize_code(code)
        for code in h1_candidates.head(10)["CodeX"]
    ]

    actual = [
        normalize_code(board_rows.get(row, ""))
        for row in range(2, 12)
    ]

    if len(expected) != 10:
        raise RuntimeError(
            "LOW-CxV ABORT: TOP10 has fewer than 10 stocks"
        )

    if actual != expected:
        raise RuntimeError(
            "LOW-CxV ABORT: TOP10 board rows mismatch\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )

    selected = select_h1_low_cxv(h1_candidates)

    print("=== LOW-CxV BOARD DRY RUN ===")
    print("TOP10 board verification: PASS")
    print("Excel write: DISABLED")

    for _, row in selected.iterrows():
        print(
            f"Row {int(row['BoardRow'])}: "
            f"{row['CodeX']} "
            f"LOW-CxV #{int(row['LowCxVRank'])}"
        )

    print("Selected:", len(selected))
    return selected


def write_low_cxv_board(h1_candidates, enabled=False):
    """
    Write LOW-CxV to rows 12-14 only.

    Default: DRY RUN.
    Requires matching TOP10 in rows 2-11.
    """

    from pathlib import Path
    from datetime import datetime
    if not enabled:
        print("LOW-CxV Excel write: DISABLED")
        selected = select_h1_low_cxv(h1_candidates)
        for _, row in selected.iterrows():
            print(
                f"Row {int(row['BoardRow'])}: "
                f"{row['CodeX']} "
                f"LOW-CxV #{int(row['LowCxVRank'])}"
            )
        return selected

    from intraday.rss_live_board import get_live_board

    excel, book, sheet = get_live_board()

    board_rows = {
        row: sheet.Cells(row, 1).Value
        for row in range(2, 12)
    }

    selected = preview_low_cxv_board(
        h1_candidates, board_rows
    )

    if book.ReadOnly:
        raise RuntimeError("LOW-CxV ABORT: Workbook is read-only")

    old_values = {
        (r, c): sheet.Cells(r, c).Value
        for r in range(12, 15)
        for c in (1, 8)
    }

    for r in range(12, 15):
        old_code = normalize_code(old_values[(r, 1)])
        old_label = str(old_values[(r, 8)] or "").strip()

        if old_code or old_label:
            if not old_label.startswith("LOW-CxV #"):
                raise RuntimeError(
                    f"LOW-CxV ABORT: Row {r} belongs to another strategy"
                )

    backup_dir = Path(book.FullName).parent / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup = backup_dir / (
        "rakuten_rss_morning_before_low_cxv_"
        + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        + ".xlsx"
    )

    book.SaveCopyAs(str(backup))

    if not backup.is_file() or backup.stat().st_size == 0:
        raise RuntimeError("LOW-CxV ABORT: Backup failed")

    # Recheck TOP10 immediately before changing cells.
    latest_rows = {
        r: sheet.Cells(r, 1).Value
        for r in range(2, 12)
    }
    preview_low_cxv_board(h1_candidates, latest_rows)

    # Refuse to overwrite target rows changed since validation.
    for (r, c), old_value in old_values.items():
        if sheet.Cells(r, c).Value != old_value:
            raise RuntimeError(
                f"LOW-CxV ABORT: Cell changed before write: {r}, {c}"
            )

    try:
        for row_number in range(12, 15):
            sheet.Cells(row_number, 1).Value = None
            sheet.Cells(row_number, 8).Value = None

        for _, row in selected.iterrows():
            r = int(row["BoardRow"])
            rank = int(row["LowCxVRank"])

            sheet.Cells(r, 1).Value = str(row["CodeX"])
            sheet.Cells(r, 8).Value = f"LOW-CxV #{rank}"

        book.Save()

    except Exception as write_error:
        try:
            for (r, c), value in old_values.items():
                sheet.Cells(r, c).Value = value
        except Exception as restore_error:
            raise RuntimeError(
                "LOW-CxV write failed AND rollback failed. "
                f"Backup: {backup}. "
                f"Write error: {write_error}. "
                f"Restore error: {restore_error}"
            ) from write_error

        raise RuntimeError(
            "LOW-CxV write failed; cell rollback attempted. "
            "Restored values have not been saved. "
            f"Backup: {backup}"
        ) from write_error

    print("LOW-CxV BOARD WRITE OK")
    print("Backup:", backup)

    return selected
