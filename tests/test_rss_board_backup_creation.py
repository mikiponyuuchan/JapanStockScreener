import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_backup import create_board_backup


class FakeWorkbook:
    def __init__(self, original, mode="success"):
        self.FullName = str(original)
        self.mode = mode
        self.calls = 0

    def SaveCopyAs(self, destination):
        self.calls += 1

        if self.mode == "error":
            raise RuntimeError("Simulated SaveCopyAs failure")

        if self.mode == "missing":
            return

        if self.mode == "empty":
            Path(destination).write_bytes(b"")
            return

        Path(destination).write_bytes(b"FAKE BACKUP")


class TestBoardBackupCreation(unittest.TestCase):

    def test_missing_original_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workbook = FakeWorkbook(root / "missing.xlsx")

            with self.assertRaisesRegex(
                RuntimeError, "Original workbook not found"
            ):
                create_board_backup(
                    workbook, root / "backups"
                )

            self.assertEqual(workbook.calls, 0)

    def test_savecopyas_failure_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original.xlsx"
            original.write_bytes(b"ORIGINAL")

            workbook = FakeWorkbook(original, "error")

            with self.assertRaisesRegex(
                RuntimeError, "Simulated SaveCopyAs failure"
            ):
                create_board_backup(
                    workbook, root / "backups"
                )

            self.assertEqual(workbook.calls, 1)

    def test_backup_not_created_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original.xlsx"
            original.write_bytes(b"ORIGINAL")

            workbook = FakeWorkbook(original, "missing")

            with self.assertRaisesRegex(
                RuntimeError, "Backup file was not created"
            ):
                create_board_backup(
                    workbook, root / "backups"
                )

    def test_empty_backup_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original.xlsx"
            original.write_bytes(b"ORIGINAL")

            workbook = FakeWorkbook(original, "empty")

            with self.assertRaisesRegex(
                RuntimeError, "Backup file is empty"
            ):
                create_board_backup(
                    workbook, root / "backups"
                )

    def test_successful_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original.xlsx"
            original.write_bytes(b"ORIGINAL")

            workbook = FakeWorkbook(original)

            backup = create_board_backup(
                workbook, root / "backups"
            )

            self.assertTrue(backup.is_file())
            self.assertEqual(
                backup.read_bytes(), b"FAKE BACKUP"
            )
            self.assertEqual(workbook.calls, 1)
            self.assertNotEqual(backup, original)
            self.assertEqual(
                original.read_bytes(), b"ORIGINAL"
            )


if __name__ == "__main__":
    unittest.main()
