import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, "src")

from screener.loader import load_stock_list


SOURCE_DIR = Path("data/jpx_short_sale_trigger")
OUTPUT_DIR = Path("data/analysis/short_sale_trigger")

BATCH_SIZE = 100


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


def parse_trigger_time(value):
    if pd.isna(value):
        return None, None

    text = str(value).strip()

    match = re.search(
        r"(\d{1,2}):(\d{2}):(\d{2})",
        text,
    )

    if not match:
        return text, None

    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3))

    total_minutes = (
        hour * 60
        + minute
        + second / 60.0
    )

    normalized = (
        f"{hour:02d}:"
        f"{minute:02d}:"
        f"{second:02d}"
    )

    return normalized, total_minutes


def time_bucket(minutes):
    if minutes is None:
        return "UNKNOWN"

    if minutes < 10 * 60:
        return "09:00-09:59"

    if minutes < 13 * 60:
        return "10:00-12:59"

    if minutes < 14.5 * 60:
        return "13:00-14:29"

    return "14:30-15:30"


def parse_xls(path):
    raw = pd.read_excel(
        path,
        sheet_name=0,
        header=None,
    )

    match = re.match(
        r"(\d{8})_Triggered_Stocks\.xls",
        path.name,
        re.IGNORECASE,
    )

    if not match:
        return pd.DataFrame()

    trigger_date = datetime.strptime(
        match.group(1),
        "%Y%m%d",
    ).date()

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

        trigger_time, minutes = (
            parse_trigger_time(
                row.iloc[4]
            )
        )

        rows.append(
            {
                "TriggerDate":
                    trigger_date,
                "Code":
                    code,
                "JPXName":
                    str(
                        row.iloc[2]
                    ).strip(),
                "TriggerTime":
                    trigger_time,
                "TriggerMinutes":
                    minutes,
                "TriggerTimeBucket":
                    time_bucket(
                        minutes
                    ),
                "Market":
                    str(
                        row.iloc[5]
                    ).strip(),
            }
        )

    return pd.DataFrame(rows)


def load_trigger_events(month, universe):
    files = sorted(
        SOURCE_DIR.glob(
            f"{month}*_Triggered_Stocks.xls"
        )
    )

    if not files:
        raise RuntimeError(
            f"No XLS files found for {month}"
        )

    frames = []

    for path in files:
        df = parse_xls(path)

        if not df.empty:
            frames.append(df)

    if not frames:
        raise RuntimeError(
            "No trigger rows parsed."
        )

    events = pd.concat(
        frames,
        ignore_index=True,
    )

    raw_count = len(events)

    events = events[
        events["Code"].isin(
            universe
        )
    ].copy()

    events["Name"] = events["Code"].map(
        universe
    )

    events = events.sort_values(
        [
            "TriggerDate",
            "Code",
        ]
    ).reset_index(
        drop=True
    )

    print(
        "XLS files     :",
        len(files),
    )
    print(
        "JPX rows      :",
        raw_count,
    )
    print(
        "Common stocks :",
        len(events),
    )

    return events


def download_batch(codes, start_date, end_date):
    history = {}

    total = len(codes)

    for start in range(
        0,
        total,
        BATCH_SIZE,
    ):
        subset = codes[
            start:start + BATCH_SIZE
        ]

        tickers = [
            f"{code}.T"
            for code in subset
        ]

        end_pos = min(
            start + BATCH_SIZE,
            total,
        )

        print(
            f"Yahoo batch   : "
            f"{start + 1}-{end_pos} / {total}"
        )

        try:
            df = yf.download(
                tickers=tickers,
                start=start_date,
                end=end_date,
                auto_adjust=False,
                progress=False,
                group_by="column",
                threads=True,
            )
        except Exception as exc:
            print(
                "Yahoo batch ERROR :",
                exc,
            )
            continue

        if df is None or df.empty:
            continue

        if not isinstance(
            df.columns,
            pd.MultiIndex,
        ):
            if len(subset) == 1:
                code = subset[0]
                one = df.copy()
                one.index = pd.to_datetime(
                    one.index
                )
                history[code] = one
            continue

        level0 = set(
            df.columns.get_level_values(0)
        )
        level1 = set(
            df.columns.get_level_values(1)
        )

        for code in subset:
            ticker = f"{code}.T"

            one = None

            if ticker in level1:
                try:
                    one = df.xs(
                        ticker,
                        axis=1,
                        level=1,
                    ).copy()
                except Exception:
                    one = None

            elif ticker in level0:
                try:
                    one = df.xs(
                        ticker,
                        axis=1,
                        level=0,
                    ).copy()
                except Exception:
                    one = None

            if one is None or one.empty:
                continue

            one.index = pd.to_datetime(
                one.index
            )

            one = one.dropna(
                how="all"
            )

            history[code] = one

    return history


