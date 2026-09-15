from datetime import timedelta
from pathlib import Path
import sys

import holidays
import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "data" / "analysis"
TRACKING = ROOT / "data" / "tracking"
OUT_PATH = TRACKING / "earnings_catalyst_forward.csv"

FORWARD_START = pd.Timestamp("2026-09-11").date()

COL_GU = "\u0047\u0055\u7387"
COL_0930_PRICE = "\u0030\u0039\u003a\u0033\u0030\u4fa1\u683c"
COL_0930 = "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387"
COL_OPEN = "\u7fcc\u65e5\u5bc4\u4ed8"
COL_HIGH_PRICE = "\u7fcc\u65e5\u9ad8\u5024"
COL_HIGH = "\u7fcc\u65e5\u9ad8\u5024\u7387"
COL_CLOSE_PRICE = "\u7fcc\u65e5\u7d42\u5024"
COL_CLOSE = "\u7fcc\u65e5\u7d42\u5024\u7387"


def normalize_code(value):
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def next_business_day(date):
    jp_holidays = holidays.JP(
        years=[date.year, date.year + 1]
    )

    d = date + timedelta(days=1)

    while d.weekday() >= 5 or d in jp_holidays:
        d += timedelta(days=1)

    return d


def flatten_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    return df


def normalize_index(df):
    index = pd.to_datetime(df.index)

    if index.tz is not None:
        index = index.tz_convert(
            "Asia/Tokyo"
        ).tz_localize(None)

    df = df.copy()
    df.index = index
    return df.sort_index()


def get_value(row, column):
    value = row[column]

    if isinstance(value, pd.Series):
        value = value.iloc[0]

    return float(value)


def pct(value, base):
    if value is None or base is None or base == 0:
        return None

    return (value / base - 1.0) * 100.0


