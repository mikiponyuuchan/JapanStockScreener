from pathlib import Path
from zipfile import ZipFile, BadZipFile
import posixpath
import xml.etree.ElementTree as ET


SHEET_NAME = "H1\u30e9\u30a4\u30d6\u30dc\u30fc\u30c9"

MAIN_NS = (
    "http://schemas.openxmlformats.org/"
    "spreadsheetml/2006/main"
)

REL_NS = (
    "http://schemas.openxmlformats.org/"
    "officeDocument/2006/relationships"
)

PKG_REL_NS = (
    "http://schemas.openxmlformats.org/"
    "package/2006/relationships"
)


def verify_board_backup(backup_path):
    path = Path(backup_path)

    if not path.is_file():
        raise RuntimeError("Backup file not found")

    if path.stat().st_size == 0:
        raise RuntimeError("Backup file is empty")

    try:
        with ZipFile(path, "r") as archive:
            names = set(archive.namelist())

            required = {
                "[Content_Types].xml",
                "xl/workbook.xml",
                "xl/_rels/workbook.xml.rels",
            }

            missing = required - names

            if missing:
                raise RuntimeError(
                    "Missing Excel components: "
                    + ", ".join(sorted(missing))
                )

            if archive.testzip() is not None:
                raise RuntimeError("Backup ZIP CRC error")

            workbook = ET.fromstring(
                archive.read("xl/workbook.xml")
            )

            relationships = ET.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )

            rel_targets = {}

            for rel in relationships.findall(
                f"{{{PKG_REL_NS}}}Relationship"
            ):
                if rel.get("TargetMode") == "External":
                    continue

                rel_targets[rel.get("Id")] = rel.get(
                    "Target"
                )

            sheets = workbook.find(
                f"{{{MAIN_NS}}}sheets"
            )

            if sheets is None:
                raise RuntimeError("No worksheet definitions")

            target_sheet = None

            for sheet in sheets:
                if sheet.get("name") == SHEET_NAME:
                    target_sheet = sheet
                    break

            if target_sheet is None:
                raise RuntimeError(
                    "H1 live board sheet not found"
                )

            rel_id = target_sheet.get(
                f"{{{REL_NS}}}id"
            )

            target = rel_targets.get(rel_id)

            if not target:
                raise RuntimeError(
                    "H1 sheet relationship not found"
                )

            if target.startswith("/"):
                sheet_path = target.lstrip("/")
            else:
                sheet_path = posixpath.normpath(
                    posixpath.join("xl", target)
                )

            if sheet_path not in names:
                raise RuntimeError(
                    "H1 sheet XML not found"
                )

            ET.fromstring(archive.read(sheet_path))

    except (BadZipFile, ET.ParseError) as exc:
        raise RuntimeError(
            "Backup structure verification failed"
        ) from exc

    print("BACKUP FILE:", path)
    print("BACKUP SIZE:", path.stat().st_size)
    print("BACKUP ZIP: OK")
    print("BACKUP WORKBOOK: OK")
    print("H1 LIVE BOARD SHEET: OK")
    print("BACKUP VERIFIED")

    return True
