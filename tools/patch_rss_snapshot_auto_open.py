from pathlib import Path
import shutil


TARGET = Path(
    "src/intraday/rss_snapshot.py"
)

BACKUP = Path(
    "src/intraday/"
    "rss_snapshot_before_auto_open.py"
)


OLD = '''def get_test_sheet():
    excel = get_excel()

    try:
        book = excel.Workbooks.Item(
            WORKBOOK_NAME
        )

    except Exception as exc:
        raise RuntimeError(
            f"{WORKBOOK_NAME} is not open."
        ) from exc

    sheet = book.Worksheets.Item(1)

    return excel, book, sheet
'''


NEW = '''def get_test_sheet():
    """
    Get the workbook used for the full-market
    Rakuten RSS snapshot.

    If the workbook is already open, reuse it.

    If it is not open, automatically open the
    existing workbook from data/intraday.
    """

    excel = get_excel()

    try:
        book = excel.Workbooks.Item(
            WORKBOOK_NAME
        )

        print(
            f"RSS snapshot workbook : "
            f"already open"
        )

    except Exception:
        workbook_path = (
            ROOT
            / "data"
            / "intraday"
            / WORKBOOK_NAME
        ).resolve()

        if not workbook_path.exists():
            raise RuntimeError(
                "RSS snapshot workbook "
                "was not found: "
                f"{workbook_path}"
            )

        print(
            "RSS snapshot workbook : "
            "opening automatically"
        )
        print(
            f"Workbook              : "
            f"{workbook_path}"
        )

        try:
            book = excel.Workbooks.Open(
                str(workbook_path)
            )

        except Exception as exc:
            raise RuntimeError(
                "RSS snapshot workbook "
                "could not be opened: "
                f"{workbook_path}"
            ) from exc

        print(
            "RSS snapshot workbook : "
            "OPEN OK"
        )

    sheet = book.Worksheets.Item(1)

    return excel, book, sheet
'''


def main():

    if not TARGET.exists():
        raise RuntimeError(
            f"Target not found: {TARGET}"
        )

    text = TARGET.read_text(
        encoding="utf-8"
    )

    if NEW in text:
        print(
            "ALREADY PATCHED : "
            "RSS snapshot auto-open"
        )
        return

    if OLD not in text:
        raise RuntimeError(
            "get_test_sheet() block "
            "was not found."
        )

    if not BACKUP.exists():
        shutil.copy2(
            TARGET,
            BACKUP,
        )

        print(
            f"BACKUP  : {BACKUP}"
        )
    else:
        print(
            f"BACKUP EXISTS : {BACKUP}"
        )

    text = text.replace(
        OLD,
        NEW,
        1,
    )

    TARGET.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "PATCHED : RSS snapshot "
        "workbook auto-open"
    )
    print(
        f"PATCHED : {TARGET}"
    )
    print("COMPLETE")


if __name__ == "__main__":
    main()