import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


DATA_DIR = Path("data/yahoo_credit")

TOP_URL = "https://finance.yahoo.co.jp/quote/{}.T"

CREDIT_URL = (
    "https://finance.yahoo.co.jp/quote/{}.T/history?styl=margin"
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
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
}

MAX_RETRIES = 2
REQUEST_DELAY = 0.8
RETRY_DELAYS = [3, 8]


def get_credit_history(
    code: str,
    timeout: int = 20,
) -> pd.DataFrame | None:

    code = str(code).strip()

    if not code:
        return None

    top_url = TOP_URL.format(code)
    credit_url = CREDIT_URL.format(code)

    session = requests.Session()
    session.headers.update(HEADERS)

    # --------------------------------------------------------
    # Step 1: access stock top page
    # --------------------------------------------------------

    top_ok = False

    for attempt in range(MAX_RETRIES + 1):

        try:
            response = session.get(
                top_url,
                timeout=timeout,
            )

            if response.status_code == 200:
                top_ok = True
                break

            print(
                f"[{code}] TOP HTTP "
                f"{response.status_code}"
            )

        except requests.RequestException as e:

            print(
                f"[{code}] TOP request error: {e}"
            )

        if attempt < MAX_RETRIES:
            time.sleep(
                RETRY_DELAYS[
                    min(
                        attempt,
                        len(RETRY_DELAYS) - 1,
                    )
                ]
            )

    if not top_ok:

        print(
            f"[{code}] TOP page failed"
        )

        return None

    # --------------------------------------------------------
    # Step 2: access credit history page
    # --------------------------------------------------------

    time.sleep(REQUEST_DELAY)

    response = None

    for attempt in range(MAX_RETRIES + 1):

        try:

            response = session.get(
                credit_url,
                timeout=timeout,
            )

            status = response.status_code

            print(
                f"[{code}] CREDIT HTTP "
                f"{status} "
                f"size={len(response.content):,}"
            )

            if status == 200:
                break

        except requests.RequestException as e:

            print(
                f"[{code}] CREDIT request error: {e}"
            )

            response = None

        if attempt < MAX_RETRIES:

            delay = RETRY_DELAYS[
                min(
                    attempt,
                    len(RETRY_DELAYS) - 1,
                )
            ]

            print(
                f"[{code}] retry after {delay}s"
            )

            time.sleep(delay)

    if response is None:
        return None

    if response.status_code != 200:

        print(
            f"[{code}] CREDIT page failed"
        )

        return None

    # --------------------------------------------------------
    # Step 3: parse HTML
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    tables = soup.find_all("table")

    print(
        f"[{code}] tables={len(tables)}"
    )

    if not tables:

        print(
            f"[{code}] no table"
        )

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

        print(
            f"[{code}] no credit table"
        )

        return None

    # --------------------------------------------------------
    # Step 4: DataFrame
    # --------------------------------------------------------

    header = target_rows[0]

    data_rows = []

    for row in target_rows[1:]:

        if len(row) < len(header):
            continue

        data_rows.append(
            row[:len(header)]
        )

    if not data_rows:

        print(
            f"[{code}] no data rows"
        )

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

    # --------------------------------------------------------
    # Step 5: numeric conversion
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Step 6: date conversion
    # --------------------------------------------------------

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


def save_credit_history(
    df: pd.DataFrame,
    code: str,
) -> Path | None:

    if df is None or df.empty:
        return None

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

    return path


def main():

    print("=" * 60)
    print("Yahoo credit test")
    print("=" * 60)

    test_codes = [
        "1301",
        "1332",
        "1605",
        "1801",
        "2002",
    ]

    success = 0
    failed = 0

    for code in test_codes:

        start = time.perf_counter()

        print()
        print(
            f"[{code}] retrieving..."
        )

        try:

            df = get_credit_history(code)

            elapsed = (
                time.perf_counter()
                - start
            )

            if df is not None and not df.empty:

                success += 1

                print(
                    f"[{code}] SUCCESS "
                    f"{len(df)} rows "
                    f"({elapsed:.2f}s)"
                )

                print(
                    df.head(3).to_string(
                        index=False
                    )
                )

                path = save_credit_history(
                    df,
                    code,
                )

                print(
                    f"saved: {path}"
                )

            else:

                failed += 1

                print(
                    f"[{code}] FAILED "
                    f"({elapsed:.2f}s)"
                )

        except Exception as e:

            failed += 1

            elapsed = (
                time.perf_counter()
                - start
            )

            print(
                f"[{code}] ERROR: {e} "
                f"({elapsed:.2f}s)"
            )

    print()
    print("=" * 60)
    print("TEST RESULT")
    print("=" * 60)
    print(
        f"success: {success}/{len(test_codes)}"
    )
    print(
        f"failed : {failed}/{len(test_codes)}"
    )


if __name__ == "__main__":
    main()