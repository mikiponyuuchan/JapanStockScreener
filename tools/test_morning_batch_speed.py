import sys
import time
from pathlib import Path
from datetime import datetime

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from screener.loader import load_stock_list


BATCH_SIZE = 100
PERIOD = "1d"


def extract_ticker_df(raw_df, ticker, batch_size):
    if raw_df is None or raw_df.empty:
        return None

    try:
        if isinstance(raw_df.columns, pd.MultiIndex):

            level0 = raw_df.columns.get_level_values(0)
            level1 = raw_df.columns.get_level_values(1)

            if ticker in level0:
                df = raw_df[ticker].copy()

            elif ticker in level1:
                df = raw_df.loc[:, ticker].copy()

            else:
                return None

        else:
            if batch_size != 1:
                return None

            df = raw_df.copy()

        df = df.dropna(
            how="all"
        )

        if df.empty:
            return None

        return df

    except Exception:
        return None


def main():

    print("=" * 60)
    print("Morning Yahoo batch speed test")
    print("=" * 60)

    stocks = load_stock_list()

    if stocks is None or len(stocks) == 0:
        raise RuntimeError(
            "stock list is empty"
        )

    # loaderの返り値に合わせてコード列を探す
    code_col = None

    for col in stocks.columns:
        values = stocks[col].astype(str)

        ratio = values.str.fullmatch(
            r"[0-9A-Z]{4}"
        ).mean()

        if ratio > 0.8:
            code_col = col
            break

    if code_col is None:
        raise RuntimeError(
            "stock code column not found"
        )

    codes = (
        stocks[code_col]
        .astype(str)
        .tolist()
    )

    total = len(codes)

    print(
        f"stocks      : {total}"
    )

    print(
        f"period      : {PERIOD}"
    )

    print(
        f"batch size  : {BATCH_SIZE}"
    )

    print()

    start_time = time.perf_counter()

    success = 0
    empty = 0
    error_batches = 0

    latest_times = []

    for batch_start in range(
        0,
        total,
        BATCH_SIZE
    ):

        batch_codes = codes[
            batch_start:
            batch_start + BATCH_SIZE
        ]

        tickers = [
            f"{code}.T"
            for code in batch_codes
        ]

        batch_no = (
            batch_start // BATCH_SIZE
            + 1
        )

        batch_total = (
            total + BATCH_SIZE - 1
        ) // BATCH_SIZE

        batch_start_time = (
            time.perf_counter()
        )

        try:

            raw_df = yf.download(
                tickers=tickers,
                period=PERIOD,
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True
            )

        except Exception as e:

            error_batches += 1

            print(
                f"BATCH ERROR "
                f"{batch_no}/{batch_total} "
                f": {e}"
            )

            continue

        for code in batch_codes:

            ticker = f"{code}.T"

            df = extract_ticker_df(
                raw_df,
                ticker,
                len(batch_codes)
            )

            if df is None or df.empty:
                empty += 1
                continue

            success += 1

            try:
                latest_times.append(
                    df.index[-1]
                )
            except Exception:
                pass

        elapsed_batch = (
            time.perf_counter()
            - batch_start_time
        )

        completed = min(
            batch_start + BATCH_SIZE,
            total
        )

        if (
            completed % 1000 == 0
            or completed == total
        ):

            elapsed_total = (
                time.perf_counter()
                - start_time
            )

            print(
                f"{completed:4d} / "
                f"{total}  "
                f"batch={elapsed_batch:.1f}s  "
                f"total={elapsed_total:.1f}s"
            )

    total_elapsed = (
        time.perf_counter()
        - start_time
    )

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)

    print(
        f"Total stocks     : {total}"
    )

    print(
        f"Success          : {success}"
    )

    print(
        f"Empty            : {empty}"
    )

    print(
        f"Batch errors     : {error_batches}"
    )

    print(
        f"Total time       : "
        f"{total_elapsed:.1f} sec"
    )

    if total_elapsed > 0:

        print(
            f"Stocks / sec     : "
            f"{total / total_elapsed:.1f}"
        )

    if latest_times:

        try:

            print(
                f"Latest index max : "
                f"{max(latest_times)}"
            )

            print(
                f"Latest index min : "
                f"{min(latest_times)}"
            )

        except Exception:
            pass

    print()
    print(
        "Finished at      : "
        + datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )


if __name__ == "__main__":
    main()