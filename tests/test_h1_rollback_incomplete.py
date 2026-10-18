import unittest

from intraday.rss_board_rollback import apply_changes_with_rollback


class FakeCell:
    def __init__(self, value, fail_values=()):
        self._value = value
        self.HasFormula = False
        self.fail_values = set(fail_values)

    @property
    def Value(self):
        return self._value

    @Value.setter
    def Value(self, value):
        if value in self.fail_values:
            raise RuntimeError("Simulated write or rollback failure")
        self._value = value


class FakeSheet:
    def __init__(self):
        self.cells = {
            (2, 1): FakeCell("1001", fail_values={"1001"}),
            (2, 8): FakeCell("SSR", fail_values={"H1 #1 BUY / SSR"}),
        }

    def Cells(self, row, col):
        return self.cells[(row, col)]


class TestH1RollbackIncomplete(unittest.TestCase):
    def test_rollback_failure_is_reported(self):
        sheet = FakeSheet()

        changes = [
            (2, 1, "1001", "7203"),
            (2, 8, "SSR", "H1 #1 BUY / SSR"),
        ]

        with self.assertRaisesRegex(
            RuntimeError,
            "WRITE FAILED AND ROLLBACK INCOMPLETE",
        ):
            apply_changes_with_rollback(sheet, changes)

        self.assertEqual(sheet.Cells(2, 1).Value, "7203")
        self.assertEqual(sheet.Cells(2, 8).Value, "SSR")


if __name__ == "__main__":
    unittest.main()
