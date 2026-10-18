import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_h1_board_adapter import prepare_h1_fixed_board


class TestH1RunnerDataConnection(unittest.TestCase):

    def test_0930_to_0932_with_runner_data(self):
        # Morning Runnerと同じ形式のデータ
        h1_candidates = [
            "7203", "1002", "1003", "1004", "1005",
            "1006", "1007", "1008", "1009", "1010",
        ]

        early_volume = {
            "7203": 1000.0,
            "1002": 1000.0,
        }

        snapshot_0930 = {
            "7203": {"Price": 2000.0, "Volume": 1500.0},
            "1002": {"Price": 1000.0, "Volume": 2500.0},
        }

        # J1が先に登録されている状態を再現
        current_rows = [
            {"row": 2, "code": "7203", "label": "J1 BUY"},
        ]

        board_0930 = prepare_h1_fixed_board(
            current_rows=current_rows,
            h1_candidates=h1_candidates,
            early_volume_map=early_volume,
            snapshot_map=snapshot_0930,
            floor_to_tick=int,
            j1_codes=None,
            decision_enabled=False,
        )

        self.assertEqual(
            [board_0930[r][0] for r in range(2, 12)],
            h1_candidates,
        )
        self.assertIn("J1 BUY", board_0930[2][1])

        # 09:30の結果を09:32へ引き継ぐ
        rows_0930 = [
            {"row": row, "code": code, "label": label}
            for row, (code, label) in board_0930.items()
            if code
        ]

        board_0932 = prepare_h1_fixed_board(
            current_rows=rows_0930,
            h1_candidates=h1_candidates,
            early_volume_map=early_volume,
            snapshot_map=snapshot_0930,
            floor_to_tick=int,
            j1_codes=None,
            decision_enabled=True,
        )

        self.assertEqual(
            [board_0932[r][0] for r in range(2, 12)],
            h1_candidates,
        )
        self.assertIn("H1 #1 BUY", board_0932[2][1])
        self.assertIn("J1 BUY", board_0932[2][1])
        self.assertIn("H1 #2 WAIT 995", board_0932[3][1])
        self.assertIn("H1 #3 NO DATA", board_0932[4][1])

        print("RUNNER DATA CONNECTION: PASS")
        print("H1 RANK / J1 LABEL: PRESERVED")
        print("NO EXCEL ACCESS / NO WRITE / NO SAVE")


if __name__ == "__main__":
    unittest.main()
