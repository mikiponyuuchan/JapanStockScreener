import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_fixed_layout import build_fixed_layout


class TestH1LowCxVLayout(unittest.TestCase):

    def test_low_cxv_rows_survive_0932_update(self):
        current = {
            row: ("", "")
            for row in range(2, 22)
        }

        # LOW-CxV dedicated rows
        current[12] = ("9563", "LOW-CxV #1")
        current[13] = ("4288", "LOW-CxV #2")
        current[14] = ("9478", "LOW-CxV #3")

        # Other existing rows must remain intact
        current[17] = ("3001", "SSR-Ver1")
        current[18] = ("3002", "SSR-Ver2")

        h1 = [str(1000 + i) for i in range(1, 11)]

        board_0930 = build_fixed_layout(
            current_layout=current,
            h1_codes=h1,
            j1_codes=[],
            h1_decisions=None,
        )

        expected_low_cxv = {
            12: ("9563", "LOW-CxV #1"),
            13: ("4288", "LOW-CxV #2"),
            14: ("9478", "LOW-CxV #3"),
        }

        for row, expected in expected_low_cxv.items():
            self.assertEqual(board_0930[row], expected)

        decisions = {
            code: f"H1 #{rank} WAIT"
            for rank, code in enumerate(h1, start=1)
        }

        board_0932 = build_fixed_layout(
            current_layout=board_0930,
            h1_codes=h1,
            j1_codes=None,
            h1_decisions=decisions,
        )

        for row, expected in expected_low_cxv.items():
            self.assertEqual(board_0932[row], expected)

        self.assertEqual(board_0932[17], ("3001", "SSR-Ver1"))
        self.assertEqual(board_0932[18], ("3002", "SSR-Ver2"))

        codes = [
            code for code, label in board_0932.values()
            if code
        ]
        self.assertEqual(len(codes), len(set(codes)))

        print()
        print("LOW-CxV rows 12-14 preserved : PASS")
        print("H1 09:32 update              : PASS")
        print("Existing overflow preserved  : PASS")
        print("Duplicate prevention         : PASS")
        print("NO EXCEL ACCESS / NO WRITE / NO SAVE")


if __name__ == "__main__":
    unittest.main()