def pct(value, base):
    try:
        value = float(value)
        base = float(base)

        if pd.isna(value) or pd.isna(base):
            return np.nan

        if base == 0:
            return np.nan

        return (
            value / base - 1.0
        ) * 100.0

    except Exception:
        return np.nan


def rv(value):
    if pd.isna(value):
        return np.nan

    return round(
        float(value),
        2,
    )


def analyze_event(event, history):
    result = {
        "PrevClose": np.nan,
        "Open": np.nan,
        "High": np.nan,
        "Low": np.nan,
        "Close": np.nan,
        "DayChangePct": np.nan,
        "LowPct": np.nan,
        "LowToClosePct": np.nan,
        "NextDate": None,
        "NextOpenPct": np.nan,
        "NextHighPct": np.nan,
        "NextClosePct": np.nan,
        "NextHighFromOpenPct": np.nan,
        "NextLowFromOpenPct": np.nan,
        "NextCloseFromOpenPct": np.nan,
        "Day2Date": None,
        "Day2HighPct": np.nan,
        "Day2ClosePct": np.nan,
        "Day3Date": None,
        "Day3HighPct": np.nan,
        "Day3ClosePct": np.nan,
    }

    code = event["Code"]
    trigger_date = event["TriggerDate"]

    df = history.get(code)

    if df is None or df.empty:
        return result

    work = df.copy()

    work["_Date"] = work.index.date

    matched = work[
        work["_Date"]
        == trigger_date
    ]

    if matched.empty:
        return result

    idx = matched.index[0]

    location = work.index.get_loc(idx)

    if isinstance(location, slice):
        location = location.start

    if location <= 0:
        return result

    prev_row = work.iloc[
        location - 1
    ]

    day_row = work.iloc[
        location
    ]

    required = [
        "Open",
        "High",
        "Low",
        "Close",
    ]

    for col in required:
        if col not in day_row.index:
            return result

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
                rv(prev_close),
            "Open":
                rv(open_price),
            "High":
                rv(high_price),
            "Low":
                rv(low_price),
            "Close":
                rv(close_price),
            "DayChangePct":
                rv(
                    pct(
                        close_price,
                        prev_close,
                    )
                ),
            "LowPct":
                rv(
                    pct(
                        low_price,
                        prev_close,
                    )
                ),
            "LowToClosePct":
                rv(
                    pct(
                        close_price,
                        low_price,
                    )
                ),
        }
    )

    future = work.iloc[
        location + 1:
    ]

    if len(future) >= 1:
        row = future.iloc[0]
        d = future.index[0].date()

        next_open = float(
            row["Open"]
        )

        next_high = float(
            row["High"]
        )

        next_low = float(
            row["Low"]
        )

        next_close = float(
            row["Close"]
        )

        result.update(
            {
                "NextDate":
                    d.isoformat(),
                "NextOpenPct":
                    rv(
                        pct(
                            next_open,
                            close_price,
                        )
                    ),
                "NextHighPct":
                    rv(
                        pct(
                            next_high,
                            close_price,
                        )
                    ),
                "NextClosePct":
                    rv(
                        pct(
                            next_close,
                            close_price,
                        )
                    ),
                "NextHighFromOpenPct":
                    rv(
                        pct(
                            next_high,
                            next_open,
                        )
                    ),
                "NextLowFromOpenPct":
                    rv(
                        pct(
                            next_low,
                            next_open,
                        )
                    ),
                "NextCloseFromOpenPct":
                    rv(
                        pct(
                            next_close,
                            next_open,
                        )
                    ),
            }
        )

    if len(future) >= 2:
        row = future.iloc[1]
        d = future.index[1].date()

        result.update(
            {
                "Day2Date":
                    d.isoformat(),
                "Day2HighPct":
                    rv(
                        pct(
                            row["High"],
                            close_price,
                        )
                    ),
                "Day2ClosePct":
                    rv(
                        pct(
                            row["Close"],
                            close_price,
                        )
                    ),
            }
        )

    if len(future) >= 3:
        row = future.iloc[2]
        d = future.index[2].date()

        result.update(
            {
                "Day3Date":
                    d.isoformat(),
                "Day3HighPct":
                    rv(
                        pct(
                            row["High"],
                            close_price,
                        )
                    ),
                "Day3ClosePct":
                    rv(
                        pct(
                            row["Close"],
                            close_price,
                        )
                    ),
            }
        )

    return result


