import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/intraday/rss_live_board.py"
)


class TestH1PreviewSafeReaderFailure(unittest.TestCase):

    def test_excel_connection_failure(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "read_board_preview_safe"
        ]

        self.assertEqual(len(functions), 1)

        connector = Mock(
            side_effect=RuntimeError(
                "Microsoft Excel RSS instance was not found."
            )
        )

        namespace = {
            "get_microsoft_excel": connector,
        }

        exec(
            compile(
                ast.Module(body=functions, type_ignores=[]),
                str(SOURCE),
                "exec",
            ),
            namespace,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "was not found",
        ):
            namespace["read_board_preview_safe"]()

        connector.assert_called_once_with(
            start_if_missing=False
        )


if __name__ == "__main__":
    unittest.main()
