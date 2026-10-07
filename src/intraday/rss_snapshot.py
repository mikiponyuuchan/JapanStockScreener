# ================================================
# Rakuten MarketSpeed II RSS
# Full universe batch snapshot test
#
# 400 stocks x batches -> all normal stocks
# ================================================

import sys
import time
from pathlib import Path

import pandas as pd
from rss_excel import get_microsoft_excel


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from screener.loader import load_stock_list


WORKBOOK_NAME = "rakuten_rss_snapshot_test.xlsx"

BATCH_SIZE = 400

START_ROW = 2

POLL_INTERVAL = 0.25
BATCH_TIMEOUT_SECONDS = 15.0

# Batch early-exit settings.
# Always allow RSS enough startup time first.
MIN_BATCH_WAIT_SECONDS = 5.0

# After the minimum wait, move to the next batch
# once this percentage of stocks has been obtained.
EARLY_EXIT_SUCCESS_RATE = 0.98

# First pass????Pending????????????????
RETRY_TIMEOUT_SECONDS = 20.0


def is_excel_error_value(value):
    if isinstance(value, (int, float)):
        return value <= -2000000000

    return False


def is_numeric_rss_value(value):
    if value is None:
        return False

    if is_excel_error_value(value):
        return False

    if isinstance(value, bool):
        return False

    return isinstance(
        value,
        (int, float),
    )


def is_overlimit_value(value):
    if not isinstance(value, str):
        return False

    return (
        "\u8868\u793a\u9298\u67c4\u6570\u8d85\u904e"
        in value
    )


def normalize_code(value):
    if value is None:
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def get_excel():
    """
    Get the Microsoft Excel instance used by
    Rakuten RSS.

    WPS / Kingsoft is ignored by rss_excel.
    """
    try:
        return get_microsoft_excel(
            start_if_missing=True
        )

    except Exception as exc:
        raise RuntimeError(
            "Microsoft Excel RSS instance "
            "was not found."
        ) from exc

def get_test_sheet():
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


def load_stocks():
    stocks = load_stock_list()

    if stocks is None or stocks.empty:
        raise RuntimeError(
            "Stock list is empty."
        )

    code_col = "\u30b3\u30fc\u30c9"
    name_col = "\u9298\u67c4\u540d"

    missing = [
        col
        for col in (
            code_col,
            name_col,
        )
        if col not in stocks.columns
    ]

    if missing:
        raise RuntimeError(
            "Stock columns missing: "
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
            name_col: "MasterName",
        }
    )

    work["Code"] = (
        work["Code"]
        .map(normalize_code)
    )

    return work.reset_index(drop=True)


def clear_board(sheet):
    # Only 400 rows are used at any one time.
    last_row = START_ROW + BATCH_SIZE - 1

    sheet.Range(
        f"A1:D{last_row}"
    ).ClearContents()


def setup_batch(
    sheet,
    batch,
):
    """
    Prepare one Rakuten RSS batch.

    Excel can temporarily reject COM calls while
    MarketSpeed II RSS is updating cells.  Retry the
    whole setup so a partially written batch is cleared
    and rebuilt from the beginning.
    """
    end_row = (
        START_ROW
        + len(batch)
        - 1
    )

    rss_price = "\u73fe\u5728\u5024"
    rss_change = "\u524d\u65e5\u6bd4\u7387"
    rss_volume = "\u51fa\u6765\u9ad8"

    values = []

    for row in batch.itertuples(
        index=False
    ):
        code = row.Code

        values.append(
            (
                code,
                f'=RssMarket("{code}.T","{rss_price}")',
                f'=RssMarket("{code}.T","{rss_change}")',
                f'=RssMarket("{code}.T","{rss_volume}")',
            )
        )

    max_retries = 20
    retry_wait = 0.25
    last_error = None

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            # Rebuild from a clean board on every retry.
            clear_board(sheet)

            sheet.Range(
                "A1:D1"
            ).Value = (
                (
                    "Code",
                    "Price",
                    "ChangePercent",
                    "Volume",
                ),
            )

            sheet.Range(
                f"A{START_ROW}:D{end_row}"
            ).Formula = tuple(values)

            if attempt > 1:
                print(
                    "  Excel COM setup recovered "
                    f"after {attempt - 1} retries"
                )

            return end_row

        except Exception as exc:
            last_error = exc

            if attempt >= max_retries:
                break

            if attempt == 1:
                print(
                    "  Excel COM setup busy "
                    "- retrying..."
                )

            time.sleep(
                retry_wait
            )

    raise RuntimeError(
        "Excel COM setup failed after "
        f"{max_retries} retries : "
        f"{last_error}"
    ) from last_error


