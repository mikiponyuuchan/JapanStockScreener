import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock

SOURCE = Path("src/intraday/rss_morning_runner.py")


class TestH1CompletionRuntime(unittest.TestCase):

    def make_runner(self, candidates):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_h1_hybrid_wait_live"
        )

        namespace = {
            "H1_FIXED_BOARD_WRITE_ENABLED": True,
            "H1_HYBRID_DECISION_DONE": False,
            "H1_CANDIDATES": candidates,
            "update_h1_fixed_board_live": MagicMock(
                side_effect=RuntimeError("SIMULATED SAVE FAILURE")
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
        return namespace

    def test_empty_candidates_save_failure(self):
        ns = self.make_runner([])

        with self.assertRaisesRegex(
            RuntimeError, "SIMULATED SAVE FAILURE"
        ):
            ns["update_h1_hybrid_wait_live"]()

        self.assertIs(
            ns["H1_HYBRID_DECISION_DONE"], False
        )
        ns["update_h1_fixed_board_live"].assert_called_once_with(
            decision_enabled=True
        )

    def test_empty_candidates_save_success(self):
        ns = self.make_runner([])
        ns["update_h1_fixed_board_live"].side_effect = None

        ns["update_h1_hybrid_wait_live"]()

        self.assertIs(
            ns["H1_HYBRID_DECISION_DONE"], True
        )
        ns["update_h1_fixed_board_live"].assert_called_once_with(
            decision_enabled=True
        )


if __name__ == "__main__":
    unittest.main()
