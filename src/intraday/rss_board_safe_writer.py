from pathlib import Path


def normalize_cell(value):
    if value is None:
        return ""
    return str(value).strip()



def normalize_stock_code(value):
    text = normalize_cell(value)

    if text.endswith(".0"):
        text = text[:-2]

    return text


def prepare_board_changes(sheet, layout):
    """
    Read A/H only. Never write or save.
    layout: {row: (code, label)}
    """
    changes = []

    for row in range(2, 22):
        code_cell = sheet.Cells(row, 1)
        label_cell = sheet.Cells(row, 8)

        if bool(code_cell.HasFormula):
            raise RuntimeError(
                f"Formula detected: A{row}"
            )

        if bool(label_cell.HasFormula):
            raise RuntimeError(
                f"Formula detected: H{row}"
            )

        new_code, new_label = layout.get(
            row, ("", "")
        )

        old_code = normalize_cell(code_cell.Value)
        old_label = normalize_cell(label_cell.Value)

        new_code = normalize_cell(new_code)
        new_label = normalize_cell(new_label)

        # Compare stock codes after normalization.
        # Avoid unnecessary rewrites of numeric Excel cells.
        if normalize_stock_code(old_code) != normalize_stock_code(new_code):
            changes.append(
                (row, 1, code_cell.Value, new_code)
            )

        if old_label != new_label:
            changes.append(
                (row, 8, old_label, new_label)
            )

    return changes


def update_board(
    sheet,
    layout,
    dry_run=True,
):
    changes = prepare_board_changes(
        sheet, layout
    )

    print("DRY RUN:", dry_run)
    print("CHANGED CELLS:", len(changes))

    for row, col, old, new in changes:
        column = "A" if col == 1 else "H"
        print(
            f"{column}{row}: "
            f"{old!r} -> {new!r}"
        )

    if dry_run:
        print("NO WRITE / NO SAVE")
        return changes

    raise RuntimeError(
        "WRITE DISABLED: backup and verification "
        "must be implemented first"
    )
