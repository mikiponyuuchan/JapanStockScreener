from pathlib import Path

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

    # Production write requires an actual verified backup.
    # Never trust backup_verified=True by itself.
    raise RuntimeError(
        "WRITE DISABLED: use execute_verified_board_transaction"
    )


def execute_verified_board_transaction(
    workbook,
    sheet,
    layout,
    backup_dir,
    *,
    dry_run=True,
):
    """
    Prepare and verify an Excel board update.

    dry_run=True:
        No backup, no write, no save.

    dry_run=False:
        Create and verify a backup, recheck the
        target cells, and apply guarded writes.

    Workbook saving is deliberately NOT performed.
    """
    from intraday.rss_board_backup_guard import (
        create_verified_backup,
    )

    changes = prepare_board_changes(sheet, layout)

    if dry_run:
        print("DRY RUN:", len(changes), "changes")
        print("NO WRITE / NO SAVE")
        return changes

    if not changes:
        print("NO CHANGES")
        return []

    backup_path = create_verified_backup(
        workbook,
        backup_dir,
    )

    if not Path(backup_path).is_file():
        raise RuntimeError(
            "Verified backup file missing"
        )

    rechecked = prepare_board_changes(
        sheet,
        layout,
    )

    if rechecked != changes:
        raise RuntimeError(
            "Board changed after backup"
        )

    count = apply_changes_with_rollback(
        sheet,
        changes,
    )

    print("BACKUP VERIFIED:", backup_path)
    print("WRITE VERIFIED:", count)
    print("WORKBOOK NOT SAVED")

    return changes


def execute_and_save_verified_board(
    excel,
    workbook,
    sheet,
    layout,
    backup_dir,
    *,
    dry_run=True,
):
    """
    Verified board update with one final workbook save.

    dry_run=True: no backup, write, calculation or save.
    dry_run=False: verified backup, guarded write, save.

    On save failure, stop and retain the backup.
    Never automatically overwrite the workbook.
    """
    if dry_run:
        return execute_verified_board_transaction(
            workbook,
            sheet,
            layout,
            backup_dir,
            dry_run=True,
        )

    # Do not calculate or save when nothing changes.
    changes = prepare_board_changes(sheet, layout)
    if not changes:
        print("NO CHANGES / NO SAVE")
        return []

    applied = execute_verified_board_transaction(
        workbook,
        sheet,
        layout,
        backup_dir,
        dry_run=False,
    )

    try:
        excel.Calculate()
        workbook.Save()
    except Exception as exc:
        raise RuntimeError(
            "BOARD SAVE FAILED: stop runner and preserve "
            "the verified backup; workbook state may be "
            "uncertain. Do not retry automatically."
        ) from exc

    print("BOARD SAVED:", len(applied), "changed cells")
    return applied
