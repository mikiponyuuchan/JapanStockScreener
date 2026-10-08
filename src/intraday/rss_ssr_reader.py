import time
from pathlib import Path

from rss_excel import get_microsoft_excel


ROOT = Path(__file__).resolve().parents[2]

WORKBOOK_NAME = "rakuten_rss_ssr.xlsx"

WORKBOOK_PATH = (
    ROOT
    / "data"
    / "intraday"
    / WORKBOOK_NAME
)

SHEET_NAME = "SSR"

START_ROW = 2
MAX_STOCKS = 50


def normalize_code(value):
    if value is None:
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def is_excel_error_value(value):
    if value is None:
        return False

    text = str(value).strip()

    return text.startswith("#")


def get_ssr_sheet():
    excel = get_microsoft_excel(
        start_if_missing=True
    )

    try:
        book = excel.Workbooks.Item(
            WORKBOOK_NAME
        )

    except Exception:
        if not WORKBOOK_PATH.exists():
            raise RuntimeError(
                "Rakuten RSS SSR workbook "
                "was not found: "
                f"{WORKBOOK_PATH}"
            )

        book = excel.Workbooks.Open(
            str(WORKBOOK_PATH.resolve())
        )

    sheet = book.Worksheets.Item(
        SHEET_NAME
    )

    return excel, book, sheet


def set_ssr_codes(codes):
    normalized = []

    for code in codes:
        code = normalize_code(code)

        if not code:
            continue

        if code not in normalized:
            normalized.append(code)

    if len(normalized) > MAX_STOCKS:
        raise RuntimeError(
            f"Too many SSR stocks: "
            f"{len(normalized)} "
            f"(max={MAX_STOCKS})"
        )

    excel, book, sheet = get_ssr_sheet()

    sheet.Range(
        f"A{START_ROW}:"
        f"A{START_ROW + MAX_STOCKS - 1}"
    ).ClearContents()

    if normalized:
        end_row = (
            START_ROW
            + len(normalized)
            - 1
        )

        values = tuple(
            (code,)
            for code in normalized
        )

        sheet.Range(
            f"A{START_ROW}:A{end_row}"
        ).Value = values

    excel.Calculate()

    return len(normalized)


def read_ssr_rows(
    wait_seconds=0.0,
):
    excel, book, sheet = get_ssr_sheet()

    if wait_seconds > 0:
        time.sleep(wait_seconds)

    excel.Calculate()

    end_row = (
        START_ROW
        + MAX_STOCKS
        - 1
    )

    values = sheet.Range(
        f"A{START_ROW}:I{end_row}"
    ).Value

    rows = []

    for values_row in values:
        (
            code,
            name,
            prev_close,
            open_price,
            open_time,
            current_price,
            current_time,
            low_price,
            low_time,
        ) = values_row

        code = normalize_code(code)

        if not code:
            continue

        row = {
            "Code": code,
            "Name": (
                ""
                if name is None
                else str(name).strip()
            ),
            "PreviousClose": prev_close,
            "OpeningPrice": open_price,
            "OpeningPriceTime": open_time,
            "CurrentPrice": current_price,
            "CurrentPriceTime": current_time,
            "LowPrice": low_price,
            "LowPriceTime": low_time,
        }

        rows.append(row)

    return rows


def row_has_valid_prices(row):
    required = (
        "PreviousClose",
        "OpeningPrice",
        "CurrentPrice",
        "LowPrice",
    )

    for key in required:
        value = row.get(key)

        if value is None:
            return False

        if is_excel_error_value(value):
            return False

        try:
            if float(value) <= 0:
                return False

        except Exception:
            return False

    return True


def load_ssr_snapshot(
    codes,
    wait_seconds=5.0,
):
    count = set_ssr_codes(codes)

    if count == 0:
        return []

    return read_ssr_rows(
        wait_seconds=wait_seconds
    )
