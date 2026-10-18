import ast
import unittest
from pathlib import Path

SOURCE = Path("src/intraday/rss_morning_runner.py")


class TestH10932FailureGuard(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "run_capture"
        )

        target = next(
            node for node in ast.walk(function)
            if isinstance(node, ast.Try)
            and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "run_h1_0932_refill_filter"
                for statement in node.body
                for child in ast.walk(statement)
            )
        )

        cls.handler = target.handlers[0]

    def run_case(self, enabled):
        source = (
            "def test_guard():\n"
            "    try:\n"
            "        raise ValueError('simulated failure')\n"
            "    except Exception as exc:\n"
        )

        handler_lines = ast.unparse(
            ast.Module(
                body=self.handler.body,
                type_ignores=[],
            )
        ).splitlines()

        source += "\n".join(
            "        " + line
            for line in handler_lines
        ) + "\n"

        namespace = {
            "H1_FIXED_BOARD_WRITE_ENABLED": enabled,
        }

        exec(source, namespace)
        return namespace["test_guard"]

    def test_off_keeps_legacy_behavior(self):
        self.run_case(False)()

    def test_on_raises_and_stops(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "H1 FIXED BOARD FAILURE",
        ):
            self.run_case(True)()


if __name__ == "__main__":
    unittest.main()
