import argparse
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ============================================================
# Settings
# ============================================================

DATA_DIR = Path("data/yahoo_credit_test")

TOP_URL = "https://finance.yahoo.co.jp/quote/{}.T"

CREDIT_URL = (
    "https://finance.yahoo.co.jp/"
    "quote/{}.T/history?styl=margin"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 "
        "Safari/537.36"
    ),
    "Accept-Language": (
        "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
}

# 通常アクセス間隔
REQUEST_DELAY = 1.0

# HTTP 500 / 429 のリトライ回数
MAX_RETRIES = 1

# リトライ待機時間
RETRY_DELAY = 5

# TOP_500 が連続したら停止
MAX_CONSECUTIVE_500 = 5


# ============================================================
# Credit table parser
# ============================================================

def parse_credit_html(
    html: str,
    code: str,
) -> pd.DataFrame | None:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    tables = soup.find_all("table")

    if not tables:
        return None

    required = {
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    }

    target_rows = None

    for table in tables:

        rows = []

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            values = [
                cell.get_text(
                    " ",
                    strip=True,
                )
                for cell in cells
            ]

            if values:
                rows.append(values)

        if not rows:
            continue

        header = set(rows[0])

        if required.issubset(header):

            target_rows = rows
            break

    if target_rows is None:
        return None

    header = target_rows[0]

    data_rows = []

    for row in target_rows[1:]:

        if len(row) < len(header):
            continue

        data_rows.append(
            row[:len(header)]
        )

    if not data_rows:
        return None

    df = pd.DataFrame(
        data_rows,
        columns=header,
    )

    columns = [
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    df = df[columns].copy()

    df.insert(
        0,
        "コード",
        code,
    )

    numeric_columns = [
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    for column in numeric_columns:

        df[column] = (
            df[column]
            .astype(str)
            .str.replace(
                ",",
                "",
                regex=False,
            )
            .str.strip()
        )

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["日付"] = pd.to_datetime(
        df["日付"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["日付"]
    )

    if df.empty:
        return None

    df = (
        df.sort_values(
            "日付",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    return df


# ============================================================
# One stock
# ============================================================

def get_credit(
    session: requests.Session,
    code: str,
    timeout: int = 20,
):

    top_url = TOP_URL.format(code)
    credit_url = CREDIT_URL.format(code)

    # --------------------------------------------------------
    # TOP page
    # --------------------------------------------------------

    try:

        response = session.get(
            top_url,
            timeout=timeout,
        )

    except requests.RequestException as e:

        return None, "TOP_ERROR", str(e)

    if response.status_code != 200:

        return (
            None,
            f"TOP_{response.status_code}",
            "",
        )

    time.sleep(0.5)

    # --------------------------------------------------------
    # CREDIT page
    # --------------------------------------------------------

    for attempt in range(MAX_RETRIES + 1):

        try:

            response = session.get(
                credit_url,
                timeout=timeout,
            )

        except requests.RequestException as e:

            if attempt < MAX_RETRIES:

                time.sleep(RETRY_DELAY)
                continue

            return None, "REQUEST_ERROR", str(e)

        status = response.status_code

        if status == 200:

            df = parse_credit_html(
                response.text,
                code,
            )

            if df is None:

                return (
                    None,
                    "NO_TABLE",
                    "",
                )

            return (
                df,
                "SUCCESS",
                "",
            )

        if status == 500:

            if attempt < MAX_RETRIES:

                time.sleep(RETRY_DELAY)
                continue

            return (
                None,
                "HTTP_500",
                "",
            )

        if status == 429:

            if attempt < MAX_RETRIES:

                time.sleep(RETRY_DELAY)
                continue

            return (
                None,
                "HTTP_429",
                "",
            )

        return (
            None,
            f"HTTP_{status}",
            "",
        )

    return None, "UNKNOWN", ""


# ============================================================
# Save result
# ============================================================

def save_result(
    df: pd.DataFrame,
    code: str,
):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = DATA_DIR / f"{code}.csv"

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Yahoo信用残 500銘柄テスト"
        )
    )

    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help=(
            "開始番号（1～500）"
            " 例: --start 76"
        ),
    )

    args = parser.parse_args()

    start_index = args.start

    if start_index < 1:
        start_index = 1

    if start_index > 500:

        print(
            "start must be between 1 and 500."
        )

        return

    print("=" * 70)
    print("Yahoo credit 500 stock test")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # JPX stock list
    # --------------------------------------------------------

    stock_list_path = Path(
        "data/jpx_stock_list.xls"
    )

    if not stock_list_path.exists():

        print(
            f"Stock list not found: "
            f"{stock_list_path}"
        )

        return

    stock_df = pd.read_excel(
        stock_list_path
    )

    # コード列を探す
    code_column = None

    for column in stock_df.columns:

        name = str(column)

        if (
            "コード" in name
            or "Code" in name
        ):

            code_column = column
            break

    if code_column is None:

        print("Code column not found")
        print(
            stock_df.columns.tolist()
        )

        return

    codes = (
        stock_df[code_column]
        .dropna()
        .astype(str)
        .str.replace(
            ".0",
            "",
            regex=False,
        )
        .str.strip()
        .tolist()
    )

    codes = [
        code
        for code in codes
        if code
    ]

    # 最初の500銘柄
    codes = codes[:500]

    total_codes = len(codes)

    if start_index > total_codes:

        print(
            f"start index {start_index} "
            f"is greater than "
            f"total stocks {total_codes}"
        )

        return

    print(
        f"Test stocks : {total_codes}"
    )

    print(
        f"Start index : {start_index}"
    )

    print()

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    success = 0
    skipped = 0
    http_500 = 0
    http_429 = 0
    no_table = 0
    other_failed = 0

    failed_codes = []

    consecutive_500 = 0

    start_all = time.perf_counter()

    try:

        for index in range(
            start_index,
            total_codes + 1,
        ):

            code = codes[index - 1]

            # ------------------------------------------------
            # 既に成功済みならスキップ
            # ------------------------------------------------

            saved_path = (
                DATA_DIR / f"{code}.csv"
            )

            if saved_path.exists():

                skipped += 1

                print(
                    f"[{index}/{total_codes}] "
                    f"{code} SKIP "
                    f"(already saved)"
                )

                continue

            start = time.perf_counter()

            print(
                f"[{index}/{total_codes}] "
                f"{code} retrieving...",
                end=" ",
                flush=True,
            )

            try:

                df, status, detail = get_credit(
                    session,
                    code,
                )

                elapsed = (
                    time.perf_counter()
                    - start
                )

                if status == "SUCCESS":

                    success += 1

                    consecutive_500 = 0

                    save_result(
                        df,
                        code,
                    )

                    print(
                        f"SUCCESS "
                        f"{len(df)} rows "
                        f"({elapsed:.2f}s)"
                    )

                elif status == "HTTP_500":

                    http_500 += 1
                    failed_codes.append(code)

                    consecutive_500 += 1

                    print(
                        f"HTTP 500 "
                        f"({elapsed:.2f}s)"
                    )

                    if (
                        consecutive_500
                        >= MAX_CONSECUTIVE_500
                    ):

                        print()
                        print(
                            "Yahoo側のHTTP 500が"
                            f" {MAX_CONSECUTIVE_500}回"
                            "連続したため、"
                            "テストを停止します。"
                        )

                        break

                elif status == "HTTP_429":

                    http_429 += 1
                    failed_codes.append(code)

                    consecutive_500 = 0

                    print(
                        f"HTTP 429 "
                        f"({elapsed:.2f}s)"
                    )

                elif status == "NO_TABLE":

                    no_table += 1
                    failed_codes.append(code)

                    consecutive_500 = 0

                    print(
                        f"NO TABLE "
                        f"({elapsed:.2f}s)"
                    )

                else:

                    other_failed += 1
                    failed_codes.append(code)

                    consecutive_500 = 0

                    print(
                        f"FAILED {status} "
                        f"({elapsed:.2f}s)"
                    )

            except Exception as e:

                other_failed += 1
                failed_codes.append(code)

                consecutive_500 = 0

                elapsed = (
                    time.perf_counter()
                    - start
                )

                print(
                    f"ERROR {e} "
                    f"({elapsed:.2f}s)"
                )

            time.sleep(
                REQUEST_DELAY
            )

    except KeyboardInterrupt:

        print()
        print()
        print(
            "KeyboardInterrupt: "
            "test stopped by user."
        )

    total_time = (
        time.perf_counter()
        - start_all
    )

    processed = (
        success
        + skipped
        + http_500
        + http_429
        + no_table
        + other_failed
    )

    print()
    print("=" * 70)
    print("TEST RESULT")
    print("=" * 70)

    print(
        f"start     : {start_index}"
    )

    print(
        f"processed : {processed}"
    )

    print(
        f"success   : {success}"
    )

    print(
        f"skipped   : {skipped}"
    )

    print(
        f"HTTP 500  : {http_500}"
    )

    print(
        f"HTTP 429  : {http_429}"
    )

    print(
        f"NO TABLE  : {no_table}"
    )

    print(
        f"other     : {other_failed}"
    )

    print(
        f"time      : {total_time:.1f}s"
    )

    print()

    if failed_codes:

        print(
            "Failed codes:"
        )

        print(
            ", ".join(failed_codes)
        )

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()