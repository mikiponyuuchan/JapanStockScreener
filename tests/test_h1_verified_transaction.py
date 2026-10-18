import unittest
from unittest.mock import patch, MagicMock

from intraday.rss_board_transaction import (
    execute_verified_board_transaction,
)


class TestH1VerifiedTransaction(unittest.TestCase):

    def setUp(self):
        self.workbook = MagicMock()
        self.sheet = MagicMock()
        self.layout = {row: ("", "") for row in range(2, 22)}
        self.changes = [(2, 1, "", "7203")]

    @patch("intraday.rss_board_transaction.prepare_board_changes")
    def test_dry_run_never_writes(self, prepare):
        prepare.return_value = self.changes

        with patch(
            "intraday.rss_board_backup_guard.create_verified_backup"
        ) as backup, patch(
            "intraday.rss_board_transaction.apply_changes_with_rollback"
        ) as write:
            result = execute_verified_board_transaction(
                self.workbook, self.sheet, self.layout,
                "unused", dry_run=True,
            )

        self.assertEqual(result, self.changes)
        backup.assert_not_called()
        write.assert_not_called()
        self.workbook.Save.assert_not_called()

    @patch("intraday.rss_board_transaction.prepare_board_changes")
    def test_backup_then_write(self, prepare):
        prepare.return_value = self.changes

        with patch(
            "intraday.rss_board_backup_guard.create_verified_backup",
            return_value=__file__,
        ) as backup, patch(
            "intraday.rss_board_transaction.apply_changes_with_rollback",
            return_value=1,
        ) as write:
            result = execute_verified_board_transaction(
                self.workbook, self.sheet, self.layout,
                "unused", dry_run=False,
            )

        self.assertEqual(result, self.changes)
        backup.assert_called_once()
        write.assert_called_once_with(self.sheet, self.changes)
        self.workbook.Save.assert_not_called()

    @patch("intraday.rss_board_transaction.prepare_board_changes")
    def test_changed_cells_block_write(self, prepare):
        prepare.side_effect = [
            self.changes,
            [(2, 1, "9999", "7203")],
        ]

        with patch(
            "intraday.rss_board_backup_guard.create_verified_backup",
            return_value=__file__,
        ), patch(
            "intraday.rss_board_transaction.apply_changes_with_rollback"
        ) as write:
            with self.assertRaisesRegex(
                RuntimeError, "Board changed after backup"
            ):
                execute_verified_board_transaction(
                    self.workbook, self.sheet, self.layout,
                    "unused", dry_run=False,
                )

        write.assert_not_called()
        self.workbook.Save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
