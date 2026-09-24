from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


# ============================================================
# H1 +10% AFTER-TAKE ANALYSIS
#
# Entry rule:
#   09:31 close filter
#   -3.0% <= Close0931Pct < +1.0%
#   Entry = 09:32 OPEN
#
# Purpose:
#   Analyze price action AFTER first +10% touch.
# ============================================================


SIGNAL_PATH = Path(
    "data/analysis/intraday_strategy_h1_0931_candle.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/intraday_strategy_h1_after_take10.csv"
)

LOWER_LIMIT = -3.0
UPPER_LIMIT = 1.0

TAKE_PCT = 10.0

ENTRY_HOUR = 9
ENTRY_MINUTE = 32


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
            idx = (
                idx
                .tz_convert("Asia/Tokyo")
                .tz_localize(None)
            )
    except Exception:
        try:
            idx = idx.tz_localize(None)
        except Exception:
            pass

    df = df.copy()
    df.index = idx

    for col in needed:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    return df


def pct(price, base):
    return (
        float(price) / float(base) - 1
    ) * 100


def time_text(ts):
    if ts is None:
        return ""

    return pd.Timestamp(ts).strftime(
        "%H:%M"
    )


def analyze_stock(row, bars):
    date_text = str(
        row["DetectionDate"]
    )

    base_date = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    entry_time = base_date.replace(
        hour=ENTRY_HOUR,
        minute=ENTRY_MINUTE,
        second=0,
        microsecond=0,
    )

    work = bars[
        bars.index >= entry_time
    ].copy()

    if work.empty:
        return None

    # --------------------------------------------------------
    # Entry = 09:32 OPEN
    # --------------------------------------------------------

    first_bar = work.iloc[0]

    entry_price = float(
        first_bar["Open"]
    )

    if entry_price <= 0:
        return None

    take_price = (
        entry_price
        * (1 + TAKE_PCT / 100)
    )

    # --------------------------------------------------------
    # First +10% touch
    # --------------------------------------------------------

    take_hits = work[
        work["High"] >= take_price
    ]

    if take_hits.empty:
        return None

    take_time = take_hits.index[0]

    # Include the +10% touch bar.
    after = work[
        work.index >= take_time
    ].copy()

    if after.empty:
        return None

    # --------------------------------------------------------
    # Whole-day MFE
    # --------------------------------------------------------

    max_high = float(
        work["High"].max()
    )

    max_high_time = work[
        work["High"] == max_high
    ].index[0]

    mfe_pct = pct(
        max_high,
        entry_price,
    )

    # --------------------------------------------------------
    # After +10% touch
    # --------------------------------------------------------

    after_max_high = float(
        after["High"].max()
    )

    after_max_time = after[
        after["High"] == after_max_high
    ].index[0]

    after_min_low = float(
        after["Low"].min()
    )

    after_min_time = after[
        after["Low"] == after_min_low
    ].index[0]

    after_max_pct = pct(
        after_max_high,
        entry_price,
    )

    after_min_pct = pct(
        after_min_low,
        entry_price,
    )

    # Extra upside measured from the +10% level itself.
    extra_from_take_pct = (
        after_max_high / take_price - 1
    ) * 100

    # Maximum decline from the +10% take price.
    min_from_take_pct = (
        after_min_low / take_price - 1
    ) * 100

    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    close_price = float(
        work["Close"].iloc[-1]
    )

    close_pct = pct(
        close_price,
        entry_price,
    )

    close_from_take_pct = (
        close_price / take_price - 1
    ) * 100

    # How many percentage points of the peak were given back
    # by the close.
    peak_to_close_pp = (
        mfe_pct - close_pct
    )

    # --------------------------------------------------------
    # Drawdown after +10%
    #
    # Calculate maximum decline from the running peak after
    # the +10% touch.
    # --------------------------------------------------------

    running_peak = None
    max_drawdown_pct = 0.0
    max_drawdown_time = None

    for ts, bar in after.iterrows():
        high = float(
            bar["High"]
        )

        low = float(
            bar["Low"]
        )

        if (
            running_peak is None
            or high > running_peak
        ):
            running_peak = high

        if (
            running_peak is None
            or running_peak <= 0
        ):
            continue

        drawdown_pct = (
            low / running_peak - 1
        ) * 100

        if drawdown_pct < max_drawdown_pct:
            max_drawdown_pct = (
                drawdown_pct
            )
            max_drawdown_time = ts

    return {
        "DetectionDate":
            date_text,

        "Code":
            normalize_code(
                row["Code"]
            ),

        "Name":
            row["Name"],

        "Rank":
            row["Rank"],

        "Change":
            row["Change"],

        "VolumeRatio":
            row.get(
                "VolumeRatio",
                pd.NA,
            ),

        "CxV":
            row["CxV"],

        "Close0931Pct":
            row["Close0931Pct"],

        "Entry0932Price":
            entry_price,

        "Take10Price":
            take_price,

        "HitPlus10Time":
            time_text(
                take_time
            ),

        "MFE":
            mfe_pct,

        "MFETime":
            time_text(
                max_high_time
            ),

        "AfterTakeMaxPct":
            after_max_pct,

        "AfterTakeMaxTime":
            time_text(
                after_max_time
            ),

        "ExtraFromTake10Pct":
            extra_from_take_pct,

        "AfterTakeMinPct":
            after_min_pct,

        "AfterTakeMinTime":
            time_text(
                after_min_time
            ),

        "MinFromTake10Pct":
            min_from_take_pct,

        "MaxDrawdownAfterTakePct":
            max_drawdown_pct,

        "MaxDrawdownTime":
            time_text(
                max_drawdown_time
            ),

        "ClosePrice":
            close_price,

        "ClosePct":
            close_pct,

        "CloseFromTake10Pct":
            close_from_take_pct,

        "PeakToCloseGivebackPP":
            peak_to_close_pp,
    }


