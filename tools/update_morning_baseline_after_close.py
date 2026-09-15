import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from screener.loader import load_stock_list
from services.yahoo_service import (
    _download_history_batch,
    get_expected_market_date,
)
from services.morning_baseline_service import (
    save_morning_baseline,
)


BATCH_SIZE = 100
FRESH_RATIO_MIN = 0.90


def main():
    print("=" * 72)
    print(" MORNING BASELINE UPDATE")
    print("=" * 72)

    stocks = load_stock_list()

    if stocks is None or stocks.empty:
        print("ERROR : No stocks.")
        return 1

    codes = [
        str(code)
        for code in stocks["\u30b3\u30fc\u30c9"]
    ]

    print(f"Stocks        : {len(codes)}")
    print("Yahoo download: start")

    started = time.time()

    history_map = _download_history_batch(
        codes,
        period="6mo",
        batch_size=BATCH_SIZE,
    )

    elapsed = time.time() - started

    expected_date = get_expected_market_date()

    valid_count = 0
    fresh_count = 0
    date_counts = {}

    for history_df in history_map.values():
        if (
            history_df is None
            or history_df.empty
            or "Date" not in history_df.columns
        ):
            continue

        latest_date = pd.to_datetime(
            history_df["Date"],
            errors="coerce",
        ).max()

        if pd.isna(latest_date):
            continue

        latest_date = (
            pd.Timestamp(latest_date)
            .tz_localize(None)
            .normalize()
        )

        valid_count += 1

        if latest_date >= expected_date:
            fresh_count += 1

        date_str = latest_date.strftime(
            "%Y-%m-%d"
        )

        date_counts[date_str] = (
            date_counts.get(date_str, 0) + 1
        )

    fresh_ratio = (
        fresh_count / valid_count
        if valid_count
        else 0.0
    )

    print(
        f"Yahoo time    : {elapsed:.1f} sec"
    )
    print(
        f"Yahoo success : {len(history_map)}"
    )
    print(
        "Expected date : "
        f"{expected_date.strftime('%Y-%m-%d')}"
    )
    print(
        f"Fresh data    : {fresh_count} / "
        f"{valid_count} ({fresh_ratio:.2%})"
    )

    if date_counts:
        summary = ", ".join(
            f"{date}={count}"
            for date, count
            in sorted(
                date_counts.items(),
                reverse=True,
            )
        )
        print(f"Date summary  : {summary}")

    if fresh_ratio < FRESH_RATIO_MIN:
        print()
        print(
            "ERROR : Yahoo daily data is stale."
        )
        print(
            "Morning baseline was NOT updated."
        )
        return 1

    saved = save_morning_baseline(
        history_map,
        stocks=stocks,
    )

    if not saved:
        print()
        print(
            "ERROR : Morning baseline was "
            "not saved."
        )
        return 1

    print()
    print(
        "Morning baseline update completed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
