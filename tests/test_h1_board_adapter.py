import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_h1_board_adapter import (
    prepare_h1_fixed_board,
)


class TestH1BoardAdapter(unittest.TestCase):

    def test_0930_to_0932(self):
        codes = [
            "7203", "1002", "1003", "1004", "1005",
            "1006", "1007", "1008", "1009", "1010",
        ]

        rows = [
            {"row": 2, "code": "7203", "label": "J1 BUY"},
            {"row": 3, "code": "6501", "label": "SSR-Ver1"},
        ]

        board_0930 = prepare_h1_fixed_board(
            current_rows=rows,
            h1_candidates=codes,
            early_volume_map={},
            snapshot_map={},
            floor_to_tick=int,
            j1_codes=["7203"],
            decision_enabled=False,
        )

        self.assertEqual(
            [board_0930[r][0] for r in range(2, 12)],
            codes,
        )
        self.assertIn("J1 BUY", board_0930[2][1])
        self.assertEqual(board_0930[17][0], "6501")

        rows_0930 = [
            {"row": r, "code": code, "label": label}
            for r, (code, label) in board_0930.items()
            if code
        ]

        board_0932 = prepare_h1_fixed_board(
            current_rows=rows_0930,
            h1_candidates=codes,
            early_volume_map={
                "7203": 1000,
                "1002": 1000,
            },
            snapshot_map={
                "7203": {
                    "Volume": 1500,
                    "Price": 2000,
                },
                "1002": {
                    "Volume": 2500,
                    "Price": 1000,
                },
            },
            floor_to_tick=int,
            j1_codes=None,
            decision_enabled=True,
        )

        self.assertEqual(
            [board_0932[r][0] for r in range(2, 12)],
            codes,
        )
        self.assertIn("H1 #1 BUY", board_0932[2][1])
        self.assertIn("J1 BUY", board_0932[2][1])
        self.assertIn("H1 #2 WAIT 995", board_0932[3][1])
        self.assertIn("H1 #3 NO DATA", board_0932[4][1])
        self.assertEqual(board_0932[17][0], "6501")
        self.assertIn("SSR-Ver1", board_0932[17][1])


if __name__ == "__main__":
    unittest.main()