def inspect_batch(
    sheet,
    end_row,
):
    # Excel / ??RSS????????
    # COM????????????????????
    # ??????????????????
    max_retries = 20
    retry_wait = 0.25

    last_error = None

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            values = sheet.Range(
                f"A{START_ROW}:D{end_row}"
            ).Value

            last_error = None
            break

        except Exception as exc:
            last_error = exc

            if attempt >= max_retries:
                break

            if attempt == 1:
                print(
                    "  Excel COM busy - retrying..."
                )

            time.sleep(
                retry_wait
            )

    if last_error is not None:
        raise RuntimeError(
            "Excel COM read failed after "
            f"{max_retries} retries : "
            f"{last_error}"
        ) from last_error

    rows = []
    pending = []
    overlimit = []
    excel_errors = []

    for row in values:
        (
            code,
            price,
            change,
            volume,
        ) = row

        code = normalize_code(code)

        data = (
            code,
            price,
            change,
            volume,
        )

        if any(
            is_overlimit_value(x)
            for x in (
                price,
                change,
                volume,
            )
        ):
            overlimit.append(data)
            continue

        if any(
            is_excel_error_value(x)
            for x in (
                price,
                change,
                volume,
            )
        ):
            excel_errors.append(data)
            continue

        if (
            is_numeric_rss_value(price)
            and is_numeric_rss_value(change)
            and is_numeric_rss_value(volume)
        ):
            rows.append(
                {
                    "Code": code,
                    "Price": price,
                    "ChangePercent": change,
                    "Volume": volume,
                }
            )
            continue

        pending.append(data)

    return {
        "rows": rows,
        "pending": pending,
        "overlimit": overlimit,
        "excel_errors": excel_errors,
    }


