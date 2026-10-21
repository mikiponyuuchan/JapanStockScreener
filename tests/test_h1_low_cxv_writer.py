import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.h1_low_cxv_selector import select_h1_low_cxv


class TestLowCxVWriterContract(unittest.TestCase):

    def test_selector_returns_at_most_three_candidates(self):
        import pandas as pd

        candidates = pd.DataFrame([
            {"CodeX": str(1000 + i), "ChangeX": 5.0,
             "CxV": float(i), "VolumeX": 2.0,
             "NameX": f"Stock{i}"}
            for i in range(1, 11)
        ])

        result = select_h1_low_cxv(candidates)

        self.assertLessEqual(len(result), 3)
        self.assertEqual(
            list(result["LowCxVRank"]),
            list(range(1, len(result) + 1)),
        )

    def test_empty_candidates_do_not_require_board_assignments(self):
        import pandas as pd

        candidates = pd.DataFrame(
            columns=["CodeX", "ChangeX", "CxV", "VolumeX", "NameX"]
        )

        result = select_h1_low_cxv(candidates)

        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
