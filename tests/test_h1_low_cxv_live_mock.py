import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "intraday"))

import intraday.rss_live_board as live_board
from intraday.h1_low_cxv_board import write_low_cxv_board


class FakeCell:
    def __init__(self, value=None, formula=False):
        self.Value = value
        self.HasFormula = formula


class FakeSheet:
    def __init__(self):
        self.cells = {}

    def Cells(self, row, col):
        return self.cells.setdefault(
            (row, col), FakeCell()
        )


class FakeWorkbook:
    def __init__(self, path):
        self.FullName = str(path)
        self.ReadOnly = False
        self.save_calls = 0

    def Save(self):
        self.save_calls += 1

    def SaveCopyAs(self, destination):
        Path(destination).write_bytes(b"fake backup")


class TestLowCxVLiveMockSafety(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        original = Path(self.temp.name) / "board.xlsx"
        original.write_bytes(b"fake workbook")

        self.book = FakeWorkbook(original)
        self.sheet = FakeSheet()

        # Initialize all possible LOW-CxV target cells
        # before taking test snapshots.
        for row in range(12, 22):
            for col in (1, 8):
                self.sheet.Cells(row, col)

        self.excel = type(
            "FakeExcel", (), {"Calculate": lambda self: None}
        )()

        self.candidates = pd.DataFrame([
            {
                "CodeX": str(1000 + i),
                "NameX": f"Stock{i}",
                "ChangeX": 5.0,
                "CxV": float(i),
            }
            for i in range(1, 11)
        ])

        # Simulate the verified TOP10 already on the board.
        for row, code in zip(
            range(2, 12),
            self.candidates["CodeX"],
        ):
            self.sheet.Cells(row, 1).Value = code

    def test_formula_aborts_without_any_cell_changes(self):
        # Formula protection must apply even if the cell
        # does not have a LOW-CxV label.
        self.sheet.Cells(12, 1).HasFormula = True
        before = {
            key: (cell.Value, cell.HasFormula)
            for key, cell in self.sheet.cells.items()
        }

        with patch.object(
            live_board,
            "get_live_board",
            return_value=(self.excel, self.book, self.sheet),
        ), patch(
            "intraday.rss_board_backup_guard.create_verified_backup"
        ) as backup:
            with self.assertRaisesRegex(
                RuntimeError, "Formula in A12"
            ):
                write_low_cxv_board(
                    self.candidates, enabled=True
                )

        backup.assert_not_called()

        after = {
            key: (cell.Value, cell.HasFormula)
            for key, cell in self.sheet.cells.items()
        }
        self.assertEqual(after, before)
        self.assertEqual(self.book.save_calls, 0)

    def test_backup_failure_aborts_without_any_cell_changes(self):
        before = {
            key: (cell.Value, cell.HasFormula)
            for key, cell in self.sheet.cells.items()
        }

        with patch.object(
            live_board,
            "get_live_board",
            return_value=(self.excel, self.book, self.sheet),
        ), patch(
            "intraday.rss_board_backup_guard.create_verified_backup",
            side_effect=RuntimeError("Simulated backup failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Verified backup failed"
            ):
                write_low_cxv_board(
                    self.candidates, enabled=True
                )

        after = {
            key: (cell.Value, cell.HasFormula)
            for key, cell in self.sheet.cells.items()
        }
        self.assertEqual(after, before)
        self.assertEqual(self.book.save_calls, 0)


if __name__ == "__main__":
    unittest.main()
