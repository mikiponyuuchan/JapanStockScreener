import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from intraday.rss_board_fixed_layout import build_fixed_layout


class TestH1J1Update0932(unittest.TestCase):

    def test_j1_label_survives_h1_decision_update(self):
        initial = {
            12: ("7203", "J1 BUY"),
            17: ("6501", "SSR-Ver1"),
        }

        layout_0930 = build_fixed_layout(
            current_layout=initial,
            h1_codes=["7203"],
            j1_codes=["7203"],
        )

        self.assertIn("J1 BUY", layout_0930[2][1])

        layout_0932 = build_fixed_layout(
            current_layout=layout_0930,
            h1_codes=["7203"],
            j1_codes=None,
            h1_decisions={
                "7203": "H1 #1 WAIT 995",
            },
        )

        self.assertEqual(layout_0932[2][0], "7203")
        self.assertIn("H1 #1 WAIT 995", layout_0932[2][1])
        self.assertIn("J1 BUY", layout_0932[2][1])
        self.assertEqual(layout_0932[17], ("6501", "SSR-Ver1"))


if __name__ == "__main__":
    unittest.main()
