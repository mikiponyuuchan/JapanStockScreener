import ast
import unittest
from pathlib import Path


SOURCE = Path("src/intraday/rss_morning_runner.py")


class TestH1ProductionSwitch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

    def test_production_switch_defaults_off(self):
        assignments = [
            node for node in cls_tree_body(self.tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "H1_FIXED_BOARD_WRITE_ENABLED"
                for target in node.targets
            )
        ]
        self.assertEqual(len(assignments), 1)
        self.assertIs(assignments[0].value.value, False)

    def test_fixed_board_has_both_stages(self):
        calls = [
            node for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "update_h1_fixed_board_live"
        ]

        stages = [
            keyword.value.value
            for call in calls
            for keyword in call.keywords
            if keyword.arg == "decision_enabled"
            and isinstance(keyword.value, ast.Constant)
        ]

        self.assertIn(False, stages)
        self.assertIn(True, stages)

    def test_legacy_writes_are_guarded(self):
        functions = [
            node for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        guarded = 0

        for function in functions:
            for node in ast.walk(function):
                if not isinstance(node, ast.If):
                    continue

                condition = node.test

                if not (
                    isinstance(condition, ast.UnaryOp)
                    and isinstance(condition.op, ast.Not)
                    and isinstance(condition.operand, ast.Name)
                    and condition.operand.id
                    == "H1_FIXED_BOARD_WRITE_ENABLED"
                ):
                    continue

                guarded += 1

        self.assertGreaterEqual(guarded, 6)


def cls_tree_body(tree):
    return tree.body


if __name__ == "__main__":
    unittest.main()
