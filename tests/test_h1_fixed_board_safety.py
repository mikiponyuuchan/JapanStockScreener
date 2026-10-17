import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_fixed_layout import build_fixed_layout


def empty_board():
    return {row: ("", "") for row in range(2, 22)}


class TestH1FixedBoardSafety(unittest.TestCase):

    def test_duplicate_h1_blocked(self):
        board = empty_board()

        with self.assertRaisesRegex(
            ValueError, "Duplicate H1 codes"
        ):
            build_fixed_layout(
                board,
                ["1001", "1002", "1001"],
                [],
            )

    def test_ssr_protected_when_stock_moves_to_h1(self):
        board = empty_board()
        board[17] = ("3001", "SSR-Ver2")

        result = build_fixed_layout(
            board,
            ["3001", "1002"],
            [],
        )

        self.assertEqual(result[2][0], "3001")
        self.assertIn("SSR-Ver2", result[2][1])
        self.assertEqual(result[17], ("", ""))

        codes = [
            code for code, label in result.values()
            if code
        ]
        self.assertEqual(len(codes), len(set(codes)))

    def test_relocation_capacity_blocked(self):
        board = empty_board()

        # Five protected stocks already occupy overflow rows.
        for row in range(17, 22):
            board[row] = (
                str(3000 + row),
                "SSR-Ver2",
            )

        # A sixth protected stock is displaced from H1.
        board[2] = ("4001", "SSR-Ver1")

        with self.assertRaisesRegex(
            RuntimeError,
            "PROTECTED RELOCATION BLOCKED",
        ):
            build_fixed_layout(
                board,
                ["1001"],
                [],
            )


if __name__ == "__main__":
    unittest.main()
