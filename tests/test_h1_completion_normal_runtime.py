import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock


SOURCE = Path("src/intraday/rss_morning_runner.py")


class TestH1CompletionNormalRuntime(unittest.TestCase):

    def make_runner(self, case, save_failure=False):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_h1_hybrid_wait_live"
        )

        early_volume = {
            "BUY": 100,
            "WAIT": 100,
            "NO_DATA": None,
        }[case]

        volume_0930 = {
            "BUY": 150,
            "WAIT": 250,
            "NO_DATA": 150,
        }[case]

        save_mock = MagicMock()

        if save_failure:
            save_mock.side_effect = RuntimeError(
                "SIMULATED SAVE FAILURE"
            )

        namespace = {
            "H1_FIXED_BOARD_WRITE_ENABLED": True,
            "H1_HYBRID_DECISION_DONE": False,
            "H1_CANDIDATES": ["7203"],
            "H1_EARLY_VOLUME": {
                "7203": early_volume,
            },
            "H1_0930_SNAPSHOT": {
                "7203": {
                    "Price": 3000,
                    "Volume": volume_0930,
                }
            },
            "H1_WAIT_GROWTH_THRESHOLD": 100.0,
            "H1_WAIT_PULLBACK_LEVEL": -0.50,
            "floor_to_tick": lambda x: int(x),
            "_safe_float": lambda x: (
                None if x is None else float(x)
            ),
            "update_h1_fixed_board_live": save_mock,
            "add_candidate": MagicMock(),
        }

        exec(
            compile(
                ast.Module(
                    body=[function],
                    type_ignores=[],
                ),
                str(SOURCE),
                "exec",
            ),
            namespace,
        )

        return namespace

    def test_save_success(self):
        for case in ("BUY", "WAIT", "NO_DATA"):
            with self.subTest(case=case):
                ns = self.make_runner(
                    case,
                    save_failure=False,
                )

                ns["update_h1_hybrid_wait_live"]()

                self.assertIs(
                    ns["H1_HYBRID_DECISION_DONE"],
                    True,
                )

                ns[
                    "update_h1_fixed_board_live"
                ].assert_called_once_with(
                    decision_enabled=True
                )

                ns["add_candidate"].assert_not_called()

    def test_save_failure(self):
        for case in ("BUY", "WAIT", "NO_DATA"):
            with self.subTest(case=case):
                ns = self.make_runner(
                    case,
                    save_failure=True,
                )

                with self.assertRaisesRegex(
                    RuntimeError,
                    "SIMULATED SAVE FAILURE",
                ):
                    ns["update_h1_hybrid_wait_live"]()

                self.assertIs(
                    ns["H1_HYBRID_DECISION_DONE"],
                    False,
                )

                ns[
                    "update_h1_fixed_board_live"
                ].assert_called_once_with(
                    decision_enabled=True
                )

                ns["add_candidate"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
