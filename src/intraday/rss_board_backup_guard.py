from pathlib import Path

from intraday.rss_board_backup import create_board_backup
from intraday.rss_board_backup_verify import verify_board_backup


def create_verified_backup(workbook, backup_dir):
    backup_path = create_board_backup(
        workbook,
        backup_dir,
    )

    if not verify_board_backup(backup_path):
        raise RuntimeError(
            "Backup verification failed"
        )

    print("BACKUP GUARD OK")

    return Path(backup_path)
