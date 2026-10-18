import unittest
from unittest.mock import MagicMock, patch

from intraday.rss_board_transaction import (
    execute_and_save_verified_board,
)


class TestH1BoardSave(unittest.TestCase):

    def setUp(self):
        self.excel = MagicMock()
        self.workbook = MagicMock()
        self.sheet = MagicMock()
        self.layout = {
            row: ("", "") for row in range(2, 22)
        }
        self.changes = [(2, 1, "", "7203")]

    @patch("intraday.rss_board_transaction.prepare_board_changes")
    def test_success_saves_once(self, prepare):
        prepare.return_value = self.changes

        with patch(
            "intraday.rss_board_transaction.execute_verified_board_transaction",
            return_value=self.changes,
        ) as transaction:
            result = execute_and_save_verified_board(
                self.excel, self.workbook, self.sheet,
                self.layout, "unused", dry_run=False,
            )

        self.assertEqual(result, self.changes)
        transaction.assert_called_once()
        self.excel.Calculate.assert_called_once()
        self.workbook.Save.assert_called_once()

    @patch("intraday.rss_board_transaction.prepare_board_changes")
    def test_save_failure_stops(self, prepare):
        prepare.return_value = self.changes
        self.workbook.Save.side_effect = RuntimeError(
            "Simulated save failure"
        )

        with patch(
            "intraday.rss_board_transaction.execute_verified_board_transaction",
            return_value=self.changes,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "BOARD SAVE FAILED"
            ):
                execute_and_save_verified_board(
                    self.excel, self.workbook, self.sheet,
                    self.layout, "unused", dry_run=False,
                )

        self.workbook.Save.assert_called_once()

    @patch("intraday.rss_board_transaction.prepare_board_changes")
    def test_no_changes_no_save(self, prepare):
        prepare.return_value = []

        result = execute_and_save_verified_board(
            self.excel, self.workbook, self.sheet,
            self.layout, "unused", dry_run=False,
        )

        self.assertEqual(result, [])
        self.excel.Calculate.assert_not_called()
        self.workbook.Save.assert_not_called()

    def test_dry_run_no_save(self):
        with patch(
            "intraday.rss_board_transaction.execute_verified_board_transaction",
            return_value=[],
        ):
            execute_and_save_verified_board(
                self.excel, self.workbook, self.sheet,
                self.layout, "unused", dry_run=True,
            )

        self.excel.Calculate.assert_not_called()
        self.workbook.Save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
