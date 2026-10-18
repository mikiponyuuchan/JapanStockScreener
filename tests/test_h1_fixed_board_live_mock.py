import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SOURCE = Path("src/intraday/rss_morning_runner.py")


class TestH1FixedBoardLiveMock(unittest.TestCase):

    def test_fixed_board_live_0930_and_0932(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_h1_fixed_board_live"
        )

        # Compile only this function, without running
        # the morning runner or importing Excel COM.
        isolated = ast.Module(
            body=[function],
            type_ignores=[],
        )
        namespace = {
            "H1_FIXED_BOARD_WRITE_ENABLED": True,
            "H1_CANDIDATES": ["7203"],
            "H1_EARLY_VOLUME": {"7203": 100},
            "H1_0930_SNAPSHOT": {
                "7203": {"Price": 3000, "Volume": 250}
            },
            "J1_CODES": [],
            "H1_WAIT_GROWTH_THRESHOLD": 100.0,
            "H1_WAIT_PULLBACK_LEVEL": -0.50,
            "floor_to_tick": lambda price: int(price),
            "Path": Path,
        }

        exec(
            compile(isolated, str(SOURCE), "exec"),
            namespace,
        )

        sheet = MagicMock()
        sheet.Cells.return_value.Value = ""

        excel = MagicMock()
        book = MagicMock()
        namespace["get_live_board"] = MagicMock(
            return_value=(excel, book, sheet)
        )

        prepared_layouts = []

        def fake_prepare(**kwargs):
            prepared_layouts.append(kwargs)
            return {row: ("", "") for row in range(2, 22)}

        with patch(
            "intraday.rss_h1_board_adapter.prepare_h1_fixed_board",
            side_effect=fake_prepare,
        ), patch(
            "intraday.rss_board_transaction.execute_and_save_verified_board",
            return_value=[],
        ) as save:
            namespace["update_h1_fixed_board_live"](
                decision_enabled=False
            )
            namespace["update_h1_fixed_board_live"](
                decision_enabled=True
            )

        self.assertEqual(len(prepared_layouts), 2)
        self.assertFalse(
            prepared_layouts[0]["decision_enabled"]
        )
        self.assertTrue(
            prepared_layouts[1]["decision_enabled"]
        )

        self.assertEqual(
            prepared_layouts[0]["current_rows"][0],
            {"row": 2, "code": "", "label": ""},
        )
        self.assertEqual(
            prepared_layouts[1]["h1_candidates"],
            ["7203"],
        )
        self.assertEqual(save.call_count, 2)
        self.assertEqual(
            namespace["H1_FIXED_BOARD_WRITE_ENABLED"],
            True,
        )

    def test_disabled_switch_blocks_connection(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_h1_fixed_board_live"
        )

        namespace = {
            "H1_FIXED_BOARD_WRITE_ENABLED": False,
        }

        exec(
            compile(
                ast.Module(body=[function], type_ignores=[]),
                str(SOURCE),
                "exec",
            ),
            namespace,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "production write is disabled",
        ):
            namespace["update_h1_fixed_board_live"](
                decision_enabled=False
            )


if __name__ == "__main__":
    unittest.main()