def add_return_band(df):
    values = pd.to_numeric(
        df["LowToClosePct"],
        errors="coerce",
    )

    df["ReturnBand"] = pd.cut(
        values,
        bins=[
            -np.inf,
            2.0,
            5.0,
            10.0,
            np.inf,
        ],
        right=False,
        labels=[
            "<2",
            "2-<5",
            "5-<10",
            ">=10",
        ],
    )

    return df


def positive_rate(series, level):
    s = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if s.empty:
        return np.nan

    return round(
        (s >= level).mean()
        * 100.0,
        1,
    )


def make_summary(panel):
    rows = []

    order = [
        "<2",
        "2-<5",
        "5-<10",
        ">=10",
    ]

    for band in order:
        group = panel[
            panel["ReturnBand"].astype(str)
            == band
        ]

        if group.empty:
            rows.append(
                {
                    "ReturnBand": band,
                    "N": 0,
                }
            )
            continue

        rows.append(
            {
                "ReturnBand":
                    band,
                "N":
                    len(group),
                "LowToCloseMean":
                    rv(
                        group[
                            "LowToClosePct"
                        ].mean()
                    ),
                "LowToCloseMedian":
                    rv(
                        group[
                            "LowToClosePct"
                        ].median()
                    ),
                "NextOpenMean":
                    rv(
                        group[
                            "NextOpenPct"
                        ].mean()
                    ),
                "NextHighMean":
                    rv(
                        group[
                            "NextHighPct"
                        ].mean()
                    ),
                "NextHighMedian":
                    rv(
                        group[
                            "NextHighPct"
                        ].median()
                    ),
                "NextHigh3Rate":
                    positive_rate(
                        group[
                            "NextHighPct"
                        ],
                        3.0,
                    ),
                "NextHigh5Rate":
                    positive_rate(
                        group[
                            "NextHighPct"
                        ],
                        5.0,
                    ),
                "NextHigh10Rate":
                    positive_rate(
                        group[
                            "NextHighPct"
                        ],
                        10.0,
                    ),
                "NextCloseMean":
                    rv(
                        group[
                            "NextClosePct"
                        ].mean()
                    ),
                "NextCloseMedian":
                    rv(
                        group[
                            "NextClosePct"
                        ].median()
                    ),
                "NextHighFromOpenMean":
                    rv(
                        group[
                            "NextHighFromOpenPct"
                        ].mean()
                    ),
                "NextHighFromOpenMedian":
                    rv(
                        group[
                            "NextHighFromOpenPct"
                        ].median()
                    ),
                "NextHighFromOpen3Rate":
                    positive_rate(
                        group[
                            "NextHighFromOpenPct"
                        ],
                        3.0,
                    ),
                "NextHighFromOpen5Rate":
                    positive_rate(
                        group[
                            "NextHighFromOpenPct"
                        ],
                        5.0,
                    ),
                "NextLowFromOpenMean":
                    rv(
                        group[
                            "NextLowFromOpenPct"
                        ].mean()
                    ),
                "NextLowFromOpenMedian":
                    rv(
                        group[
                            "NextLowFromOpenPct"
                        ].median()
                    ),
                "NextCloseFromOpenMean":
                    rv(
                        group[
                            "NextCloseFromOpenPct"
                        ].mean()
                    ),
                "NextCloseFromOpenMedian":
                    rv(
                        group[
                            "NextCloseFromOpenPct"
                        ].median()
                    ),
                "Day2HighMean":
                    rv(
                        group[
                            "Day2HighPct"
                        ].mean()
                    ),
                "Day3HighMean":
                    rv(
                        group[
                            "Day3HighPct"
                        ].mean()
                    ),
            }
        )

    return pd.DataFrame(rows)


