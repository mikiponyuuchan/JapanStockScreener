import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_h1_board_bridge import build_h1_board_layout


class TestH1DecisionIntegration(unittest.TestCase):

    def test_buy_wait_no_data_and_fixed_ranking(self):
        codes = ["1001", "1002", "1003"]

        board_0930 = build_h1_board_layout(
            current_layout={},
            h1_codes=codes,
            j1_codes=["2001"],
            early_volume_map={},
            snapshot_map={},
            floor_to_tick=lambda x: int(x),
            decision_enabled=False,
        )

        board_0932 = build_h1_board_layout(
            current_layout=board_0930,
            h1_codes=codes,
            j1_codes=None,
            early_volume_map={
                "1001": 1000,
                "1002": 1000,
            },
            snapshot_map={
                "1001": {"Volume": 1500, "Price": 1000},
                "1002": {"Volume": 2000, "Price": 1000},
            },
            floor_to_tick=lambda x: int(x),
            decision_enabled=True,
        )

        self.assertEqual(
            [board_0932[row][0] for row in range(2, 5)],
            codes,
        )

        self.assertEqual(
            board_0932[2][1],
            "H1 #1 BUY",
        )

        self.assertEqual(
            board_0932[3][1],
            "H1 #2 WAIT 995",
        )

        self.assertEqual(
            board_0932[4][1],
            "H1 #3 NO DATA",
        )

        self.assertEqual(board_0932[12][0], "2001")
        self.assertIn("J1 BUY", board_0932[12][1])


if __name__ == "__main__":
    unittest.main()
