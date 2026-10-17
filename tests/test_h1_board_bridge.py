import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_h1_board_bridge import build_h1_board_layout


class TestH1BoardBridge(unittest.TestCase):

    def test_0930_to_0932_keeps_h1_ranking(self):
        h1_codes = [str(1001 + i) for i in range(10)]

        board_0930 = build_h1_board_layout(
            current_layout={},
            h1_codes=h1_codes,
            j1_codes=["2001", "2002"],
            early_volume_map={},
            snapshot_map={},
            floor_to_tick=lambda price: price,
            decision_enabled=False,
        )

        self.assertEqual(
            [board_0930[row][0] for row in range(2, 12)],
            h1_codes,
        )

        decisions = {
            code: f"H1 BUY #{rank}"
            for rank, code in enumerate(h1_codes, 1)
        }

        with patch(
            "intraday.rss_h1_board_bridge.build_h1_decisions",
            return_value=decisions,
        ) as mock_decisions:

            board_0932 = build_h1_board_layout(
                current_layout=board_0930,
                h1_codes=h1_codes,
                j1_codes=None,
                early_volume_map={},
                snapshot_map={},
                floor_to_tick=lambda price: price,
                decision_enabled=True,
            )

        mock_decisions.assert_called_once()

        for rank, code in enumerate(h1_codes, 1):
            row = rank + 1
            self.assertEqual(board_0932[row][0], code)
            self.assertIn("H1 BUY", board_0932[row][1])

        self.assertEqual(board_0932[12][0], "2001")
        self.assertEqual(board_0932[13][0], "2002")


if __name__ == "__main__":
    unittest.main()
