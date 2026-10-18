import unittest

from intraday.rss_board_fixed_layout import build_fixed_layout


class TestH1DisplacedStaleLabels(unittest.TestCase):

    def test_displaced_ssr_has_no_old_h1_label(self):
        current = {
            row: ("", "")
            for row in range(2, 22)
        }
        current[2] = ("6182", "H1 CAND #1 / SSR")

        new_codes = [
            "367A", "372A", "3791", "3915", "5242",
            "5025", "4490", "6721", "6501", "8035"
        ]

        result = build_fixed_layout(
            current_layout=current,
            h1_codes=new_codes,
            j1_codes=[],
        )

        displaced = [
            (row, code, label)
            for row, (code, label) in result.items()
            if code == "6182"
        ]

        self.assertEqual(len(displaced), 1)
        row, code, label = displaced[0]

        self.assertGreaterEqual(row, 17)
        self.assertEqual(label, "SSR")


if __name__ == "__main__":
    unittest.main()
