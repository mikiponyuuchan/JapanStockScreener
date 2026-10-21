import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_fixed_layout import build_fixed_layout


class TestH1LowCxVFreeRows(unittest.TestCase):

    def test_existing_low_cxv_and_overflow_are_preserved(self):
        current = {
            row: ("", "")
            for row in range(2, 22)
        }

        current[12] = ("9563", "LOW-CxV #1")
        current[13] = ("4288", "LOW-CxV #2")
        current[14] = ("9478", "LOW-CxV #3")
        current[17] = ("3001", "SSR-Ver1")
        current[18] = ("3002", "SSR-Ver2")

        h1 = [str(1000 + i) for i in range(1, 11)]

        result = build_fixed_layout(
            current_layout=current,
            h1_codes=h1,
            j1_codes=None,
        )

        for row, expected in {
            12: ("9563", "LOW-CxV #1"),
            13: ("4288", "LOW-CxV #2"),
            14: ("9478", "LOW-CxV #3"),
            17: ("3001", "SSR-Ver1"),
            18: ("3002", "SSR-Ver2"),
        }.items():
            self.assertEqual(result[row], expected)

        codes = [
            code for code, label in result.values()
            if code
        ]
        self.assertEqual(len(codes), len(set(codes)))

    def test_empty_rows_are_available_without_overwriting_protected_rows(self):
        current = {
            row: ("", "")
            for row in range(2, 22)
        }

        current[12] = ("9563", "LOW-CxV #1")
        current[17] = ("3001", "SSR-Ver1")
        current[19] = ("3002", "SSR-Ver2")

        h1 = [str(1000 + i) for i in range(1, 11)]

        result = build_fixed_layout(
            current_layout=current,
            h1_codes=h1,
            j1_codes=None,
        )

        free_rows = [
            row for row in range(15, 22)
            if not result[row][0] and not result[row][1]
        ]

        self.assertTrue(free_rows)
        self.assertEqual(result[17], ("3001", "SSR-Ver1"))
        self.assertEqual(result[19], ("3002", "SSR-Ver2"))

    def test_low_cxv_code_is_not_duplicated_in_h1(self):
        current = {
            row: ("", "")
            for row in range(2, 22)
        }

        current[12] = ("1001", "LOW-CxV #1")

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate H1 codes",
        ):
            build_fixed_layout(
                current_layout=current,
                h1_codes=["1001", "1002", "1001"],
                j1_codes=None,
            )


if __name__ == "__main__":
    unittest.main()
