import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, "src")

from screener.loader import load_stock_list


def normalize_code(value):
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    if (
        len(value) == 5
        and value.endswith("0")
        and value[:-1].isalnum()
    ):
        value = value[:-1]

    return value.upper()


def find_column(df, candidates):
    for name in candidates:
        if name in df.columns:
            return name
    return None


def load_universe():
    stocks = load_stock_list()

    code_col = find_column(
        stocks,
        [
            "Code",
            "\u30b3\u30fc\u30c9",
        ],
    )

    name_col = find_column(
        stocks,
        [
            "Name",
            "\u9298\u67c4\u540d",
        ],
    )

    if code_col is None:
        raise RuntimeError(
            "Universe code column not found."
        )

    result = {}

    for _, row in stocks.iterrows():
        code = normalize_code(
            row[code_col]
        )

        name = ""
        if name_col is not None:
            name = str(
                row[name_col]
            ).strip()

        result[code] = name

    return result


def parse_jpx_xls(path):
    raw = pd.read_excel(
        path,
        sheet_name=0,
        header=None,
    )

    rows = []

    for _, row in raw.iterrows():
        if len(row) < 6:
            continue

        code = normalize_code(
            row.iloc[1]
        )

        if not re.fullmatch(
            r"[0-9A-Z]{4}",
            code,
        ):
            continue

        jp_name = str(
            row.iloc[2]
        ).strip()

        trigger_time = row.iloc[4]

        market = str(
            row.iloc[5]
        ).strip()

        rows.append(
            {
                "Code": code,
                "JPXName": jp_name,
                "TriggerTime": trigger_time,
                "Market": market,
            }
        )

    return pd.DataFrame(rows)


def clean_price_frame(df):
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    if isinstance(
        out.columns,
        pd.MultiIndex,
    ):
        if len(out.columns.levels) > 1:
            out.columns = [
                col[-1]
                if col[-1] in {
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                }
                else col[0]
                for col in out.columns
            ]

    out.index = pd.to_datetime(
        out.index
    )

    try:
        out.index = (
            out.index
            .tz_localize(None)
        )
    except TypeError:
        pass

    return out


def download_one(
    code,
    start_date,
    end_date,
):
    ticker = f"{code}.T"

    try:
        df = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        try:
            df = df.xs(
                ticker,
                axis=1,
                level=1,
            )
        except Exception:
            try:
                df.columns = (
                    df.columns
                    .get_level_values(0)
                )
            except Exception:
                return pd.DataFrame()

    return clean_price_frame(df)


def pct(value, base):
    try:
        value = float(value)
        base = float(base)

        if base == 0:
            return None

        return (
            value / base - 1.0
        ) * 100.0
    except Exception:
        return None