def fetch_batch(
    excel,
    sheet,
    batch,
    batch_no,
    batch_total,
    timeout_seconds=None,
):
    if timeout_seconds is None:
        timeout_seconds = BATCH_TIMEOUT_SECONDS
    started = time.perf_counter()

    end_row = setup_batch(
        sheet,
        batch,
    )

    # Excel may also reject Calculate temporarily while
    # Rakuten RSS is processing the newly written formulas.
    calc_max_retries = 20
    calc_retry_wait = 0.25
    calc_last_error = None

    for calc_attempt in range(
        1,
        calc_max_retries + 1,
    ):
        try:
            excel.Calculate()
            calc_last_error = None

            if calc_attempt > 1:
                print(
                    "  Excel COM calculate recovered "
                    f"after {calc_attempt - 1} retries"
                )

            break

        except Exception as exc:
            calc_last_error = exc

            if calc_attempt >= calc_max_retries:
                break

            if calc_attempt == 1:
                print(
                    "  Excel COM calculate busy "
                    "- retrying..."
                )

            time.sleep(
                calc_retry_wait
            )

    if calc_last_error is not None:
        raise RuntimeError(
            "Excel COM calculate failed after "
            f"{calc_max_retries} retries : "
            f"{calc_last_error}"
        ) from calc_last_error

    setup_seconds = (
        time.perf_counter()
        - started
    )

    wait_started = time.perf_counter()

    result = None

    previous_state = None

    # Rakuten RSS can pause before delivering values in bulk.
    # Track real progress instead of stopping only by elapsed time.
    best_ok = -1
    last_progress_time = wait_started

    while True:
        result = inspect_batch(
            sheet,
            end_row,
        )

        ok = len(result["rows"])
        pending = len(result["pending"])
        overlimit = len(
            result["overlimit"]
        )
        errors = len(
            result["excel_errors"]
        )

        state = (
            ok,
            pending,
            overlimit,
            errors,
        )

        if state != previous_state:
            elapsed = (
                time.perf_counter()
                - wait_started
            )

            print(
                f"Batch {batch_no:02d}/{batch_total:02d} | "
                f"{elapsed:5.2f}s | "
                f"OK {ok:3d}/{len(batch):3d} | "
                f"Pending {pending:3d} | "
                f"OverLimit {overlimit:3d} | "
                f"Error {errors:3d}"
            )

            previous_state = state

        # Completed normally.
        if ok >= len(batch):
            break

        # OverLimit or Excel errors are final states.
        if overlimit > 0 or errors > 0:
            break

        elapsed = (
            time.perf_counter()
            - wait_started
        )

        # ----------------------------------------------------
        # Early exit
        #
        # Do not judge too early because Rakuten RSS may need
        # several seconds before values arrive in bulk.
        #
        # After the minimum wait, 98% success is enough for
        # this full-universe snapshot test.
        # ----------------------------------------------------
        required_ok = max(
            1,
            int(
                len(batch)
                * EARLY_EXIT_SUCCESS_RATE
                + 0.999999
            ),
        )

        if (
            elapsed >= MIN_BATCH_WAIT_SECONDS
            and ok >= required_ok
        ):
            print(
                f"  Early exit : "
                f"{ok}/{len(batch)} "
                f"({ok / len(batch) * 100:.2f}%) "
                f"after {elapsed:.2f}s"
            )
            break

        now_counter = time.perf_counter()

        if ok > best_ok:
            best_ok = ok
            last_progress_time = now_counter

        stall_seconds = (
            now_counter
            - last_progress_time
        )

        # timeout_seconds is now the minimum normal wait.
        # If RSS is still progressing, continue waiting.
        if (
            elapsed >= timeout_seconds
            and stall_seconds >= 4.0
        ):
            print(
                f"  Stall exit : "
                f"{ok}/{len(batch)} "
                f"no progress for "
                f"{stall_seconds:.2f}s"
            )
            break

        # Absolute safety limit.
        if elapsed >= 20.0:
            print(
                f"  Max timeout : "
                f"{ok}/{len(batch)} "
                f"after {elapsed:.2f}s"
            )
            break

        time.sleep(
            POLL_INTERVAL
        )

    wait_seconds = (
        time.perf_counter()
        - wait_started
    )

    total_seconds = (
        time.perf_counter()
        - started
    )

    return (
        result,
        setup_seconds,
        wait_seconds,
        total_seconds,
    )


