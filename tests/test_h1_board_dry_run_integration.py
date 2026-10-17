import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_h1_board_bridge import (
    board_rows_to_layout,
    build_h1_board_layout,
)
from intraday.rss_board_safe_writer import (
    prepare_board_changes,
    update_board,
)
from tests.test_rss_board_rollback import FakeSheet


class TestH1BoardDryRunIntegration(unittest.TestCase):

    def test_fixed_layout_dry_run(self):
        sheet = FakeSheet()

        sheet.Cells(2, 1).Value = "7203"
        sheet.Cells(2, 8).Value = "J1 BUY"

        sheet.Cells(3, 1).Value = "6501"
        sheet.Cells(3, 8).Value = "SSR-Ver1"

        # An unrelated column must never be changed.
        sheet.Cells(2, 9).Value = "USER MEMO"

        current_rows = [
            {"row": 2, "code": "7203", "label": "J1 BUY"},
            {"row": 3, "code": "6501", "label": "SSR-Ver1"},
        ]

        current_layout = board_rows_to_layout(current_rows)

        h1_codes = [
            "7203", "1002", "1003", "1004", "1005",
            "1006", "1007", "1008", "1009", "1010",
        ]

        layout = build_h1_board_layout(
            current_layout=current_layout,
            h1_codes=h1_codes,
            j1_codes=["7203"],
            early_volume_map={},
            snapshot_map={},
            floor_to_tick=lambda price: price,
            decision_enabled=False,
        )

        self.assertEqual(
            [layout[row][0] for row in range(2, 12)],
            h1_codes,
        )

        self.assertIn("J1", layout[2][1])
        self.assertIn("H1", layout[2][1])

        ssr_rows = [
            row for row in range(2, 22)
            if layout[row][0] == "6501"
        ]

        self.assertEqual(len(ssr_rows), 1)
        self.assertGreaterEqual(ssr_rows[0], 17)
        self.assertIn("SSR-Ver1", layout[ssr_rows[0]][1])

        changes = prepare_board_changes(sheet, layout)

        self.assertTrue(changes)
        self.assertTrue(
            all(col in (1, 8) for _, col, _, _ in changes)
        )

        before = {
            key: cell.Value
            for key, cell in sheet.cells.items()
        }

        dry_run_changes = update_board(
            sheet, layout, dry_run=True
        )

        after = {
            key: cell.Value
            for key, cell in sheet.cells.items()
        }

        self.assertEqual(changes, dry_run_changes)
        self.assertEqual(before, after)
        self.assertEqual(sheet.Cells(2, 9).Value, "USER MEMO")


if __name__ == "__main__":
    unittest.main()
