import ast
import unittest
from pathlib import Path
from unittest.mock import Mock

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/intraday/rss_live_board.py"
)


class TestH1PreviewSafeReader(unittest.TestCase):

    def test_existing_excel_only_read(self):
        tree = ast.parse(
            SOURCE.read_text(encoding="utf-8-sig")
        )

        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "read_board_preview_safe"
        ]

        self.assertEqual(len(functions), 1)

        sheet = Mock()

        def cell_value(row, col):
            values = {
                (2, 1): 7203,
                (2, 8): "J1 BUY",
                (17, 1): 3001,
                (17, 8): "SSR-Ver2",
            }
            return Mock(Value=values.get((row, col)))

        sheet.Cells.side_effect = cell_value

        book = Mock()
        book.Worksheets.return_value = sheet

        excel = Mock()
        excel.Workbooks.return_value = book

        connector = Mock(return_value=excel)

        namespace = {
            "get_microsoft_excel": connector,
            "WORKBOOK_NAME": "rakuten_rss_morning.xlsx",
            "SHEET_NAME": "H1ライブボード",
            "START_ROW": 2,
            "END_ROW": 21,
            "normalize_code": lambda v: (
                str(int(v)) if v is not None else ""
            ),
        }

        exec(
            compile(
                ast.Module(body=functions, type_ignores=[]),
                str(SOURCE),
                "exec",
            ),
            namespace,
        )

        rows = namespace["read_board_preview_safe"]()

        connector.assert_called_once_with(
            start_if_missing=False
        )

        self.assertEqual(rows, [
            {"row": 2, "code": "7203", "label": "J1 BUY"},
            {"row": 17, "code": "3001", "label": "SSR-Ver2"},
        ])

        excel.Workbooks.assert_called_once_with(
            "rakuten_rss_morning.xlsx"
        )
        book.Worksheets.assert_called_once_with(
            "H1ライブボード"
        )

        print("EXISTING EXCEL ONLY: PASS")
        print("BOARD READ: PASS")
        print("NO WRITE / NO SAVE")


if __name__ == "__main__":
    unittest.main()
