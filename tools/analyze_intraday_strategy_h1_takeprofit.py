from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


# ============================================================
# H1 09:32 ENTRY - TAKE PROFIT COMPARISON
# ============================================================

SOURCE_PATH = Path(
    "data/analysis/intraday_strategy_h1_0931_band.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/intraday_strategy_h1_takeprofit.csv"
)

SUMMARY_PATH = Path(
    "data/analysis/intraday_strategy_h1_takeprofit_summary.csv"
)

LOWER_LIMIT = -3.0
UPPER_LIMIT = 1.0

STOP_PCT = -3.0

TAKE_LEVELS = [
    3.0,
    5.0,
    7.0,
    10.0,
]


# ============================================================
# Utility
# ============================================================

def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def download_1m(code, date_text):
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
            interval="1m",
            progress=False,
            auto_adjust=False,
            threads=False,
        )

    except Exception as exc:
        print(
            f"DOWNLOAD ERROR "
            f"{date_text} {code} : {exc}"
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


def get_entry_time(date_text):
    return datetime.strptime(
        f"{date_text} 09:32",
        "%Y-%m-%d %H:%M",
    )


def time_text(value):
    if value is None:
        return ""

    return pd.Timestamp(value).strftime(
        "%H:%M"
    )


# ============================================================
# Simulation
# ============================================================

def simulate_take(
    bars,
    date_text,
    take_pct,
):
    entry_time = get_entry_time(
        date_text
    )

    work = bars[
        bars.index >= entry_time
    ].copy()

    if work.empty:
        return None

    first = work.iloc[0]

    entry_price = pd.to_numeric(
        first["Open"],
        errors="coerce",
    )

    if (
        pd.isna(entry_price)
        or entry_price <= 0
    ):
        return None

    take_price = (
        entry_price
        * (1 + take_pct / 100)
    )

    stop_price = (
        entry_price
        * (1 + STOP_PCT / 100)
    )

    take_time = None
    stop_time = None
    exit_type = None
    return_pct = None
    ambiguous_time = None

    for ts, bar in work.iterrows():
        high = pd.to_numeric(
            bar["High"],
            errors="coerce",
        )

        low = pd.to_numeric(
            bar["Low"],
            errors="coerce",
        )

        if pd.isna(high) or pd.isna(low):
            continue

        hit_take = (
            high >= take_price
        )

        hit_stop = (
            low <= stop_price
        )

        # Same 1-minute bar hits both levels.
        # OHLC cannot tell which happened first.
        if hit_take and hit_stop:
            exit_type = "AMBIG"
            ambiguous_time = ts
            break

        if hit_take:
            take_time = ts
            exit_type = "TAKE"
            return_pct = take_pct
            break

        if hit_stop:
            stop_time = ts
            exit_type = "STOP"
            return_pct = STOP_PCT
            break

    if exit_type is None:
        close_series = pd.to_numeric(
            work["Close"],
            errors="coerce",
        ).dropna()

        if close_series.empty:
            return None

        last_close = float(
            close_series.iloc[-1]
        )

        exit_type = "CLOSE"

        return_pct = (
            last_close / entry_price - 1
        ) * 100

    high_series = pd.to_numeric(
        work["High"],
        errors="coerce",
    ).dropna()

    low_series = pd.to_numeric(
        work["Low"],
        errors="coerce",
    ).dropna()

    mfe = pd.NA
    mae = pd.NA

    if not high_series.empty:
        mfe = (
            float(high_series.max())
            / entry_price
            - 1
        ) * 100

    if not low_series.empty:
        mae = (
            float(low_series.min())
            / entry_price
            - 1
        ) * 100

    return {
        "EntryPrice": entry_price,
        "TakePct": take_pct,
        "StopPct": STOP_PCT,
        "ExitType": exit_type,
        "ReturnPct": return_pct,
        "TakeTime": time_text(
            take_time
        ),
        "StopTime": time_text(
            stop_time
        ),
        "AmbiguousTime": time_text(
            ambiguous_time
        ),
        "MFE": mfe,
        "MAE": mae,
    }


# ============================================================
# Summary
# ============================================================

def make_summary(result_df):
    rows = []

    for take_pct in TAKE_LEVELS:
        x = result_df[
            result_df["TakePct"]
            == take_pct
        ].copy()

        valid = x[
            x["ReturnPct"].notna()
        ].copy()

        trades = len(x)
        valid_count = len(valid)

        mean_return = (
            valid["ReturnPct"].mean()
            if valid_count
            else pd.NA
        )

        median_return = (
            valid["ReturnPct"].median()
            if valid_count
            else pd.NA
        )

        total_return = (
            valid["ReturnPct"].sum()
            if valid_count
            else pd.NA
        )

        win_rate = (
            (
                valid["ReturnPct"] > 0
            ).mean() * 100
            if valid_count
            else pd.NA
        )

        counts = (
            x["ExitType"]
            .value_counts()
            .to_dict()
        )

        rows.append(
            {
                "TakePct": take_pct,
                "Trades": trades,
                "Valid": valid_count,
                "MeanReturn": mean_return,
                "Median": median_return,
                "WinRate": win_rate,
                "TotalReturn": total_return,
                "TAKE": counts.get(
                    "TAKE",
                    0,
                ),
                "STOP": counts.get(
                    "STOP",
                    0,
                ),
                "CLOSE": counts.get(
                    "CLOSE",
                    0,
                ),
                "AMBIG": counts.get(
                    "AMBIG",
                    0,
                ),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# Main
# ============================================================

def main():
    print(
        "=" * 78
    )
    print(
        "H1 TAKE PROFIT ANALYSIS"
    )
    print(
        "=" * 78
    )

    if not SOURCE_PATH.exists():
        print(
            f"NOT FOUND : {SOURCE_PATH}"
        )
        return

    source = pd.read_csv(
        SOURCE_PATH,
        low_memory=False,
    )

    required = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Close0931Pct",
        "CxV",
    ]

    missing = [
        col
        for col in required
        if col not in source.columns
    ]

    if missing:
        print(
            f"MISSING COLUMNS : {missing}"
        )
        return

    source["Close0931Pct"] = (
        pd.to_numeric(
            source["Close0931Pct"],
            errors="coerce",
        )
    )

    target = source[
        (
            source["Close0931Pct"]
            >= LOWER_LIMIT
        )
        & (
            source["Close0931Pct"]
            < UPPER_LIMIT
        )
    ].copy()

    target = target.drop_duplicates(
        subset=[
            "DetectionDate",
            "Code",
        ]
    )

    print(
        f"Target rows : {len(target)}"
    )
    print(
        "Entry       : 09:32 OPEN"
    )
    print(
        f"Band        : "
        f"{LOWER_LIMIT:+.1f}% "
        f"<= Close0931Pct "
        f"< {UPPER_LIMIT:+.1f}%"
    )
    print(
        f"Initial stop: {STOP_PCT:+.1f}%"
    )
    print(
        "Take levels : "
        + ", ".join(
            f"+{x:.0f}%"
            for x in TAKE_LEVELS
        )
    )

    results = []

    cache = {}

    for _, row in target.iterrows():
        date_text = str(
            row["DetectionDate"]
        )

        code = normalize_code(
            row["Code"]
        )

        key = (
            date_text,
            code,
        )

        if key not in cache:
            cache[key] = download_1m(
                code,
                date_text,
            )

        bars = cache[key]

        if bars is None:
            print(
                f"NO DATA : "
                f"{date_text} {code}"
            )
            continue

        for take_pct in TAKE_LEVELS:
            result = simulate_take(
                bars,
                date_text,
                take_pct,
            )

            if result is None:
                continue

            item = {
                "DetectionDate":
                    date_text,
                "Code":
                    code,
                "Name":
                    row["Name"],
                "Rank":
                    row["Rank"],
                "Close0931Pct":
                    row["Close0931Pct"],
                "CxV":
                    row["CxV"],
            }

            item.update(
                result
            )

            results.append(
                item
            )

    if not results:
        print(
            "NO RESULTS"
        )
        return

    result_df = pd.DataFrame(
        results
    )

    summary = make_summary(
        result_df
    )

    print()
    print(
        "=" * 78
    )
    print(
        "TAKE PROFIT COMPARISON"
    )
    print(
        "=" * 78
    )

    show = summary.copy()

    for col in [
        "MeanReturn",
        "Median",
        "WinRate",
        "TotalReturn",
    ]:
        show[col] = show[col].map(
            lambda x:
                ""
                if pd.isna(x)
                else f"{x:.2f}%"
        )

    print(
        show.to_string(
            index=False
        )
    )

    print()
    print(
        "=" * 78
    )
    print(
        "STOCK DETAIL"
    )
    print(
        "=" * 78
    )

    pivot = result_df.pivot_table(
        index=[
            "DetectionDate",
            "Code",
            "Name",
            "Rank",
            "Close0931Pct",
            "CxV",
        ],
        columns="TakePct",
        values="ReturnPct",
        aggfunc="first",
    ).reset_index()

    rename = {}

    for take_pct in TAKE_LEVELS:
        if take_pct in pivot.columns:
            rename[take_pct] = (
                f"TAKE+{take_pct:.0f}"
            )

    pivot = pivot.rename(
        columns=rename
    )

    print(
        pivot.to_string(
            index=False
        )
    )

    ambiguous = result_df[
        result_df["ExitType"]
        == "AMBIG"
    ].copy()

    if not ambiguous.empty:
        print()
        print(
            "=" * 78
        )
        print(
            "AMBIGUOUS 1-MINUTE BARS"
        )
        print(
            "=" * 78
        )

        cols = [
            "DetectionDate",
            "Code",
            "Name",
            "TakePct",
            "EntryPrice",
            "AmbiguousTime",
            "MFE",
            "MAE",
        ]

        print(
            ambiguous[
                cols
            ].to_string(
                index=False
            )
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )
    print(
        f"Saved : {SUMMARY_PATH}"
    )


if __name__ == "__main__":
    main()