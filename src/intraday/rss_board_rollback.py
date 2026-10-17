
def values_match(col, actual, expected):
    if col == 1:
        from intraday.rss_board_safe_writer import (
            normalize_stock_code,
        )
        return (
            normalize_stock_code(actual)
            == normalize_stock_code(expected)
        )

    return (
        type(actual) is type(expected)
        and actual == expected
    )


def apply_changes_with_rollback(sheet, changes):
    """
    Apply cell changes with rollback on failure.

    changes: [(row, col, old_value, new_value), ...]

    This function is for isolated testing.
    It does not save the workbook.
    """
    originals = []
    seen = set()

    # Validate every change before writing.
    for row, col, old, new in changes:
        if not (2 <= row <= 21 and col in (1, 8)):
            raise RuntimeError("Invalid target cell")

        key = (row, col)
        if key in seen:
            raise RuntimeError("Duplicate target cell")
        seen.add(key)

        cell = sheet.Cells(row, col)

        if bool(cell.HasFormula):
            raise RuntimeError("Formula detected")

        actual = cell.Value
        if actual != old:
            raise RuntimeError(
                f"Cell changed before write: {key}"
            )

        originals.append((row, col, actual))

    try:
        for row, col, old, new in changes:
            sheet.Cells(row, col).Value = new

            if not values_match(col, sheet.Cells(row, col).Value, new):
                raise RuntimeError(
                    f"Verification failed: {(row, col)}"
                )

    except Exception as write_error:
        rollback_errors = []

        # Restore all targets, including the failed one.
        for row, col, original in reversed(originals):
            try:
                sheet.Cells(row, col).Value = original

                if not values_match(col, sheet.Cells(row, col).Value, original):
                    raise RuntimeError(
                        "Rollback verification failed"
                    )

            except Exception as exc:
                rollback_errors.append(
                    f"{(row, col)}: {exc}"
                )

        if rollback_errors:
            raise RuntimeError(
                "WRITE FAILED AND ROLLBACK INCOMPLETE: "
                + "; ".join(rollback_errors)
            ) from write_error

        raise RuntimeError(
            "WRITE FAILED; ROLLBACK VERIFIED"
        ) from write_error

    return len(changes)
