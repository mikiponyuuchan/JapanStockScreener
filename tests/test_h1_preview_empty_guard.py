import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


SOURCE = Path("src/intraday/rss_morning_runner.py")


class TestH1PreviewEmptyGuard(unittest.TestCase):

    def test_empty_board_blocks_preview(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "preview_h1_runner_board"
        )

        module = ast.Module(body=[function], type_ignores=[])

        reader = Mock(return_value=[])
        preview = Mock()

        namespace = {
            "H1_FIXED_BOARD_DRY_RUN": True,
            "read_board_preview_safe": reader,
            "preview_h1_fixed_board": preview,
        }

        exec(
            compile(module, str(SOURCE), "exec"),
            namespace,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "H1 PREVIEW BLOCKED: existing board is empty",
        ):
            namespace["preview_h1_runner_board"](
                decision_enabled=False
            )

        reader.assert_called_once_with()
        preview.assert_not_called()


if __name__ == "__main__":
    unittest.main()
