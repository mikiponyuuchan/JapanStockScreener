# ================================================
# ?? MarketSpeed II RSS
# ????????????? ?????
#
# Step 1 : 100??
# ================================================

import sys
import time
from pathlib import Path

import win32com.client as win32


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from screener.loader import load_stock_list


WORKBOOK_NAME = "rakuten_rss_snapshot_test.xlsx"

TEST_COUNT = 3716

START_ROW = 2

POLL_INTERVAL = 0.5
TIMEOUT_SECONDS = 60.0


def is_excel_error_value(value):
    if isinstance(value, (int, float)):
        return value <= -2000000000

    return False


def has_rss_value(value):
    """
    Return True only when RSS has an actual numeric value.

    H1?????????????????
    ????????????????????
    """

    if value is None:
        return False

    if is_excel_error_value(value):
        return False

    # RSS????????????????
    # ???????????
    if isinstance(value, str):
        return False

    # bool????????????
    if isinstance(value, bool):
        return False

    return isinstance(
        value,
        (int, float),
    )


def normalize_code(value):
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .replace(".0", "")
    )


def get_excel():

    try:
        return win32.GetActiveObject(
            "Excel.Application"
        )

    except Exception as exc:
        raise RuntimeError(
            "????Excel?????????"
        ) from exc


def get_test_sheet():

    excel = get_excel()

    try:
        book = excel.Workbooks.Item(
            WORKBOOK_NAME
        )

    except Exception as exc:
        raise RuntimeError(
            f"{WORKBOOK_NAME} ?????????"
        ) from exc

    sheet = book.Worksheets.Item(1)

    return excel, book, sheet


def load_test_stocks():

    stocks = load_stock_list(
        start=0,
        limit=TEST_COUNT,
    )

    if stocks is None or stocks.empty:
        raise RuntimeError(
            "?????????"
        )

    code_col = "\u30b3\u30fc\u30c9"
    name_col = "\u9298\u67c4\u540d"

    required = [
        code_col,
        name_col,
    ]

    missing = [
        col
        for col in required
        if col not in stocks.columns
    ]

    if missing:
        raise RuntimeError(
            "???????????? : "
            + ", ".join(missing)
        )

    work = stocks[
        [
            code_col,
            name_col,
        ]
    ].copy()

    work = work.rename(
        columns={
            code_col: "Code",
            name_col: "Name",
        }
    )

    work["Code"] = (
        work["Code"]
        .map(normalize_code)
    )

    return work


def setup_rss_formulas(
    sheet,
    stocks,
):

    end_row = (
        START_ROW
        + len(stocks)
        - 1
    )

    sheet.Range(
        f"A1:E{end_row}"
    ).ClearContents()

    headers = (
        (
            "Code",
            "Name",
            "Price",
            "ChangePercent",
            "Volume",
        ),
    )

    sheet.Range(
        "A1:E1"
    ).Value = headers

    # RSS field names.
    # Unicode escapes avoid PowerShell encoding problems.
    rss_name = "\u9298\u67c4\u540d\u79f0"
    rss_price = "\u73fe\u5728\u5024"
    rss_change = "\u524d\u65e5\u6bd4\u7387"
    rss_volume = "\u51fa\u6765\u9ad8"

    values = []

    for _, stock in stocks.iterrows():

        code = stock["Code"]

        values.append(
            (
                code,
                f'=RssMarket("{code}.T","{rss_name}")',
                f'=RssMarket("{code}.T","{rss_price}")',
                f'=RssMarket("{code}.T","{rss_change}")',
                f'=RssMarket("{code}.T","{rss_volume}")',
            )
        )

    target = sheet.Range(
        f"A{START_ROW}:E{end_row}"
    )

    target.Formula = tuple(values)

    return end_row

