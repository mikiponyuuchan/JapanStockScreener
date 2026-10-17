import sys
import unittest
from pathlib import Path
from unittest.mock import patch, call

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_transaction_testonly import (
    execute_test_transaction,
)

MODULE = "intraday.rss_board_transaction_testonly"


class TestBoardTransaction(unittest.TestCase):

    def setUp(self):
        self.workbook = object()
        self.sheet = object()
        self.layout = {}
        self.backup_dir = "dummy_backup_dir"
        self.changes = [(2, 1, "1001", "2001")]

    def run_transaction(self):
        return execute_test_transaction(
            self.workbook,
            self.sheet,
            self.layout,
            self.backup_dir,
        )

    def test_backup_failure_blocks_write(self):
        with (
            patch(
                MODULE + ".prepare_board_changes",
                return_value=self.changes,
            ),
            patch(
                MODULE + ".create_verified_backup",
                side_effect=RuntimeError("Backup failed"),
            ),
            patch(
                MODULE + ".apply_changes_with_rollback"
            ) as writer,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Backup failed"
            ):
                self.run_transaction()

            writer.assert_not_called()

    def test_changed_cells_after_backup_blocks_write(self):
        with (
            patch(
                MODULE + ".prepare_board_changes",
                side_effect=[
                    self.changes,
                    [(2, 1, "1001", "3001")],
                ],
            ),
            patch(
                MODULE + ".create_verified_backup",
                return_value=Path(__file__),
            ),
            patch(
                MODULE + ".apply_changes_with_rollback"
            ) as writer,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "cells changed during backup"
            ):
                self.run_transaction()

            writer.assert_not_called()

    def test_verified_backup_allows_write(self):
        with (
            patch(
                MODULE + ".prepare_board_changes",
                side_effect=[
                    self.changes,
                    self.changes,
                ],
            ),
            patch(
                MODULE + ".create_verified_backup",
                return_value=Path(__file__),
            ) as backup,
            patch(
                MODULE + ".apply_changes_with_rollback",
                return_value=1,
            ) as writer,
        ):
            result = self.run_transaction()

            self.assertEqual(result, self.changes)
            backup.assert_called_once_with(
                self.workbook,
                self.backup_dir,
            )
            writer.assert_called_once_with(
                self.sheet,
                self.changes,
            )


if __name__ == "__main__":
    unittest.main()
