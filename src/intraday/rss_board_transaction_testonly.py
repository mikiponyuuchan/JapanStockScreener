from pathlib import Path

from intraday.rss_board_safe_writer import prepare_board_changes
from intraday.rss_board_rollback import apply_changes_with_rollback
from intraday.rss_board_backup_guard import create_verified_backup


def execute_test_transaction(
    workbook,
    sheet,
    layout,
    backup_dir,
):
    """
    Test-only transaction.
    Do not use with the production RSS workbook.
    No workbook save is performed.
    """

    changes = prepare_board_changes(sheet, layout)

    print("CHANGED CELLS:", len(changes))

    if not changes:
        print("NO CHANGES")
        return []

    backup_path = create_verified_backup(
        workbook,
        backup_dir,
    )

    if not Path(backup_path).is_file():
        raise RuntimeError(
            "WRITE BLOCKED: backup missing"
        )

    # Recheck all cells after backup creation.
    rechecked = prepare_board_changes(sheet, layout)

    if rechecked != changes:
        raise RuntimeError(
            "WRITE BLOCKED: cells changed during backup"
        )

    count = apply_changes_with_rollback(
        sheet,
        changes,
    )

    print("WRITE VERIFIED:", count)
    print("WORKBOOK NOT SAVED")

    return changes
