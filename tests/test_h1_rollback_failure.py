import unittest
from unittest.mock import patch, MagicMock

from intraday.rss_board_rollback import (
    apply_changes_with_rollback,
)


class FakeCell:
    def __init__(self, value, fail_once=False):
        self._value = value
        self.HasFormula = False
        self.fail_once = fail_once

    @property
    def Value(self):
        return self._value

    @Value.setter
    def Value(self, value):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("Simulated Excel write failure")
        self._value = value


class FakeSheet:
    def __init__(self):
        self.cells = {
            (2, 1): FakeCell("1001"),
            (2, 8): FakeCell("SSR-Ver1", fail_once=True),
        }

    def Cells(self, row, col):
        return self.cells[(row, col)]


class TestH1Rollback(unittest.TestCase):

    def test_partial_write_failure_restores_original(self):
        sheet = FakeSheet()

        changes = [
            (2, 1, "1001", "7203"),
            (2, 8, "SSR-Ver1", "H1 #1 BUY / SSR-Ver1"),
        ]

        with self.assertRaisesRegex(
            RuntimeError,
            "ROLLBACK VERIFIED",
        ):
            apply_changes_with_rollback(sheet, changes)

        self.assertEqual(sheet.Cells(2, 1).Value, "1001")
        self.assertEqual(sheet.Cells(2, 8).Value, "SSR-Ver1")


if __name__ == "__main__":
    unittest.main()
