import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


SOURCE = Path("src/intraday/rss_morning_runner.py")


class TestH1CompletionSafety(unittest.TestCase):

    def test_completion_flag_after_fixed_board_save(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_h1_hybrid_wait_live"
        )

        save_calls = [
            node for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "update_h1_fixed_board_live"
        ]

        true_assignments = [
            node for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
            and any(
                isinstance(target, ast.Name)
                and target.id == "H1_HYBRID_DECISION_DONE"
                for target in node.targets
            )
        ]

        self.assertEqual(len(save_calls), 2)
        self.assertEqual(len(true_assignments), 2)

        # Each fixed-board update must be followed
        # by a completion assignment.
        save_lines = sorted(node.lineno for node in save_calls)
        done_lines = sorted(node.lineno for node in true_assignments)

        for save_line, done_line in zip(save_lines, done_lines):
            self.assertLess(save_line, done_line)

    def test_save_failure_propagates(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_h1_fixed_board_live"
        )

        namespace = {
            "H1_FIXED_BOARD_WRITE_ENABLED": True,
            "H1_CANDIDATES": ["7203"],
            "H1_EARLY_VOLUME": {},
            "H1_0930_SNAPSHOT": {},
            "J1_CODES": [],
            "H1_WAIT_GROWTH_THRESHOLD": 100.0,
            "H1_WAIT_PULLBACK_LEVEL": -0.50,
            "floor_to_tick": lambda x: x,
            "Path": Path,
            "get_live_board": MagicMock(
                return_value=(
                    MagicMock(),
                    MagicMock(),
                    MagicMock(),
                )
            ),
        }

        exec(
            compile(
                ast.Module(body=[function], type_ignores=[]),
                str(SOURCE),
                "exec",
            ),
            namespace,
        )

        with patch(
            "intraday.rss_h1_board_adapter.prepare_h1_fixed_board",
            return_value={row: ("", "") for row in range(2, 22)},
        ), patch(
            "intraday.rss_board_transaction.execute_and_save_verified_board",
            side_effect=RuntimeError("BOARD SAVE FAILED"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "BOARD SAVE FAILED",
            ):
                namespace["update_h1_fixed_board_live"](
                    decision_enabled=True
                )


if __name__ == "__main__":
    unittest.main()