def fetch_full_snapshot():
    """
    Fetch one Rakuten RSS snapshot for the full JPX
    normal-stock universe.

    Stocks are processed in small Excel RSS batches so
    that only one batch is subscribed at a time.

    Returns
    -------
    pandas.DataFrame
        Columns:
        Code, Name, Price, ChangePercent, Volume

    dict
        Execution metadata including failed rows and
        batch timings.
    """

    stocks = load_stocks()

    total = len(stocks)

    batch_total = (
        total
        + BATCH_SIZE
        - 1
    ) // BATCH_SIZE

    excel, book, sheet = (
        get_test_sheet()
    )

    all_rows = []
    failed_rows = []
    timings = []
    retry_codes = set()

    overall_started = (
        time.perf_counter()
    )

    for batch_index in range(
        batch_total
    ):
        start = (
            batch_index
            * BATCH_SIZE
        )

        end = min(
            start + BATCH_SIZE,
            total,
        )

        batch = (
            stocks
            .iloc[start:end]
            .copy()
        )

        (
            result,
            setup_seconds,
            wait_seconds,
            total_seconds,
        ) = fetch_batch(
            excel,
            sheet,
            batch,
            batch_index + 1,
            batch_total,
        )

        all_rows.extend(
            result["rows"]
        )

        for row in result["pending"]:
            code = normalize_code(
                row[0]
            )

            if code:
                retry_codes.add(
                    code
                )

        for status_name in (
            "overlimit",
            "excel_errors",
        ):
            for row in result[
                status_name
            ]:
                failed_rows.append(
                    (
                        status_name,
                        *row,
                    )
                )

        timings.append(
            {
                "Batch": batch_index + 1,
                "Requested": len(batch),
                "Success": len(
                    result["rows"]
                ),
                "Pending": len(
                    result["pending"]
                ),
                "OverLimit": len(
                    result["overlimit"]
                ),
                "ExcelErrors": len(
                    result["excel_errors"]
                ),
                "SetupSeconds": setup_seconds,
                "WaitSeconds": wait_seconds,
                "TotalSeconds": total_seconds,
            }
        )

        clear_board(
            sheet
        )

        # Excel may temporarily reject Calculate while
        # Rakuten RSS / Excel is still busy after the
        # previous batch.  Retry here just like the
        # Calculate call used when starting a batch.
        calc_max_retries = 20
        calc_retry_wait = 0.25
        calc_last_error = None

        for calc_attempt in range(
            1,
            calc_max_retries + 1,
        ):
            try:
                excel.Calculate()
                calc_last_error = None

                if calc_attempt > 1:
                    print(
                        "  Excel COM clear calculate recovered "
                        f"after {calc_attempt - 1} retries"
                    )

                break

            except Exception as exc:
                calc_last_error = exc

                if calc_attempt >= calc_max_retries:
                    break

                if calc_attempt == 1:
                    print(
                        "  Excel COM clear calculate busy "
                        "- retrying..."
                    )

                time.sleep(
                    calc_retry_wait
                )

        if calc_last_error is not None:
            raise RuntimeError(
                "Excel COM clear calculate failed after "
                f"{calc_max_retries} retries : "
                f"{calc_last_error}"
            ) from calc_last_error

        time.sleep(
            0.25
        )

    for code in sorted(
        retry_codes
    ):
        failed_rows.append(
            (
                "pending",
                code,
                "",
                "",
                "",
            )
        )

    name_map = dict(
        zip(
            stocks["Code"],
            stocks["MasterName"],
        )
    )

    for item in all_rows:
        item["Name"] = (
            name_map.get(
                item["Code"],
                "",
            )
        )

    snapshot = pd.DataFrame(
        all_rows,
        columns=[
            "Code",
            "Name",
            "Price",
            "ChangePercent",
            "Volume",
        ],
    )

    overall_seconds = (
        time.perf_counter()
        - overall_started
    )

    metadata = {
        "Requested": total,
        "Success": len(snapshot),
        "Failed": len(failed_rows),
        "Pending": len(
            retry_codes
        ),
        "ElapsedSeconds": (
            overall_seconds
        ),
        "FailedRows": (
            failed_rows
        ),
        "BatchTimings": (
            timings
        ),
        "Workbook": book.Name,
        "Sheet": sheet.Name,
    }

    clear_board(
        sheet
    )

    excel.Calculate()

    return snapshot, metadata


def main():
    print("=" * 78)
    print(" RAKUTEN RSS FULL SNAPSHOT")
    print("=" * 78)
    print(
        "Batch size :",
        BATCH_SIZE,
    )
    print(
        "Timeout    :",
        f"{BATCH_TIMEOUT_SECONDS:.0f} sec / batch",
    )
    print()

    snapshot, metadata = (
        fetch_full_snapshot()
    )

    print()
    print("=" * 78)
    print(" FINAL RESULT")
    print("=" * 78)

    print(
        "Requested :",
        metadata["Requested"],
    )
    print(
        "Success   :",
        metadata["Success"],
    )
    print(
        "Failed    :",
        metadata["Failed"],
    )
    print(
        "Pending   :",
        metadata["Pending"],
    )
    print(
        "Total time:",
        f"{metadata['ElapsedSeconds']:.3f} sec",
    )

    print()
    print("Batch timings")
    print("-" * 78)

    for item in metadata[
        "BatchTimings"
    ]:
        print(
            f"{item['Batch']:02d} "
            f"req={item['Requested']:3d} "
            f"ok={item['Success']:3d} "
            f"pending={item['Pending']:3d} "
            f"over={item['OverLimit']:3d} "
            f"error={item['ExcelErrors']:3d} "
            f"time={item['TotalSeconds']:.3f}s"
        )

    failed_rows = metadata[
        "FailedRows"
    ]

    if failed_rows:
        print()
        print(
            "First 20 failed rows"
        )
        print("-" * 78)

        for row in failed_rows[:20]:
            print(row)

    print()
    print(
        "DataFrame rows :",
        len(snapshot),
    )

    print("=" * 78)


if __name__ == "__main__":
    main()
