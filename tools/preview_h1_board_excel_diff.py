import sys
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "intraday"))

from rss_live_board_h1_preview import (
    preview_relayout_board,
)

BOOK_PATH = (
    ROOT / "data" / "intraday" / "rakuten_rss_morning.xlsx"
)

SHEET_NAME = "H1\u30e9\u30a4\u30d6\u30dc\u30fc\u30c9"


def read_current_rows():
    excel = win32com.client.GetActiveObject(
        "Excel.Application"
    )

    expected = str(BOOK_PATH.resolve()).casefold()

    book = None

    for candidate in excel.Workbooks:
        if str(candidate.FullName).casefold() == expected:
            book = candidate
            break

    if book is None:
        raise RuntimeError(
            "Target workbook is not open in Excel"
        )

    sheet = None

    for index in range(1, book.Worksheets.Count + 1):
        candidate = book.Worksheets(index)

        if candidate.Name == SHEET_NAME:
            sheet = candidate
            break

    if sheet is None:
        raise RuntimeError(
            f"Worksheet not found: {SHEET_NAME}"
        )

    rows = []

    for row in range(2, 22):
        code = sheet.Cells(row, 1).Value2
        label = sheet.Cells(row, 8).Value2

        rows.append({
            "row": row,
            "code": str(code).strip() if code is not None else "",
            "label": str(label).strip() if label is not None else "",
        })

    return rows


def main():
    rows = read_current_rows()

    print("=" * 65)
    print("CURRENT EXCEL BOARD - READ ONLY")
    print("=" * 65)

    for item in rows:
        print(
            f"ROW {item['row']:2d} | "
            f"{item['code']:8s} | "
            f"{item['label']}"
        )

    print()
    print("READ ONLY OK")
    print("No cells changed. No workbook saved.")




# H1_REAL_BOARD_DIFF_V1
# Read-only preview. No Excel writes or saves.

def preview_current_board_diff(rows):
    import re
    from rss_live_board_h1_preview import normalize_code

    changes = []

    for item in rows:
        row = item["row"]
        raw_code = item["code"]
        code = normalize_code(raw_code)
        old_label = item["label"]

        labels = [
            part.strip()
            for part in old_label.split("/")
            if part.strip()
        ]

        # Remove H1 CAND only when an H1 decision exists.
        has_decision = any(
            re.match(r"^H1 #[0-9]+(?:[ ]|$)", label)
            for label in labels
        )

        if has_decision:
            labels = [
                label
                for label in labels
                if not re.match(
                    r"^H1 CAND #[0-9]+$",
                    label,
                )
            ]

        new_label = " / ".join(dict.fromkeys(labels))

        # Code normalization is used for comparison only.
        # This preview does not propose changing Excel code cells.
        if old_label != new_label:
            changes.append({
                "row": row,
                "code": code,
                "before": old_label,
                "after": new_label,
            })

    return changes


def show_current_board_diff():
    rows = read_current_rows()
    changes = preview_current_board_diff(rows)

    print("=" * 65)
    print("H1 LIVE BOARD LABEL DIFF - READ ONLY")
    print("=" * 65)

    for change in changes:
        print(
            f"ROW {change['row']:2d} "
            f"CODE {change['code']}"
        )
        print("  BEFORE:", change["before"])
        print("  AFTER :", change["after"])

    print()
    print("CHANGED ROWS:", len(changes))
    print("READ ONLY DIFF OK")
    print("No cells changed. No workbook saved.")


if __name__ == "__main__":
    show_current_board_diff()
