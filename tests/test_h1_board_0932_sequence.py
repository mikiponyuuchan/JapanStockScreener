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
)
from tests.test_rss_board_rollback import FakeSheet


class TestH1Board0932Sequence(unittest.TestCase):

    def test_0930_to_0932_buy_wait_no_data(self):
        sheet = FakeSheet()

        sheet.Cells(2, 1).Value = "7203"
        sheet.Cells(2, 8).Value = "J1 BUY"

        sheet.Cells(3, 1).Value = "6501"
        sheet.Cells(3, 8).Value = "SSR-Ver1"

        rows = [
            {"row": 2, "code": "7203", "label": "J1 BUY"},
            {"row": 3, "code": "6501", "label": "SSR-Ver1"},
        ]

        h1_codes = [
            "7203", "1002", "1003", "1004", "1005",
            "1006", "1007", "1008", "1009", "1010",
        ]

        board_0930 = build_h1_board_layout(
            current_layout=board_rows_to_layout(rows),
            h1_codes=h1_codes,
            j1_codes=["7203"],
            early_volume_map={},
            snapshot_map={},
            floor_to_tick=lambda price: price,
            decision_enabled=False,
        )

        early = {
            "7203": 1000,
            "1002": 1000,
        }

        snapshot = {
            "7203": {"Volume": 1500, "Price": 2000},
            "1002": {"Volume": 2500, "Price": 1000},
        }

        board_0932 = build_h1_board_layout(
            current_layout=board_0930,
            h1_codes=h1_codes,
            j1_codes=None,
            early_volume_map=early,
            snapshot_map=snapshot,
            floor_to_tick=lambda price: int(price),
            decision_enabled=True,
        )

        self.assertEqual(
            [board_0932[row][0] for row in range(2, 12)],
            h1_codes,
        )

        self.assertIn("H1 #1 BUY", board_0932[2][1])
        self.assertIn("J1 BUY", board_0932[2][1])
        self.assertIn("H1 #2 WAIT 995", board_0932[3][1])
        self.assertIn("H1 #3 NO DATA", board_0932[4][1])

        ssr = [
            row for row in range(17, 22)
            if board_0932[row][0] == "6501"
        ]

        self.assertEqual(len(ssr), 1)
        self.assertIn("SSR-Ver1", board_0932[ssr[0]][1])

        changes = prepare_board_changes(
            sheet, board_0932
        )

        self.assertTrue(changes)
        self.assertTrue(
            all(col in (1, 8) for _, col, _, _ in changes)
        )

        self.assertEqual(sheet.Cells(2, 1).Value, "7203")
        self.assertEqual(sheet.Cells(2, 8).Value, "J1 BUY")
        self.assertEqual(sheet.Cells(3, 1).Value, "6501")
        self.assertEqual(sheet.Cells(3, 8).Value, "SSR-Ver1")


if __name__ == "__main__":
    unittest.main()
