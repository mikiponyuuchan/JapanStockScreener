import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_backup_verify import (
    verify_board_backup,
)


class TestBoardBackupVerify(unittest.TestCase):

    def test_missing_backup_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing.xlsx"

            with self.assertRaisesRegex(
                RuntimeError, "Backup file not found"
            ):
                verify_board_backup(path)

    def test_empty_backup_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "empty.xlsx"
            path.write_bytes(b"")

            with self.assertRaisesRegex(
                RuntimeError, "Backup file is empty"
            ):
                verify_board_backup(path)

    def test_invalid_zip_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.xlsx"
            path.write_bytes(b"NOT AN EXCEL FILE")

            with self.assertRaisesRegex(
                RuntimeError,
                "Backup structure verification failed",
            ):
                verify_board_backup(path)


if __name__ == "__main__":
    unittest.main()
