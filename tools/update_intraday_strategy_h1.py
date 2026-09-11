from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


TRACKING_PATH = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def parse_snapshot_time(value):
    text = str(value).strip()

    try:
        return datetime.strptime(
            text,
            "%H:%M:%S",
        )
    except ValueError:
        try:
            return datetime.strptime(
                text,
                "%H:%M",
            )
        except ValueError:
            return None


def evaluation_start(date_text, time_text):
    t = parse_snapshot_time(time_text)

    if t is None:
        return None

    base = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    current = base.replace(
        hour=t.hour,
        minute=t.minute,
        second=t.second,
    )

    # Always start from the NEXT 5-minute bar.
    minute_floor = (
        current.minute // 5
    ) * 5

    bar = current.replace(
        minute=minute_floor,
        second=0,
        microsecond=0,
    )

    bar += timedelta(minutes=5)

    return bar


def can_finalize(date_text):
    try:
        detection_date = datetime.strptime(
            date_text,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return False

    now = datetime.now()
    today = now.date()

    if detection_date < today:
        return True

    if detection_date > today:
        return False

    close_time = now.replace(
        hour=MARKET_CLOSE_HOUR,
        minute=MARKET_CLOSE_MINUTE,
        second=0,
        microsecond=0,
    )

    return now >= close_time


def download_5m(code, date_text):
    ticker = f"{code}.T"

    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    end = start + timedelta(days=1)

    try:
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="5m",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:
        print(
            f"DOWNLOAD ERROR {code} "
            f"{date_text} : {exc}"
        )
        return None

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

    needed = [
        "Open",
        "High",
        "Low",
        "Close",
    ]

    if not all(
        col in df.columns
        for col in needed
    ):
        return None

    idx = pd.to_datetime(df.index)

    try:
        if idx.tz is not None:
            idx = idx.tz_convert(
                "Asia/Tokyo"
            ).tz_localize(None)
    except Exception:
        try:
            idx = idx.tz_localize(None)
        except Exception:
            pass

    df = df.copy()
    df.index = idx

    return df


def time_text(ts):
    if ts is None:
        return ""

    return pd.Timestamp(ts).strftime(
        "%H:%M"
    )


def analyze_row(row, bars):
    price = pd.to_numeric(
        row["SnapshotPrice"],
        errors="coerce",
    )

    if pd.isna(price) or price <= 0:
        return None

    start = evaluation_start(
        str(row["DetectionDate"]),
        str(row["SnapshotTime"]),
    )

    if start is None:
        return None

    work = bars[
        bars.index >= start
    ].copy()

    if work.empty:
        return None

    high = pd.to_numeric(
        work["High"],
        errors="coerce",
    )

    low = pd.to_numeric(
        work["Low"],
        errors="coerce",
    )

    close = pd.to_numeric(
        work["Close"],
        errors="coerce",
    )

    valid = (
        high.notna()
        & low.notna()
        & close.notna()
    )

    work = work[valid].copy()

    if work.empty:
        return None

    high = pd.to_numeric(
        work["High"],
        errors="coerce",
    )

    low = pd.to_numeric(
        work["Low"],
        errors="coerce",
    )

    close = pd.to_numeric(
        work["Close"],
        errors="coerce",
    )

    take_price = price * 1.10
    stop_price = price * 0.97

    take_hits = work[
        high >= take_price
    ]

    stop_hits = work[
        low <= stop_price
    ]

    take_time = (
        take_hits.index[0]
        if not take_hits.empty
        else None
    )

    stop_time = (
        stop_hits.index[0]
        if not stop_hits.empty
        else None
    )

    if (
        take_time is not None
        and stop_time is not None
    ):
        if take_time < stop_time:
            exit_type = "TAKE"
            return_pct = 10.0

        elif stop_time < take_time:
            exit_type = "STOP"
            return_pct = -3.0

        else:
            exit_type = "SAME_BAR"
            return_pct = pd.NA

    elif take_time is not None:
        exit_type = "TAKE"
        return_pct = 10.0

    elif stop_time is not None:
        exit_type = "STOP"
        return_pct = -3.0

    else:
        exit_type = "CLOSE"

        last_close = float(
            close.iloc[-1]
        )

        return_pct = (
            last_close / price - 1
        ) * 100

    max_high_pct = (
        float(high.max()) / price - 1
    ) * 100

    min_low_pct = (
        float(low.min()) / price - 1
    ) * 100

    last_close = float(
        close.iloc[-1]
    )

    close_pct = (
        last_close / price - 1
    ) * 100

    return {
        "HitPlus10Time": time_text(
            take_time
        ),
        "HitMinus3Time": time_text(
            stop_time
        ),
        "ExitType": exit_type,
        "ReturnPct": return_pct,
        "MaxHighPct": max_high_pct,
        "MinLowPct": min_low_pct,
        "ClosePct": close_pct,
    }


def main():
    if not TRACKING_PATH.exists():
        print(
            f"Not found : {TRACKING_PATH}"
        )
        return

    df = pd.read_csv(
        TRACKING_PATH,
        dtype={
            "Code": str,
        },
    )

    # Columns that start empty are otherwise inferred as float.
    # Force text result columns to object/string-compatible dtype.
    for col in [
        "HitPlus10Time",
        "HitMinus3Time",
        "ExitType",
    ]:
        if col in df.columns:
            df[col] = df[col].astype("object")

    # Outcome columns are numeric.
    for col in [
        "ReturnPct",
        "MaxHighPct",
        "MinLowPct",
        "ClosePct",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    if df.empty:
        print("Tracking is empty.")
        return

    df["Code"] = (
        df["Code"]
        .map(normalize_code)
    )

    updated = 0
    skipped = 0
    errors = 0

    cache = {}

    for idx, row in df.iterrows():

        exit_type = str(
            row.get(
                "ExitType",
                "",
            )
        ).strip()

        if (
            exit_type
            and exit_type.lower()
            != "nan"
        ):
            skipped += 1
            continue

        date_text = str(
            row["DetectionDate"]
        ).strip()

        code = normalize_code(
            row["Code"]
        )

        # Do not finalize today's data
        # until market close.
        if not can_finalize(date_text):
            skipped += 1
            continue

        key = (
            code,
            date_text,
        )

        if key not in cache:
            cache[key] = download_5m(
                code,
                date_text,
            )

        bars = cache[key]

        if bars is None:
            print(
                f"NO DATA : "
                f"{date_text} {code}"
            )
            errors += 1
            continue

        result = analyze_row(
            row,
            bars,
        )

        if result is None:
            print(
                f"NO BARS : "
                f"{date_text} {code}"
            )
            errors += 1
            continue

        for col, value in result.items():
            df.at[
                idx,
                col,
            ] = value

        updated += 1

        print(
            f"{date_text} "
            f"{code} "
            f"{result['ExitType']} "
            f"{result['ReturnPct']}"
        )

    df.to_csv(
        TRACKING_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 60)
    print("H1 RESULT UPDATE")
    print("=" * 60)
    print(f"Updated : {updated}")
    print(f"Skipped : {skipped}")
    print(f"Errors  : {errors}")

    development = df[
        df["DataType"]
        == "DEVELOPMENT"
    ]

    forward = df[
        df["DataType"]
        == "FORWARD"
    ]

    print()
    print(
        f"Development : "
        f"{len(development)}"
    )
    print(
        f"Forward     : "
        f"{len(forward)}"
    )

    if not forward.empty:
        completed = forward[
            forward["ExitType"]
            .notna()
            & (
                forward["ExitType"]
                .astype(str)
                .str.len()
                > 0
            )
        ]

        print(
            f"Forward done: "
            f"{len(completed)}"
        )

        if not completed.empty:
            ret = pd.to_numeric(
                completed["ReturnPct"],
                errors="coerce",
            ).dropna()

            print(
                f"Mean return : "
                f"{ret.mean():.2f}%"
            )
            print(
                f"Total return: "
                f"{ret.sum():.2f}%"
            )


if __name__ == "__main__":
    main()