def round_value(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return round(
        float(value),
        2,
    )


def analyze_stock(
    code,
    trigger_date,
):
    start_date = (
        trigger_date
        - timedelta(days=10)
    )

    today = date.today()

    requested_end = (
        trigger_date
        + timedelta(days=12)
    )

    end_date = min(
        requested_end,
        today + timedelta(days=1),
    )

    df = download_one(
        code,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    result = {
        "PrevClose": None,
        "Open": None,
        "High": None,
        "Low": None,
        "Close": None,
        "DayChangePct": None,
        "LowPct": None,
        "LowToClosePct": None,
        "NextDate": None,
        "NextOpenPct": None,
        "NextHighPct": None,
        "NextClosePct": None,
        "Day2Date": None,
        "Day2HighPct": None,
        "Day2ClosePct": None,
        "Day3Date": None,
        "Day3HighPct": None,
        "Day3ClosePct": None,
    }

    if df.empty:
        return result

    work = df.copy()

    work["_Date"] = (
        work.index.date
    )

    matches = work[
        work["_Date"]
        == trigger_date
    ]

    if matches.empty:
        return result

    trigger_idx = (
        matches.index[0]
    )

    position = (
        work.index.get_loc(
            trigger_idx
        )
    )

    if isinstance(
        position,
        slice,
    ):
        position = position.start

    if position <= 0:
        return result

    prev_row = work.iloc[
        position - 1
    ]

    day_row = work.iloc[
        position
    ]

    prev_close = float(
        prev_row["Close"]
    )

    open_price = float(
        day_row["Open"]
    )

    high_price = float(
        day_row["High"]
    )

    low_price = float(
        day_row["Low"]
    )

    close_price = float(
        day_row["Close"]
    )

    result.update(
        {
            "PrevClose":
                round_value(
                    prev_close
                ),
            "Open":
                round_value(
                    open_price
                ),
            "High":
                round_value(
                    high_price
                ),
            "Low":
                round_value(
                    low_price
                ),
            "Close":
                round_value(
                    close_price
                ),
            "DayChangePct":
                round_value(
                    pct(
                        close_price,
                        prev_close,
                    )
                ),
            "LowPct":
                round_value(
                    pct(
                        low_price,
                        prev_close,
                    )
                ),
            "LowToClosePct":
                round_value(
                    pct(
                        close_price,
                        low_price,
                    )
                ),
        }
    )

    future = work.iloc[
        position + 1:
    ]

    future_rows = []

    for idx, row in future.iterrows():
        future_rows.append(
            (
                idx.date(),
                row,
            )
        )

    if len(future_rows) >= 1:
        d, row = future_rows[0]

        result.update(
            {
                "NextDate":
                    d.isoformat(),
                "NextOpenPct":
                    round_value(
                        pct(
                            row["Open"],
                            close_price,
                        )
                    ),
                "NextHighPct":
                    round_value(
                        pct(
                            row["High"],
                            close_price,
                        )
                    ),
                "NextClosePct":
                    round_value(
                        pct(
                            row["Close"],
                            close_price,
                        )
                    ),
            }
        )

    if len(future_rows) >= 2:
        d, row = future_rows[1]

        result.update(
            {
                "Day2Date":
                    d.isoformat(),
                "Day2HighPct":
                    round_value(
                        pct(
                            row["High"],
                            close_price,
                        )
                    ),
                "Day2ClosePct":
                    round_value(
                        pct(
                            row["Close"],
                            close_price,
                        )
                    ),
            }
        )

    if len(future_rows) >= 3:
        d, row = future_rows[2]

        result.update(
            {
                "Day3Date":
                    d.isoformat(),
                "Day3HighPct":
                    round_value(
                        pct(
                            row["High"],
                            close_price,
                        )
                    ),
                "Day3ClosePct":
                    round_value(
                        pct(
                            row["Close"],
                            close_price,
                        )
                    ),
            }
        )

    return result


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--file",
        required=True,
    )

    parser.add_argument(
        "--date",
        required=True,
    )

    args = parser.parse_args()

    source_path = Path(
        args.file
    )

    trigger_date = datetime.strptime(
        args.date,
        "%Y-%m-%d",
    ).date()

    if not source_path.exists():
        raise SystemExit(
            f"File not found: {source_path}"
        )

    universe = load_universe()

    jpx = parse_jpx_xls(
        source_path
    )

    print("=" * 76)
    print("SHORT SALE TRIGGER VALIDATION")
    print("=" * 76)
    print(
        "Trigger date  :",
        trigger_date,
    )
    print(
        "JPX rows      :",
        len(jpx),
    )

    jpx = jpx[
        jpx["Code"].isin(
            universe
        )
    ].copy()

    print(
        "Common stocks :",
        len(jpx),
    )

    results = []

    total = len(jpx)

    for number, (_, row) in enumerate(
        jpx.iterrows(),
        start=1,
    ):
        code = row["Code"]

        values = analyze_stock(
            code,
            trigger_date,
        )

        results.append(
            {
                "TriggerDate":
                    trigger_date.isoformat(),
                "Code":
                    code,
                "Name":
                    universe.get(
                        code,
                        row["JPXName"],
                    ),
                "TriggerTime":
                    row["TriggerTime"],
                "Market":
                    row["Market"],
                **values,
            }
        )

        if (
            number % 10 == 0
            or number == total
        ):
            print(
                f"Yahoo : {number}/{total}"
            )

    out = pd.DataFrame(
        results
    )

    output_dir = Path(
        "data/analysis/short_sale_trigger"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / (
            trigger_date.strftime(
                "%Y-%m-%d"
            )
            + "_short_sale_trigger.csv"
        )
    )

    out.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 76)
    print("SUMMARY")
    print("=" * 76)

    print(
        "Rows          :",
        len(out),
    )

    if (
        not out.empty
        and "LowToClosePct"
        in out.columns
    ):
        valid = pd.to_numeric(
            out["LowToClosePct"],
            errors="coerce",
        ).dropna()

        if not valid.empty:
            print(
                "Return mean   :",
                round(
                    valid.mean(),
                    2,
                ),
            )
            print(
                "Return median :",
                round(
                    valid.median(),
                    2,
                ),
            )

    print()
    print(
        out[
            [
                "Code",
                "Name",
                "TriggerTime",
                "DayChangePct",
                "LowPct",
                "LowToClosePct",
                "NextHighPct",
                "NextClosePct",
            ]
        ]
        .to_string(
            index=False
        )
    )

    print()
    print(
        "Saved :",
        output_path.resolve(),
    )


if __name__ == "__main__":
    main()
