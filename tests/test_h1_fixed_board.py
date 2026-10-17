import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "intraday"))

from rss_h1_board_bridge import build_h1_board_layout
from intraday.rss_board_safe_writer import validate_board_layout


class TestH1FixedBoard(unittest.TestCase):

    def test_0930_to_0932(self):
        h1 = [str(1000 + i) for i in range(1, 11)]
        j1 = [str(2000 + i) for i in range(1, 6)]

        current = {
            row: ("", "")
            for row in range(2, 22)
        }

        current[17] = ("3001", "SSR-Ver1")
        current[18] = ("3002", "SSR-Ver2")

        def floor_to_tick(value):
            return int(value)

        early = {code: 100 for code in h1}

        snapshot = {
            code: {
                "Price": 1000,
                "Volume": 150 if i % 3 == 0
                          else 250 if i % 3 == 1
                          else None,
            }
            for i, code in enumerate(h1)
        }

        # 09:30: TOP10 candidate labels
        board_0930 = build_h1_board_layout(
            current_layout=current,
            h1_codes=h1,
            j1_codes=j1,
            early_volume_map=early,
            snapshot_map=snapshot,
            floor_to_tick=floor_to_tick,
            decision_enabled=False,
        )

        validate_board_layout(board_0930)

        for rank, code in enumerate(h1, start=1):
            self.assertEqual(
                board_0930[rank + 1],
                (code, f"H1 CAND #{rank}"),
            )

        # 09:32: all TOP10 receive decisions
        board_0932 = build_h1_board_layout(
            current_layout=board_0930,
            h1_codes=h1,
            j1_codes=None,
            early_volume_map=early,
            snapshot_map=snapshot,
            floor_to_tick=floor_to_tick,
            decision_enabled=True,
        )

        validate_board_layout(board_0932)

        for rank, code in enumerate(h1, start=1):
            row = rank + 1
            actual_code, label = board_0932[row]

            self.assertEqual(actual_code, code)
            self.assertTrue(
                label.startswith(f"H1 #{rank} ")
            )
            self.assertTrue(
                any(
                    decision in label
                    for decision in ("BUY", "WAIT", "NO DATA")
                )
            )

        # J1 and SSR must remain intact
        for row in range(12, 17):
            self.assertEqual(
                board_0932[row],
                board_0930[row],
            )

        for row in range(17, 22):
            self.assertEqual(
                board_0932[row],
                board_0930[row],
            )

        # No duplicate stock codes
        codes = [
            code
            for code, label in board_0932.values()
            if code
        ]
        self.assertEqual(len(codes), len(set(codes)))

        print()
        print("H1 TOP10 09:30 -> 09:32 : PASS")
        print("J1 / SSR preservation   : PASS")
        print("Duplicate prevention    : PASS")
        print("NO EXCEL ACCESS / NO WRITE / NO SAVE")


if __name__ == "__main__":
    unittest.main()
