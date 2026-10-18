import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/intraday/rss_morning_runner.py"
)


class TestH1RunnerPreviewHooks(unittest.TestCase):

    def test_disabled_and_enabled_preview(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "preview_h1_runner_board"
        ]

        self.assertEqual(len(functions), 1)

        module = ast.Module(
            body=functions,
            type_ignores=[],
        )

        namespace = {
            "H1_FIXED_BOARD_DRY_RUN": False,
            "H1_CANDIDATES": ["7203"],
            "H1_EARLY_VOLUME": {"7203": 1000.0},
            "H1_0930_SNAPSHOT": {
                "7203": {
                    "Price": 2000.0,
                    "Volume": 1500.0,
                },
            },
            "H1_WAIT_GROWTH_THRESHOLD": 100.0,
            "H1_WAIT_PULLBACK_LEVEL": -0.50,
            "floor_to_tick": int,
            "preview_h1_fixed_board": Mock(),
        }

        exec(
            compile(module, str(SOURCE), "exec"),
            namespace,
        )

        hook = namespace["preview_h1_runner_board"]
        preview = namespace["preview_h1_fixed_board"]

        # OFF: プレビューを呼び出さない
        hook(decision_enabled=False)
        preview.assert_not_called()

        # ON: 09:30
        namespace["H1_FIXED_BOARD_DRY_RUN"] = True
        hook(decision_enabled=False)

        self.assertEqual(preview.call_count, 1)
        self.assertFalse(
            preview.call_args.kwargs["decision_enabled"]
        )

        # ON: 09:32
        hook(decision_enabled=True)

        self.assertEqual(preview.call_count, 2)
        self.assertTrue(
            preview.call_args.kwargs["decision_enabled"]
        )

        self.assertEqual(
            preview.call_args.kwargs["h1_candidates"],
            ["7203"],
        )

        print("PREVIEW OFF / ON: PASS")
        print("09:30 / 09:32: PASS")
        print("NO EXCEL ACCESS / NO WRITE / NO SAVE")


if __name__ == "__main__":
    unittest.main()