def make_time_summary(panel):
    rows = []

    order = [
        "09:00-09:59",
        "10:00-12:59",
        "13:00-14:29",
        "14:30-15:30",
        "UNKNOWN",
    ]

    for bucket in order:
        group = panel[
            panel[
                "TriggerTimeBucket"
            ]
            == bucket
        ]

        if group.empty:
            continue

        rows.append(
            {
                "TriggerTimeBucket":
                    bucket,
                "N":
                    len(group),
                "LowToCloseMean":
                    rv(
                        group[
                            "LowToClosePct"
                        ].mean()
                    ),
                "NextHighMean":
                    rv(
                        group[
                            "NextHighPct"
                        ].mean()
                    ),
                "NextHighMedian":
                    rv(
                        group[
                            "NextHighPct"
                        ].median()
                    ),
                "NextHigh5Rate":
                    positive_rate(
                        group[
                            "NextHighPct"
                        ],
                        5.0,
                    ),
                "NextCloseMean":
                    rv(
                        group[
                            "NextClosePct"
                        ].mean()
                    ),
            }
        )

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--month",
        required=True,
        help="YYYYMM",
    )

    args = parser.parse_args()

    print("=" * 76)
    print("SHORT SALE TRIGGER MONTHLY BACKTEST")
    print("=" * 76)
    print("Month         :", args.month)

    universe = load_universe()

    events = load_trigger_events(
        args.month,
        universe,
    )

    if events.empty:
        raise SystemExit(
            "No common-stock events."
        )

    min_date = events[
        "TriggerDate"
    ].min()

    max_date = events[
        "TriggerDate"
    ].max()

    start_date = (
        min_date
        - timedelta(days=10)
    ).isoformat()

    end_date = (
        max_date
        + timedelta(days=12)
    ).isoformat()

    codes = sorted(
        events[
            "Code"
        ].unique()
    )

    print(
        "Unique codes  :",
        len(codes),
    )
    print(
        "Yahoo period  :",
        start_date,
        "to",
        end_date,
    )
    print()

    history = download_batch(
        codes,
        start_date,
        end_date,
    )

    print()
    print(
        "Yahoo success :",
        len(history),
        "/",
        len(codes),
    )

    rows = []

    total = len(events)

    for number, (_, event) in enumerate(
        events.iterrows(),
        start=1,
    ):
        values = analyze_event(
            event,
            history,
        )

        rows.append(
            {
                "TriggerDate":
                    event[
                        "TriggerDate"
                    ].isoformat(),
                "Code":
                    event["Code"],
                "Name":
                    event["Name"],
                "TriggerTime":
                    event[
                        "TriggerTime"
                    ],
                "TriggerMinutes":
                    event[
                        "TriggerMinutes"
                    ],
                "TriggerTimeBucket":
                    event[
                        "TriggerTimeBucket"
                    ],
                "Market":
                    event["Market"],
                **values,
            }
        )

        if (
            number % 100 == 0
            or number == total
        ):
            print(
                f"Analyze       : "
                f"{number}/{total}"
            )

    panel = pd.DataFrame(rows)

    panel = add_return_band(
        panel
    )

    summary = make_summary(
        panel
    )

    time_summary = make_time_summary(
        panel
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    panel_path = (
        OUTPUT_DIR
        / (
            f"{args.month}_"
            "short_sale_trigger_panel.csv"
        )
    )

    summary_path = (
        OUTPUT_DIR
        / (
            f"{args.month}_"
            "short_sale_trigger_summary.csv"
        )
    )

    time_path = (
        OUTPUT_DIR
        / (
            f"{args.month}_"
            "short_sale_trigger_time_summary.csv"
        )
    )

    panel.to_csv(
        panel_path,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        summary_path,
        index=False,
        encoding="utf-8-sig",
    )

    time_summary.to_csv(
        time_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 76)
    print("RETURN BAND SUMMARY")
    print("=" * 76)

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 76)
    print("TRIGGER TIME SUMMARY")
    print("=" * 76)

    print(
        time_summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 76)
    print("SAVED")
    print("=" * 76)
    print("Panel   :", panel_path)
    print("Summary :", summary_path)
    print("Time    :", time_path)


if __name__ == "__main__":
    main()