def main():

    print(
        "=" * 78
    )

    print(
        "H1 AFTER +10% ANALYSIS"
    )

    print(
        "=" * 78
    )

    if not SIGNAL_PATH.exists():
        print(
            f"NOT FOUND : {SIGNAL_PATH}"
        )
        return

    df = pd.read_csv(
        SIGNAL_PATH,
        low_memory=False,
    )

    required = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Change",
        "CxV",
        "Close0931Pct",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        print(
            f"MISSING COLUMNS : {missing}"
        )
        return

    df["Close0931Pct"] = (
        pd.to_numeric(
            df["Close0931Pct"],
            errors="coerce",
        )
    )

    # --------------------------------------------------------
    # H1 improved entry band
    # --------------------------------------------------------

    target = df[
        (
            df["Close0931Pct"]
            >= LOWER_LIMIT
        )
        &
        (
            df["Close0931Pct"]
            < UPPER_LIMIT
        )
    ].copy()

    print(
        f"Target rows : {len(target)}"
    )

    print(
        "Entry       : 09:32 OPEN"
    )

    print(
        "Band        : "
        f"{LOWER_LIMIT:+.1f}% "
        "<= Close0931Pct < "
        f"{UPPER_LIMIT:+.1f}%"
    )

    print(
        f"Take level  : +{TAKE_PCT:.1f}%"
    )

    results = []

    for _, row in target.iterrows():

        code = normalize_code(
            row["Code"]
        )

        date_text = str(
            row["DetectionDate"]
        )

        bars = download_1m(
            code,
            date_text,
        )

        if bars is None:
            print(
                f"NO DATA : "
                f"{date_text} {code}"
            )
            continue

        result = analyze_stock(
            row,
            bars,
        )

        # Only +10% reached stocks.
        if result is not None:
            results.append(
                result
            )

    result_df = pd.DataFrame(
        results
    )

    print()

    print(
        "=" * 78
    )

    print(
        "+10% REACHED"
    )

    print(
        "=" * 78
    )

    print(
        f"Reached : "
        f"{len(result_df)} / "
        f"{len(target)}"
    )

    if result_df.empty:
        print(
            "No +10% stocks."
        )
        return

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()

    print(
        "=" * 78
    )

    print(
        "AFTER +10% SUMMARY"
    )

    print(
        "=" * 78
    )

    print(
        f"MFE mean              : "
        f"{result_df['MFE'].mean():.2f}%"
    )

    print(
        f"MFE median            : "
        f"{result_df['MFE'].median():.2f}%"
    )

    print(
        f"Extra after +10 mean  : "
        f"{result_df['ExtraFromTake10Pct'].mean():.2f}%"
    )

    print(
        f"Extra after +10 median: "
        f"{result_df['ExtraFromTake10Pct'].median():.2f}%"
    )

    print(
        f"Close mean            : "
        f"{result_df['ClosePct'].mean():.2f}%"
    )

    print(
        f"Close median          : "
        f"{result_df['ClosePct'].median():.2f}%"
    )

    print(
        f"Max DD after +10 mean : "
        f"{result_df['MaxDrawdownAfterTakePct'].mean():.2f}%"
    )

    print(
        f"Max DD after +10 med. : "
        f"{result_df['MaxDrawdownAfterTakePct'].median():.2f}%"
    )

    # --------------------------------------------------------
    # Detail
    # --------------------------------------------------------

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

    detail_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Close0931Pct",
        "CxV",
        "Entry0932Price",
        "HitPlus10Time",
        "MFE",
        "MFETime",
        "ExtraFromTake10Pct",
        "MaxDrawdownAfterTakePct",
        "ClosePct",
        "PeakToCloseGivebackPP",
    ]

    print(
        result_df[
            detail_cols
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()

    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()