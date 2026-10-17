from pathlib import Path
from datetime import datetime


def create_board_backup(workbook, backup_dir):
    """
    Create a backup using Excel SaveCopyAs.
    Does not modify cells or save the original.
    """
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    original = Path(workbook.FullName)

    if not original.is_file():
        raise RuntimeError(
            "Original workbook not found"
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    backup_path = backup_dir / (
        original.stem
        + "_backup_"
        + timestamp
        + original.suffix
    )

    if backup_path.exists():
        raise RuntimeError(
            "Backup path already exists"
        )

    workbook.SaveCopyAs(str(backup_path))

    if not backup_path.is_file():
        raise RuntimeError(
            "Backup file was not created"
        )

    if backup_path.stat().st_size == 0:
        raise RuntimeError(
            "Backup file is empty"
        )

    print("BACKUP CREATED:", backup_path)
    print("BACKUP SIZE:", backup_path.stat().st_size)

    return backup_path
