import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_rollback import (
    apply_changes_with_rollback,
)


class FakeCell:
    def __init__(self, value="", formula=False):
        self._value = value
        self.HasFormula = formula
        self.fail_value = None
        self.fail_once = False
        self.fail_always = False

    @property
    def Value(self):
        return self._value

    @Value.setter
    def Value(self, value):
        if self.fail_always or (
            self.fail_once and value == self.fail_value
        ):
            self.fail_once = False
            raise RuntimeError("Simulated write failure")
        self._value = value


class FakeSheet:
    def __init__(self):
        self.cells = {}

    def Cells(self, row, col):
        return self.cells.setdefault(
            (row, col), FakeCell()
        )


class TestBoardRollback(unittest.TestCase):

    def test_successful_write(self):
        sheet = FakeSheet()
        sheet.Cells(2, 1).Value = "1001"

        count = apply_changes_with_rollback(
            sheet, [(2, 1, "1001", "2001")]
        )

        self.assertEqual(count, 1)
        self.assertEqual(sheet.Cells(2, 1).Value, "2001")

    def test_write_failure_rolls_back(self):
        sheet = FakeSheet()
        sheet.Cells(2, 1).Value = "1001"
        sheet.Cells(2, 8).Value = "OLD"

        cell = sheet.Cells(2, 8)
        cell.fail_value = "NEW"
        cell.fail_once = True

        with self.assertRaisesRegex(
            RuntimeError, "ROLLBACK VERIFIED"
        ):
            apply_changes_with_rollback(
                sheet,
                [
                    (2, 1, "1001", "2001"),
                    (2, 8, "OLD", "NEW"),
                ],
            )

        self.assertEqual(sheet.Cells(2, 1).Value, "1001")
        self.assertEqual(sheet.Cells(2, 8).Value, "OLD")

    def test_formula_protected(self):
        sheet = FakeSheet()
        sheet.Cells(2, 8).HasFormula = True

        with self.assertRaisesRegex(
            RuntimeError, "Formula detected"
        ):
            apply_changes_with_rollback(
                sheet, [(2, 8, "", "NEW")]
            )

    def test_rollback_failure_reported(self):
        sheet = FakeSheet()
        sheet.Cells(2, 1).Value = "1001"
        sheet.Cells(2, 8).Value = "OLD"

        first = sheet.Cells(2, 1)
        second = sheet.Cells(2, 8)

        # Simulate a write that succeeds but cannot
        # restore the original value.
        class RestoreFailCell(FakeCell):
            @FakeCell.Value.setter
            def Value(self, value):
                if value == "1001":
                    raise RuntimeError("Restore blocked")
                self._value = value

        replacement = RestoreFailCell("1001")
        sheet.cells[(2, 1)] = replacement

        second.fail_value = "NEW"
        second.fail_once = True

        with self.assertRaisesRegex(
            RuntimeError, "ROLLBACK INCOMPLETE"
        ):
            apply_changes_with_rollback(
                sheet,
                [
                    (2, 1, "1001", "2001"),
                    (2, 8, "OLD", "NEW"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
