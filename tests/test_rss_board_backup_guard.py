import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_backup_guard import (
    create_verified_backup,
)

MODULE = "intraday.rss_board_backup_guard"


class TestBoardBackupGuard(unittest.TestCase):

    def setUp(self):
        self.workbook = object()
        self.backup_dir = "dummy_backup_dir"
        self.backup_path = Path("dummy_backup.xlsx")

    def test_creation_failure_blocks_verification(self):
        with (
            patch(
                MODULE + ".create_board_backup",
                side_effect=RuntimeError("Backup creation failed"),
            ),
            patch(
                MODULE + ".verify_board_backup"
            ) as verifier,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Backup creation failed"
            ):
                create_verified_backup(
                    self.workbook,
                    self.backup_dir,
                )

            verifier.assert_not_called()

    def test_verification_failure_rejected(self):
        with (
            patch(
                MODULE + ".create_board_backup",
                return_value=self.backup_path,
            ),
            patch(
                MODULE + ".verify_board_backup",
                return_value=False,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Backup verification failed"
            ):
                create_verified_backup(
                    self.workbook,
                    self.backup_dir,
                )

    def test_verified_backup_returns_path(self):
        with (
            patch(
                MODULE + ".create_board_backup",
                return_value=self.backup_path,
            ) as creator,
            patch(
                MODULE + ".verify_board_backup",
                return_value=True,
            ) as verifier,
        ):
            result = create_verified_backup(
                self.workbook,
                self.backup_dir,
            )

            self.assertEqual(result, self.backup_path)
            creator.assert_called_once_with(
                self.workbook,
                self.backup_dir,
            )
            verifier.assert_called_once_with(
                self.backup_path,
            )


if __name__ == "__main__":
    unittest.main()
