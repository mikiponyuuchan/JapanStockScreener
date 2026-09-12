from pathlib import Path
from datetime import timedelta
import argparse

import holidays
import pandas as pd
import yfinance as yf


def next_business_day(date):
    jp_holidays = holidays.JP(
        years=[
            date.year,
            date.year + 1,
        ]
    )

    d = date + timedelta(days=1)

    while (
        d.weekday() >= 5
        or d in jp_holidays
    ):
        d += timedelta(days=1)

    return d


def normalize_code(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value


def download_intraday(
    code,
    trade_date,
):
    ticker = f"{code}.T"

    start = trade_date
    end = trade_date + timedelta(
        days=1
    )

    df = yf.download(
        ticker,
        start=start.strftime(
            "%Y-%m-%d"
        ),
        end=end.strftime(
            "%Y-%m-%d"
        ),
        interval="5m",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return None

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        df.columns = [
            col[0]
            for col in df.columns
        ]

    df = df.copy()

    index = pd.to_datetime(
        df.index
    )

    if index.tz is not None:
        index = index.tz_convert(
            "Asia/Tokyo"
        ).tz_localize(None)

    df.index = index

    return df.sort_index()


def get_value(row, column):
    value = row[column]

    if isinstance(
        value,
        pd.Series,
    ):
        value = value.iloc[0]

    return float(value)


def pct(value, base):
    if (
        value is None
        or base is None
        or base == 0
    ):
        return None

    return (
        value / base - 1.0
    ) * 100.0


def analyze_stock(
    code,
    base_price,
    trade_date,
):
    df = download_intraday(
        code,
        trade_date,
    )

    if df is None or df.empty:
        return None

    day = df[
        df.index.date
        == trade_date
    ].copy()

    if day.empty:
        return None

    open_price = get_value(
        day.iloc[0],
        "Open",
    )

    high_price = float(
        day["High"]
        .astype(float)
        .max()
    )

    close_price = get_value(
        day.iloc[-1],
        "Close",
    )

    morning = day[
        day.index.time
        <= pd.Timestamp(
            "09:30"
        ).time()
    ]

    if morning.empty:
        price_0930 = None
    else:
        price_0930 = get_value(
            morning.iloc[-1],
            "Close",
        )

    return {
        "翌日寄付":
            open_price,
        "GU率":
            pct(
                open_price,
                base_price,
            ),
        "09:30価格":
            price_0930,
        "09:30騰落率":
            pct(
                price_0930,
                base_price,
            ),
        "翌日高値":
            high_price,
        "翌日高値率":
            pct(
                high_price,
                base_price,
            ),
        "翌日終値":
            close_price,
        "翌日終値率":
            pct(
                close_price,
                base_price,
            ),
    }


def get_base_price(
    code,
    detection_date,
):
    ticker = f"{code}.T"

    start = (
        detection_date
        - timedelta(days=7)
    )

    end = (
        detection_date
        + timedelta(days=1)
    )

    df = yf.download(
        ticker,
        start=start.strftime(
            "%Y-%m-%d"
        ),
        end=end.strftime(
            "%Y-%m-%d"
        ),
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return None

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        df.columns = [
            col[0]
            for col in df.columns
        ]

    index = pd.to_datetime(
        df.index
    )

    if index.tz is not None:
        index = index.tz_convert(
            "Asia/Tokyo"
        ).tz_localize(None)

    df.index = index

    target = df[
        df.index.date
        == detection_date
    ]

    if target.empty:
        return None

    return get_value(
        target.iloc[-1],
        "Close",
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
        help="YYYY-MM-DD",
    )

    args = parser.parse_args()

    detection_date = (
        pd.Timestamp(
            args.date
        ).date()
    )

    trade_date = next_business_day(
        detection_date
    )

    input_path = Path(
        "results"
    ) / (
        f"{args.date}_"
        "earnings_catalyst.xlsx"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            input_path
        )

    df = pd.read_excel(
        input_path
    )

    if df.empty or len(df.columns) == 0:
        print(
            "=" * 74
        )
        print(
            "EARNINGS NEXT-DAY VALIDATION"
        )
        print(
            "=" * 74
        )
        print(
            "Detection date :",
            detection_date,
        )
        print(
            "Trade date     :",
            trade_date,
        )
        print(
            "Candidates     : 0"
        )
        print()
        print(
            "No eligible earnings."
        )
        return

    #
    # Use column positions to avoid
    # Japanese source-code encoding
    # problems.
    #
    code_col = df.columns[0]
    name_col = df.columns[1]

    sales_col = df.columns[3]
    operating_col = df.columns[4]
    ordinary_col = df.columns[5]
    net_col = df.columns[6]

    rating_col = df.columns[7]
    revision_col = df.columns[8]

    target = df[
        df[rating_col].isin(
            [
                "STRONG_GOOD",
                "GOOD",
            ]
        )
    ].copy()

    print(
        "=" * 74
    )

    print(
        "EARNINGS NEXT-DAY VALIDATION"
    )

    print(
        "=" * 74
    )

    print(
        "Detection date :",
        detection_date,
    )

    print(
        "Trade date     :",
        trade_date,
    )

    print(
        "Candidates     :",
        len(target),
    )

    today = pd.Timestamp.now(
        tz="Asia/Tokyo"
    ).date()

    if trade_date > today:
        print()
        print(
            "NOT READY :",
            trade_date,
            "is a future trading day.",
        )
        print(
            "Run this tool after",
            trade_date,
            "market data becomes available.",
        )
        return

    results = []

    for i, row in target.iterrows():
        code = normalize_code(
            row[code_col]
        )

        name = str(
            row[name_col]
        )

        print(
            f"{code} {name}",
            end=" : ",
        )

        try:
            base_price = (
                get_base_price(
                    code,
                    detection_date,
                )
            )

            if base_price is None:
                print(
                    "NO BASE"
                )
                continue

            result = analyze_stock(
                code,
                base_price,
                trade_date,
            )

            if result is None:
                print(
                    "NO INTRADAY"
                )
                continue

            output = {
                "Code":
                    code,
                "Name":
                    name,
                "Rating":
                    row[rating_col],
                "SalesYoY":
                    row[sales_col],
                "OperatingYoY":
                    row[
                        operating_col
                    ],
                "OrdinaryYoY":
                    row[
                        ordinary_col
                    ],
                "NetYoY":
                    row[net_col],
                "Revision":
                    row[
                        revision_col
                    ],
                "BasePrice":
                    base_price,
            }

            output.update(
                result
            )

            results.append(
                output
            )

            print(
                "OK",
                f"GU={result['GU率']:.2f}%",
                f"09:30={result['09:30騰落率']:.2f}%",
                f"High={result['翌日高値率']:.2f}%",
                f"Close={result['翌日終値率']:.2f}%",
            )

        except Exception as e:
            print(
                "ERROR",
                repr(e),
            )

    result_df = pd.DataFrame(
        results
    )

    out_dir = Path(
        "data/analysis"
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_path = (
        out_dir
        / (
            f"{args.date}_"
            "earnings_next_day.csv"
        )
    )

    result_df.to_csv(
        out_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "=" * 74
    )

    print(
        "RESULT"
    )

    print(
        "=" * 74
    )

    print(
        "Completed :",
        len(result_df),
        "/",
        len(target),
    )

    if not result_df.empty:
        for rating in [
            "STRONG_GOOD",
            "GOOD",
        ]:
            part = result_df[
                result_df[
                    "Rating"
                ] == rating
            ]

            if part.empty:
                continue

            print()
            print(
                rating,
                "N=",
                len(part),
            )

            for column in [
                "GU率",
                "09:30騰落率",
                "翌日高値率",
                "翌日終値率",
            ]:
                values = (
                    pd.to_numeric(
                        part[column],
                        errors="coerce",
                    )
                    .dropna()
                )

                if values.empty:
                    continue

                print(
                    f"  {column:<12}",
                    f"mean={values.mean():6.2f}%",
                    f"median={values.median():6.2f}%",
                )

    print()
    print(
        "Saved :",
        out_path,
    )


if __name__ == "__main__":
    main()