def inspect_rows(
    sheet,
    end_row,
):

    values = sheet.Range(
        f"A{START_ROW}:E{end_row}"
    ).Value

    success = 0
    pending = 0
    errors = 0

    success_rows = []
    pending_rows = []

    for row in values:

        code, name, price, change, volume = row

        code = normalize_code(
            code
        )

        has_error = any(
            is_excel_error_value(x)
            for x in (
                name,
                price,
                change,
                volume,
            )
        )

        if has_error:
            errors += 1

            pending_rows.append(
                (
                    code,
                    name,
                    price,
                    change,
                    volume,
                )
            )

            continue

        # H1??????
        # ??????????????????
        #
        # Name????????????????????
        if (
            has_rss_value(price)
            and has_rss_value(change)
            and has_rss_value(volume)
        ):
            success += 1

            success_rows.append(
                (
                    code,
                    name,
                    price,
                    change,
                    volume,
                )
            )

        else:
            pending += 1

            pending_rows.append(
                (
                    code,
                    name,
                    price,
                    change,
                    volume,
                )
            )

    return {
        "success": success,
        "pending": pending,
        "errors": errors,
        "success_rows": success_rows,
        "pending_rows": pending_rows,
    }


def main():

    print("=" * 72)
    print(" ??RSS SNAPSHOT TEST")
    print("=" * 72)
    print(
        f"Test stocks : {TEST_COUNT}"
    )
    print(
        f"Timeout     : {TIMEOUT_SECONDS:.0f} sec"
    )
    print()

    stocks = load_test_stocks()

    print(
        "Stock list loaded :",
        len(stocks),
    )

    excel, book, sheet = (
        get_test_sheet()
    )

    print(
        "Workbook :",
        book.Name,
    )
    print(
        "Sheet    :",
        sheet.Name,
    )
    print()

    print(
        "Setting RSS formulas..."
    )

    setup_start = (
        time.perf_counter()
    )

    end_row = setup_rss_formulas(
        sheet,
        stocks,
    )

    excel.Calculate()

    setup_seconds = (
        time.perf_counter()
        - setup_start
    )

    print(
        "Formula setup : "
        f"{setup_seconds:.3f} sec"
    )

    print()
    print(
        "Waiting for RSS values..."
    )

    wait_start = (
        time.perf_counter()
    )

    previous_success = -1

    final_result = None

    while True:

        result = inspect_rows(
            sheet,
            end_row,
        )

        elapsed = (
            time.perf_counter()
            - wait_start
        )

        if (
            result["success"]
            != previous_success
        ):
            print(
                f"{elapsed:6.2f} sec | "
                f"OK {result['success']:3d}"
                f"/{len(stocks)} | "
                f"Pending {result['pending']:3d} | "
                f"Error {result['errors']:3d}"
            )

            previous_success = (
                result["success"]
            )

        final_result = result

        if (
            result["success"]
            >= len(stocks)
        ):
            break

        if elapsed >= TIMEOUT_SECONDS:
            break

        time.sleep(
            POLL_INTERVAL
        )

    total_wait = (
        time.perf_counter()
        - wait_start
    )

    print()
    print("=" * 72)
    print(" RESULT")
    print("=" * 72)

    print(
        f"Requested     : {len(stocks)}"
    )
    print(
        f"Success       : {final_result['success']}"
    )
    print(
        f"Pending       : {final_result['pending']}"
    )
    print(
        f"Excel errors  : {final_result['errors']}"
    )
    print(
        f"Formula setup : {setup_seconds:.3f} sec"
    )
    print(
        f"RSS wait      : {total_wait:.3f} sec"
    )
    print(
        "Total         : "
        f"{setup_seconds + total_wait:.3f} sec"
    )

    print()

    print(
        "First 10 successful rows"
    )
    print("-" * 72)

    for row in (
        final_result[
            "success_rows"
        ][:10]
    ):
        print(
            row
        )

    if final_result[
        "pending_rows"
    ]:

        print()
        print(
            "Unresolved rows "
            f"({len(final_result['pending_rows'])})"
        )
        print("-" * 72)

        for row in (
            final_result[
                "pending_rows"
            ][:20]
        ):
            print(
                row
            )

    print()
    print("=" * 72)


if __name__ == "__main__":
    main()



