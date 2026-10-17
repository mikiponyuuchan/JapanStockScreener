import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from intraday.rss_board_fixed_layout import build_fixed_layout


class TestH1J1Overlap(unittest.TestCase):

    def test_j1_label_preserved_when_code_is_also_h1(self):
        current = {
            12: ("7203", "J1 BUY"),
            17: ("6501", "SSR-Ver1"),
        }

        layout = build_fixed_layout(
            current_layout=current,
            h1_codes=["7203"],
            j1_codes=["7203"],
        )

        code, label = layout[2]

        self.assertEqual(code, "7203")
        self.assertIn("H1 CAND #1", label)
        self.assertIn("J1 BUY", label)

    def test_ssr_label_preserved_with_h1_j1_overlap(self):
        current = {
            12: ("7203", "J1 BUY / SSR-Ver1"),
        }

        layout = build_fixed_layout(
            current_layout=current,
            h1_codes=["7203"],
            j1_codes=["7203"],
        )

        code, label = layout[2]

        self.assertEqual(code, "7203")
        self.assertIn("J1 BUY", label)
        self.assertIn("SSR-Ver1", label)


if __name__ == "__main__":
    unittest.main()
