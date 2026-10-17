from intraday.rss_board_safe_writer import (
    prepare_board_changes,
)
from intraday.rss_board_rollback import (
    apply_changes_with_rollback,
)


def execute_board_transaction(
    sheet,
    layout,
    backup_verified=False,
    dry_run=True,
):
    """
    Coordinate change detection and guarded writes.

    No workbook save is performed.
    Backup creation is handled separately.
    """

    changes = prepare_board_changes(sheet, layout)

    print("DRY RUN:", dry_run)
    print("CHANGED CELLS:", len(changes))

    for row, col, old, new in changes:
        column = "A" if col == 1 else "H"
        print(
            f"{column}{row}: {old!r} -> {new!r}"
        )

    if dry_run:
        print("NO WRITE / NO SAVE")
        return changes

    # Production writes remain disabled.
    # A caller-provided boolean is not proof of backup.
    raise RuntimeError(
        "WRITE DISABLED: verified backup integration pending"
    )

    print("WRITE VERIFIED:", count)
    print("WORKBOOK NOT SAVED")

    return changes
