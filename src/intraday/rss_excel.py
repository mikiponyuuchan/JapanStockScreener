from pathlib import Path
import subprocess
import time

import pythoncom
import win32com.client as win32


ROOT = Path(__file__).resolve().parents[2]

INTRADAY_DIR = (
    ROOT
    / "data"
    / "intraday"
)

H1_WORKBOOK_NAME = "rakuten_rss_morning.xlsx"

REQUIRED_WORKBOOKS = (
    "rakuten_rss_morning.xlsx",
)

EXCEL_EXE = Path(
    r"C:\Program Files\Microsoft Office"
    r"\Root\Office16\EXCEL.EXE"
)

MICROSOFT_EXCEL_PATH_MARKERS = (
    "microsoft office",
    "office16",
)


def _is_microsoft_excel(excel):
    """
    Verify that the COM Application belongs to
    Microsoft Excel, not an Excel-compatible app.
    """
    try:
        path = str(
            excel.Path
        ).lower()

        version = str(
            excel.Version
        )

    except Exception:
        return False

    if (
        "kingsoft" in path
        or "wps office" in path
    ):
        return False

    if not any(
        marker in path
        for marker in MICROSOFT_EXCEL_PATH_MARKERS
    ):
        return False

    if not version.startswith("16."):
        return False

    return True


def _find_h1_book_in_rot():
    """
    Find rakuten_rss_morning.xlsx directly in the
    Running Object Table.

    Do not use GetActiveObject("Excel.Application"),
    because WPS may register that ProgID.
    """
    target = str(
        (
            INTRADAY_DIR
            / H1_WORKBOOK_NAME
        ).resolve()
    ).lower()

    rot = pythoncom.GetRunningObjectTable()
    enum = rot.EnumRunning()
    ctx = pythoncom.CreateBindCtx(0)

    while True:
        items = enum.Next(1)

        if not items:
            break

        moniker = items[0]

        try:
            display_name = (
                moniker.GetDisplayName(
                    ctx,
                    None,
                )
            )
        except Exception:
            continue

        if str(display_name).lower() != target:
            continue

        try:
            unknown = rot.GetObject(
                moniker
            )

            dispatch = (
                unknown.QueryInterface(
                    pythoncom.IID_IDispatch
                )
            )

            book = win32.Dispatch(
                dispatch
            )

            excel = book.Application

            if not _is_microsoft_excel(
                excel
            ):
                continue

            return excel, book

        except Exception:
            continue

    return None, None



def _excel_process_exists():
    """Check whether Microsoft Excel is already running."""
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/NH"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError("Could not inspect Excel processes")
    return "EXCEL.EXE" in result.stdout.upper()


def _retry_existing_book(seconds=5):
    """Allow time for an existing workbook to register in ROT."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        excel, book = _find_h1_book_in_rot()
        if excel is not None:
            return excel
        time.sleep(0.5)
    return None


def get_microsoft_excel(
    start_if_missing=True,
    timeout=20,
):
    """
    Return the Microsoft Excel instance that owns
    rakuten_rss_morning.xlsx.

    WPS / Kingsoft is deliberately ignored.
    """
    excel, book = _find_h1_book_in_rot()

    if excel is not None:
        return excel

    excel = _retry_existing_book(seconds=5)
    if excel is not None:
        return excel

    if not start_if_missing:
        raise RuntimeError(
            "Microsoft Excel RSS instance "
            "was not found."
        )

    if _excel_process_exists():
        raise RuntimeError(
            "Excel is already running, but the Rakuten RSS "
            "workbook was not found in ROT. "
            "Duplicate Excel launch prevented. "
            "Close duplicate Excel windows and reopen the "
            "original workbook, then retry."
        )

    if not EXCEL_EXE.exists():
        raise RuntimeError(
            "Microsoft EXCEL.EXE was not found: "
            f"{EXCEL_EXE}"
        )

    h1_path = (
        INTRADAY_DIR
        / H1_WORKBOOK_NAME
    ).resolve()

    if not h1_path.exists():
        raise RuntimeError(
            "Rakuten RSS H1 workbook "
            "was not found: "
            f"{h1_path}"
        )

    subprocess.Popen(
        [
            str(EXCEL_EXE),
            "/x",
            str(h1_path),
        ]
    )

    deadline = (
        time.time()
        + timeout
    )

    last_error = None

    while time.time() < deadline:
        try:
            excel, book = (
                _find_h1_book_in_rot()
            )

            if excel is not None:
                excel.Visible = True
                return excel

        except Exception as exc:
            last_error = exc

        time.sleep(0.5)

    raise RuntimeError(
        "Microsoft Excel started, but the "
        "Rakuten RSS H1 workbook could not "
        "be obtained from the Running Object "
        f"Table. Last error: {last_error}"
    )


def ensure_rss_workbooks():
    """
    Ensure all Rakuten RSS workbooks are open
    in the same Microsoft Excel instance.
    """
    excel = get_microsoft_excel(
        start_if_missing=True
    )

    results = {}

    for workbook_name in REQUIRED_WORKBOOKS:

        try:
            book = excel.Workbooks.Item(
                workbook_name
            )

            results[workbook_name] = (
                "ALREADY OPEN"
            )

            continue

        except Exception:
            pass

        workbook_path = (
            INTRADAY_DIR
            / workbook_name
        ).resolve()

        if not workbook_path.exists():
            raise RuntimeError(
                "RSS workbook was not found: "
                f"{workbook_path}"
            )

        excel.Workbooks.Open(
            str(workbook_path)
        )

        results[workbook_name] = "OPENED"

    excel.Visible = True

    return excel, results