def get_base_price(code, detection_date):
    ticker = f"{code}.T"

    df = yf.download(
        ticker,
        start=(
            detection_date
            - timedelta(days=7)
        ).strftime("%Y-%m-%d"),
        end=(
            detection_date
            + timedelta(days=1)
        ).strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return None

    df = flatten_columns(df)
    df = normalize_index(df)

    target = df[
        df.index.date == detection_date
    ]

    if target.empty:
        return None

    return get_value(
        target.iloc[-1],
        "Close",
    )


def download_daily(code, trade_date):
    ticker = f"{code}.T"

    df = yf.download(
        ticker,
        start=trade_date.strftime("%Y-%m-%d"),
        end=(
            trade_date
            + timedelta(days=1)
        ).strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return None

    df = flatten_columns(df)
    df = normalize_index(df)

    day = df[
        df.index.date == trade_date
    ].copy()

    if day.empty:
        return None

    return day


def analyze_daily_fallback(
    code,
    base_price,
    trade_date,
):
    day = download_daily(
        code,
        trade_date,
    )

    if day is None or day.empty:
        return None

    open_price = get_value(
        day.iloc[0],
        "Open",
    )

    high_price = get_value(
        day.iloc[0],
        "High",
    )

    close_price = get_value(
        day.iloc[-1],
        "Close",
    )

    return {
        COL_OPEN: open_price,
        COL_GU: pct(open_price, base_price),
        COL_0930_PRICE: None,
        COL_0930: None,
        COL_HIGH_PRICE: high_price,
        COL_HIGH: pct(high_price, base_price),
        COL_CLOSE_PRICE: close_price,
        COL_CLOSE: pct(close_price, base_price),
    }


def analyze_stock(code, base_price, trade_date):
    ticker = f"{code}.T"

    df = yf.download(
        ticker,
        start=trade_date.strftime("%Y-%m-%d"),
        end=(
            trade_date
            + timedelta(days=1)
        ).strftime("%Y-%m-%d"),
        interval="5m",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return analyze_daily_fallback(
            code,
            base_price,
            trade_date,
        )

    df = flatten_columns(df)
    df = normalize_index(df)

    day = df[
        df.index.date == trade_date
    ].copy()

    if day.empty:
        return None

    open_price = get_value(
        day.iloc[0],
        "Open",
    )

    high_price = float(
        day["High"].astype(float).max()
    )

    close_price = get_value(
        day.iloc[-1],
        "Close",
    )

    morning = day[
        day.index.time
        <= pd.Timestamp("09:30").time()
    ]

    if morning.empty:
        price_0930 = None
    else:
        price_0930 = get_value(
            morning.iloc[-1],
            "Close",
        )

    return {
        COL_OPEN: open_price,
        COL_GU: pct(open_price, base_price),
        COL_0930_PRICE: price_0930,
        COL_0930: pct(price_0930, base_price),
        COL_HIGH_PRICE: high_price,
        COL_HIGH: pct(high_price, base_price),
        COL_CLOSE_PRICE: close_price,
        COL_CLOSE: pct(close_price, base_price),
    }


def load_candidates():
    rows = []

    pattern = "*_earnings_catalyst_ver1_top3.csv"

    for path in sorted(ANALYSIS.glob(pattern)):
        date_str = path.name[:10]

        try:
            detection_date = pd.Timestamp(
                date_str
            ).date()
        except Exception:
            continue

        if detection_date < FORWARD_START:
            continue

        try:
            df = pd.read_csv(
                path,
                dtype=str,
            )
        except pd.errors.EmptyDataError:
            continue

        if df.empty:
            continue

        for rank, (_, row) in enumerate(
            df.iterrows(),
            start=1,
        ):
            rows.append(
                {
                    "DetectionDate": date_str,
                    "Code": normalize_code(
                        row.get("Code", "")
                    ),
                    "Name": row.get("Name", ""),
                    "Rank": rank,
                    "EarningsType": row.get(
                        "EarningsType",
                        "",
                    ),
                    "Rating": row.get(
                        "Rating",
                        "",
                    ),
                    "HypothesisRank": row.get(
                        "HypothesisRank",
                        "",
                    ),
                    "WarningFlag": row.get(
                        "WarningFlag",
                        "",
                    ),
                }
            )

    return pd.DataFrame(rows)


def print_metric(df, label, column):
    values = pd.to_numeric(
        df[column],
        errors="coerce",
    ).dropna()

    if values.empty:
        return

    print(
        f"{label:<6}",
        f"mean={values.mean():7.2f}%",
        f"median={values.median():7.2f}%",
        f"plus={(values > 0).mean() * 100:6.1f}%",
    )


def print_summary(df):
    print()
    print("=" * 78)
    print("EARNINGS CATALYST FORWARD")
    print("=" * 78)

    print("Forward rows :", len(df))

    valid = df[
        pd.to_numeric(
            df[COL_CLOSE],
            errors="coerce",
        ).notna()
    ].copy()

    print("Valid results:", len(valid))

    if valid.empty:
        return

    print()

    print_metric(
        valid,
        "GU",
        COL_GU,
    )
    print_metric(
        valid,
        "09:30",
        COL_0930,
    )
    print_metric(
        valid,
        "HIGH",
        COL_HIGH,
    )
    print_metric(
        valid,
        "CLOSE",
        COL_CLOSE,
    )

    high = pd.to_numeric(
        valid[COL_HIGH],
        errors="coerce",
    ).dropna()

    close = pd.to_numeric(
        valid[COL_CLOSE],
        errors="coerce",
    ).dropna()

    print()
    print(
        "HIGH thresholds:",
        f"+3={(high >= 3).mean() * 100:5.1f}%",
        f"+5={(high >= 5).mean() * 100:5.1f}%",
        f"+10={(high >= 10).mean() * 100:5.1f}%",
    )

    print(
        "Close positive:",
        f"{(close > 0).mean() * 100:.1f}%",
    )

    # --------------------------------------------------
    # Tradable return from next-day open
    # --------------------------------------------------

    open_price = pd.to_numeric(
        valid[COL_OPEN],
        errors="coerce",
    )

    high_price = pd.to_numeric(
        valid[COL_HIGH_PRICE],
        errors="coerce",
    )

    close_price = pd.to_numeric(
        valid[COL_CLOSE_PRICE],
        errors="coerce",
    )

    open_to_high = (
        high_price / open_price - 1.0
    ) * 100.0

    open_to_close = (
        close_price / open_price - 1.0
    ) * 100.0

    open_to_high = (
        open_to_high
        .replace(
            [float("inf"), float("-inf")],
            pd.NA,
        )
        .dropna()
    )

    open_to_close = (
        open_to_close
        .replace(
            [float("inf"), float("-inf")],
            pd.NA,
        )
        .dropna()
    )

    print()
    print("-" * 78)
    print("NEXT-OPEN TRADE VIEW")
    print("-" * 78)

    print(
        "Open->HIGH :",
        f"N={len(open_to_high)}",
        f"mean={open_to_high.mean():7.2f}%",
        f"median={open_to_high.median():7.2f}%",
    )

    print(
        "Open->HIGH thresholds:",
        f"+3={(open_to_high >= 3).mean() * 100:5.1f}%",
        f"+5={(open_to_high >= 5).mean() * 100:5.1f}%",
        f"+10={(open_to_high >= 10).mean() * 100:5.1f}%",
    )

    print(
        "Open->CLOSE:",
        f"N={len(open_to_close)}",
        f"mean={open_to_close.mean():7.2f}%",
        f"median={open_to_close.median():7.2f}%",
        f"plus={(open_to_close > 0).mean() * 100:5.1f}%",
    )


def main():
    TRACKING.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidates = load_candidates()

    if candidates.empty:
        print("No forward candidates.")
        return

    today = pd.Timestamp.now(
        tz="Asia/Tokyo"
    ).date()

    existing = {}

    if OUT_PATH.exists():
        try:
            old_df = pd.read_csv(
                OUT_PATH,
                dtype=str,
            )

            for _, old_row in old_df.iterrows():
                key = (
                    str(
                        old_row.get(
                            "DetectionDate",
                            "",
                        )
                    ),
                    normalize_code(
                        old_row.get(
                            "Code",
                            "",
                        )
                    ),
                )

                if (
                    old_row.get(
                        "DataStatus",
                        "",
                    ) == "OK"
                ):
                    existing[key] = (
                        old_row.to_dict()
                    )

        except Exception as e:
            print(
                "Existing tracking read warning:",
                repr(e),
            )

    results = []

    print("=" * 78)
    print("EARNINGS CATALYST FORWARD UPDATE")
    print("=" * 78)
    print(
        "Forward start :",
        FORWARD_START,
    )
    print(
        "Candidates    :",
        len(candidates),
    )
    print()

    for _, row in candidates.iterrows():
        key = (
            str(row["DetectionDate"]),
            normalize_code(
                row["Code"]
            ),
        )

        if key in existing:
            output = existing[key]
            results.append(output)

            print(
                row["DetectionDate"],
                row["Code"],
                ": CACHED OK",
            )
            continue

        detection_date = pd.Timestamp(
            row["DetectionDate"]
        ).date()

        trade_date = next_business_day(
            detection_date
        )

        output = row.to_dict()
        output["TradeDate"] = str(
            trade_date
        )
        output["BasePrice"] = None

        for col in [
            COL_OPEN,
            COL_GU,
            COL_0930_PRICE,
            COL_0930,
            COL_HIGH_PRICE,
            COL_HIGH,
            COL_CLOSE_PRICE,
            COL_CLOSE,
        ]:
            output[col] = None

        if trade_date > today:
            output["DataStatus"] = "WAIT"
            results.append(output)
            continue

        code = row["Code"]

        print(
            row["DetectionDate"],
            code,
            end=" : ",
        )

        try:
            base_price = get_base_price(
                code,
                detection_date,
            )

            if base_price is None:
                output["DataStatus"] = "NO_BASE"
                print("NO BASE")
                results.append(output)
                continue

            output["BasePrice"] = base_price

            result = analyze_stock(
                code,
                base_price,
                trade_date,
            )

            if result is None:
                output["DataStatus"] = "NO_INTRADAY"
                print("NO INTRADAY")
                results.append(output)
                continue

            output.update(result)
            output["DataStatus"] = "OK"

            value_0930 = result[
                COL_0930
            ]

            if value_0930 is None:
                text_0930 = "N/A"
            else:
                text_0930 = (
                    f"{value_0930:.2f}%"
                )

            print(
                "OK",
                f"GU={result[COL_GU]:.2f}%",
                f"09:30={text_0930}",
                f"High={result[COL_HIGH]:.2f}%",
                f"Close={result[COL_CLOSE]:.2f}%",
            )

        except Exception as e:
            output["DataStatus"] = "ERROR"
            print(
                "ERROR",
                repr(e),
            )

        results.append(output)

    result_df = pd.DataFrame(
        results
    )

    result_df.to_csv(
        OUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print_summary(result_df)

    print()
    print(
        "Saved :",
        OUT_PATH,
    )


if __name__ == "__main__":
    main()
