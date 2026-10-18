import unittest
from unittest.mock import patch

from intraday.rss_h1_board_preview import preview_h1_fixed_board


class TestH1PreviewJ1(unittest.TestCase):

    def test_j1_codes_forwarded(self):
        expected = {row: ("", "") for row in range(2, 22)}

        with patch(
            "intraday.rss_h1_board_preview.prepare_h1_fixed_board",
            return_value=expected,
        ) as adapter:

            result = preview_h1_fixed_board(
                current_rows=[],
                h1_candidates=["1001", "1002"],
                early_volume_map={},
                snapshot_map={},
                floor_to_tick=lambda price: price,
                j1_codes=["1001", "6501"],
            )

        self.assertEqual(result, expected)
        self.assertEqual(
            adapter.call_args.kwargs["j1_codes"],
            ["1001", "6501"],
        )

        print("J1 ARGUMENT FORWARDING: PASS")
        print("NO EXCEL ACCESS / NO WRITE / NO SAVE")


if __name__ == "__main__":
    unittest.main()
