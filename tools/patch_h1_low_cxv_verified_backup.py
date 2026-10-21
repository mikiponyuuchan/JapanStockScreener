from pathlib import Path

target = Path("src/intraday/h1_low_cxv_board.py")
text = target.read_text(encoding="utf-8")

old = '''    # Create and verify a workbook backup before writing.
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
'''

new = '''    # Create and verify a workbook backup before writing.
    from intraday.rss_board_backup_guard import (
        create_verified_backup,
    )

    backup_dir = Path(book.FullName).parent / "backup"

    try:
        backup_path = create_verified_backup(
            book,
            backup_dir,
        )
    except Exception as exc:
        raise RuntimeError(
            "LOW-CxV ABORT: Verified backup failed; "
            "no board cells were changed"
        ) from exc
'''

if text.count(old) != 1:
    raise SystemExit(
        "PATCH ABORT: backup block mismatch; no changes made"
    )

updated = text.replace(old, new, 1)
compile(updated, str(target), "exec")

target.write_text(updated, encoding="utf-8", newline="")

print("PATCH OK:", target)
print("Common verified-backup guard enabled")
print("Syntax: OK")
