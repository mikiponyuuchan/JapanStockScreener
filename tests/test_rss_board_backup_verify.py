import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intraday.rss_board_backup_verify import verify_board_backup


def make_test_workbook(path, sheet_name="H1ライブボード"):
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships">'
        '<sheets><sheet name="' + sheet_name + '" '
        'sheetId="1" r:id="rId1"/></sheets></workbook>'
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/'
        'package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<Types/>",
        )
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            rels_xml,
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><sheetData/></worksheet>',
        )


class TestBoardBackupVerify(unittest.TestCase):

    def test_missing_backup_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing.xlsx"
            with self.assertRaisesRegex(
                RuntimeError, "Backup file not found"
            ):
                verify_board_backup(path)

    def test_empty_backup_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "empty.xlsx"
            path.write_bytes(b"")
            with self.assertRaisesRegex(
                RuntimeError, "Backup file is empty"
            ):
                verify_board_backup(path)

    def test_invalid_zip_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.xlsx"
            path.write_bytes(b"NOT AN EXCEL FILE")
            with self.assertRaisesRegex(
                RuntimeError,
                "Backup structure verification failed",
            ):
                verify_board_backup(path)

    def test_valid_structure_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "valid.xlsx"
            make_test_workbook(path)
            self.assertTrue(verify_board_backup(path))

    def test_missing_h1_sheet_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing_sheet.xlsx"
            make_test_workbook(path, sheet_name="OtherSheet")
            with self.assertRaisesRegex(
                RuntimeError, "H1 live board sheet not found"
            ):
                verify_board_backup(path)


if __name__ == "__main__":
    unittest.main()
