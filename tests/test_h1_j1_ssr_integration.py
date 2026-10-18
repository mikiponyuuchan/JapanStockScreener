import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_h1_board_bridge import build_h1_board_layout
from intraday.rss_board_safe_writer import validate_board_layout


class TestH1J1SSRIntegration(unittest.TestCase):

    def test_overlap_preserves_ssr(self):
        current = {
            row: ("", "")
            for row in range(2, 22)
        }

        current[17] = ("7203", "SSR-Ver2")
        current[18] = ("3001", "SSR-Ver1")

        result = build_h1_board_layout(
            current_layout=current,
            h1_codes=["7203"],
            j1_codes=["7203", "6501"],
            early_volume_map={},
            snapshot_map={},
            floor_to_tick=lambda price: price,
            decision_enabled=False,
        )

        validate_board_layout(result)

        self.assertEqual(result[2][0], "7203")
        self.assertIn("H1 CAND #1", result[2][1])
        self.assertIn("J1 BUY", result[2][1])
        self.assertIn("SSR-Ver2", result[2][1])

        self.assertEqual(result[12], ("6501", "J1 BUY"))
        self.assertEqual(result[17], ("", ""))
        self.assertEqual(result[18], ("3001", "SSR-Ver1"))

        codes = [
            code for code, label in result.values()
            if code
        ]

        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main()
