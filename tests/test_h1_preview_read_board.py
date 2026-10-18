import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/intraday/rss_morning_runner.py"
)


class TestH1PreviewReadBoard(unittest.TestCase):

    def make_hook(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "preview_h1_runner_board"
        ]

        self.assertEqual(len(functions), 1)

        rows = [
            {"row": 2, "code": "7203", "label": "J1 BUY"},
            {"row": 17, "code": "3001", "label": "SSR-Ver2"},
        ]

        reader = Mock(return_value=rows)
        preview = Mock()

        namespace = {
            "H1_FIXED_BOARD_DRY_RUN": False,
            "H1_CANDIDATES": ["7203"],
            "J1_CODES": ["7203", "6501"],
            "H1_EARLY_VOLUME": {},
            "H1_0930_SNAPSHOT": {},
            "H1_WAIT_GROWTH_THRESHOLD": 100.0,
            "H1_WAIT_PULLBACK_LEVEL": -0.50,
            "floor_to_tick": int,
            "read_board": reader,
            "preview_h1_fixed_board": preview,
        }

        module = ast.Module(
            body=functions,
            type_ignores=[],
        )

        exec(
            compile(module, str(SOURCE), "exec"),
            namespace,
        )

        return (
            namespace,
            namespace["preview_h1_runner_board"],
            reader,
            preview,
            rows,
        )

    def test_preview_off_no_read(self):
        namespace, hook, reader, preview, rows = (
            self.make_hook()
        )

        hook(decision_enabled=False)

        reader.assert_not_called()
        preview.assert_not_called()

    def test_preview_on_passes_existing_rows(self):
        namespace, hook, reader, preview, rows = (
            self.make_hook()
        )

        namespace["H1_FIXED_BOARD_DRY_RUN"] = True

        hook(decision_enabled=False)

        reader.assert_called_once_with()
        preview.assert_called_once()

        self.assertEqual(
            preview.call_args.kwargs["current_rows"],
            rows,
        )

        self.assertEqual(
            preview.call_args.kwargs["j1_codes"],
            ["7203", "6501"],
        )

    def test_read_failure_blocks_preview(self):
        namespace, hook, reader, preview, rows = (
            self.make_hook()
        )

        namespace["H1_FIXED_BOARD_DRY_RUN"] = True
        reader.side_effect = RuntimeError(
            "Mock Excel read failure"
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Mock Excel read failure",
        ):
            hook(decision_enabled=True)

        reader.assert_called_once_with()
        preview.assert_not_called()


if __name__ == "__main__":
    unittest.main()
