import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import intraday.h1_low_cxv_board as board


class TestLowCxVWriterSafety(unittest.TestCase):

    def test_disabled_mode_never_connects_to_excel(self):
        import pandas as pd

        candidates = pd.DataFrame(
            columns=["CodeX", "ChangeX", "CxV"]
        )

        with patch(
            "intraday.h1_low_cxv_board.get_live_board",
            create=True,
            side_effect=AssertionError("Excel must not be accessed"),
        ):
            result = board.write_low_cxv_board(
                candidates,
                enabled=False,
            )

        self.assertTrue(result.empty)

    def test_backup_guard_rejects_unverified_backup(self):
        from intraday.rss_board_backup_guard import (
            create_verified_backup,
        )

        with patch(
            "intraday.rss_board_backup_guard.create_board_backup",
            return_value=ROOT / "nonexistent_test_backup.xlsx",
        ), patch(
            "intraday.rss_board_backup_guard.verify_board_backup",
            return_value=False,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Backup verification failed",
            ):
                create_verified_backup(
                    object(),
                    ROOT / "tests",
                )

    def test_rollback_rejects_formula_cell(self):
        from tests.test_rss_board_rollback import FakeSheet
        from intraday.rss_board_rollback import (
            apply_changes_with_rollback,
        )

        sheet = FakeSheet()
        cell = sheet.Cells(12, 1)
        cell.Value = "1234"
        cell.HasFormula = True

        with self.assertRaisesRegex(
            RuntimeError,
            "Formula detected",
        ):
            apply_changes_with_rollback(
                sheet,
                [(12, 1, "1234", "5678")],
            )

        self.assertEqual(cell.Value, "1234")


if __name__ == "__main__":
    unittest.main()
