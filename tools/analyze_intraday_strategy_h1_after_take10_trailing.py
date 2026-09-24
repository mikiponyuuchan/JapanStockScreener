from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


# ============================================================
# H1 AFTER +10% TRAILING ANALYSIS
#
# H1 candidate rule:
#   09:31 filter
#   -3.0% <= Close0931Pct < +1.0%
#   Entry = 09:32 OPEN
#   Initial stop = -3%
#
# Compare:
#   BASE       : 100% exit at +10%
#   HALF_TRAIL : 50% exit at +10%
#                remaining 50% trailing from post-+10 peak
#
# Trailing widths:
#   -2%, -3%, -4%, -5%
#
# IMPORTANT:
#   Trailing becomes active only AFTER the first +10% touch bar.
#   This avoids assuming the intrabar order inside the 1-minute
#   bar in which +10% is first reached.
# ============================================================


SOURCE_PATH = Path(
    "data/analysis/intraday_strategy_h1_after_take10.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_after_take10_trailing.csv"
)

SUMMARY_PATH = Path(
    "data/analysis/"
    "intraday_strategy_h1_after_take10_trailing_summary.csv"
)


TAKE_PCT = 10.0

TRAILINGS = {
    "TRAIL2": 2.0,
    "TRAIL3": 3.0,
    "TRAIL4": 4.0,
    "TRAIL5": 5.0,
}


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

    idx = pd.to_datetime(
        df.index
    )

    try:
        if idx.tz is not None:
            idx = (
                idx
                .tz_convert("Asia/Tokyo")
                .tz_localize(None)
            )
    except Exception:
        try:
            idx = idx.tz_localize(
                None
            )
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
        subset=needed
    )

    return df


def pct(price, entry):
    return (
        float(price)
        / float(entry)
        - 1
    ) * 100


def time_text(ts):
    if ts is None:
        return ""

    return pd.Timestamp(
        ts
    ).strftime("%H:%M")


def analyze_trailing(
    bars,
    entry_price,
    take_time,
    trail_pct,
):
    """
    Remaining 50% after +10%.

    Trailing starts from the NEXT 1-minute bar after
    the first +10% touch.

    We initialize the running peak using the high of
    the +10% touch bar.

    If a later bar trades through the trailing stop,
    exit at the trailing stop price.

    If no trailing stop is hit, exit at day's last close.
    """

    take_bar = bars.loc[
        take_time
    ]

    # In case duplicate timestamps somehow exist.
    if isinstance(
        take_bar,
        pd.DataFrame,
    ):
        take_bar = take_bar.iloc[0]

    running_peak = float(
        take_bar["High"]
    )

    after = bars[
        bars.index > take_time
    ].copy()

    # +10% was reached in the final available bar.
    if after.empty:
        last_close = float(
            bars["Close"].iloc[-1]
        )

        return {
            "TrailExitType": "CLOSE",
            "TrailExitTime":
                time_text(
                    bars.index[-1]
                ),
            "TrailExitPrice":
                last_close,
            "TrailReturnPct":
                pct(
                    last_close,
                    entry_price,
                ),
            "TrailPeakPct":
                pct(
                    running_peak,
                    entry_price,
                ),
        }

    for ts, bar in after.iterrows():

        high = float(
            bar["High"]
        )

        low = float(
            bar["Low"]
        )

        # Conservative 1-minute-bar handling:
        #
        # First test the stop based on the peak known
        # BEFORE this bar.
        #
        # Only if the stop was not hit do we allow this
        # bar's high to raise the running peak.
        #
        # This avoids assuming that HIGH occurred before
        # LOW inside the same 1-minute bar.

        stop_price = (
            running_peak
            * (1 - trail_pct / 100)
        )

        if low <= stop_price:
            return {
                "TrailExitType":
                    "TRAIL",

                "TrailExitTime":
                    time_text(ts),

                "TrailExitPrice":
                    stop_price,

                "TrailReturnPct":
                    pct(
                        stop_price,
                        entry_price,
                    ),

                "TrailPeakPct":
                    pct(
                        running_peak,
                        entry_price,
                    ),
            }

        if high > running_peak:
            running_peak = high

    last_close = float(
        after["Close"].iloc[-1]
    )

    return {
        "TrailExitType":
            "CLOSE",

        "TrailExitTime":
            time_text(
                after.index[-1]
            ),

        "TrailExitPrice":
            last_close,

        "TrailReturnPct":
            pct(
                last_close,
                entry_price,
            ),

        "TrailPeakPct":
            pct(
                running_peak,
                entry_price,
            ),
    }


def analyze_stock(row, bars):

    date_text = str(
        row["DetectionDate"]
    )

    entry_price = pd.to_numeric(
        row["Entry0932Price"],
        errors="coerce",
    )

    if (
        pd.isna(entry_price)
        or entry_price <= 0
    ):
        return []

    # --------------------------------------------------------
    # Locate +10% touch again from raw 1-minute data.
    # --------------------------------------------------------

    base_date = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    entry_time = base_date.replace(
        hour=9,
        minute=32,
        second=0,
        microsecond=0,
    )

    work = bars[
        bars.index >= entry_time
    ].copy()

    if work.empty:
        return []

    take_price = (
        float(entry_price)
        * (1 + TAKE_PCT / 100)
    )

    take_hits = work[
        work["High"] >= take_price
    ]

    if take_hits.empty:
        return []

    take_time = (
        take_hits.index[0]
    )

    output = []

    # --------------------------------------------------------
    # Baseline:
    # 100% at +10%
    # --------------------------------------------------------

    output.append({
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

        "Close0931Pct":
            row["Close0931Pct"],

        "CxV":
            row["CxV"],

        "Entry0932Price":
            float(entry_price),

        "HitPlus10Time":
            time_text(
                take_time
            ),

        "Method":
            "BASE_TAKE10",

        "TrailPct":
            pd.NA,

        "FirstHalfReturnPct":
            10.0,

        "SecondHalfReturnPct":
            10.0,

        "CombinedReturnPct":
            10.0,

        "TrailExitType":
            "TAKE",

        "TrailExitTime":
            time_text(
                take_time
            ),

        "TrailExitPrice":
            take_price,

        "TrailPeakPct":
            row.get(
                "MFE",
                pd.NA,
            ),
    })

    # --------------------------------------------------------
    # 50% +10%, 50% trailing
    # --------------------------------------------------------

    for method, trail_pct in (
        TRAILINGS.items()
    ):

        trail = analyze_trailing(
            work,
            float(entry_price),
            take_time,
            trail_pct,
        )

        second_half_return = (
            trail["TrailReturnPct"]
        )

        combined_return = (
            10.0
            + second_half_return
        ) / 2.0

        output.append({
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

            "Close0931Pct":
                row["Close0931Pct"],

            "CxV":
                row["CxV"],

            "Entry0932Price":
                float(entry_price),

            "HitPlus10Time":
                time_text(
                    take_time
                ),

            "Method":
                f"HALF_{method}",

            "TrailPct":
                trail_pct,

            "FirstHalfReturnPct":
                10.0,

            "SecondHalfReturnPct":
                second_half_return,

            "CombinedReturnPct":
                combined_return,

            "TrailExitType":
                trail["TrailExitType"],

            "TrailExitTime":
                trail["TrailExitTime"],

            "TrailExitPrice":
                trail["TrailExitPrice"],

            "TrailPeakPct":
                trail["TrailPeakPct"],
        })

    return output


def make_summary(result_df):

    rows = []

    for method, group in (
        result_df.groupby(
            "Method",
            sort=False,
        )
    ):

        returns = pd.to_numeric(
            group["CombinedReturnPct"],
            errors="coerce",
        ).dropna()

        if returns.empty:
            continue

        mean_return = (
            returns.mean()
        )

        median_return = (
            returns.median()
        )

        total_return = (
            returns.sum()
        )

        beat_base = (
            returns > 10.0
        ).sum()

        equal_base = (
            returns == 10.0
        ).sum()

        below_base = (
            returns < 10.0
        ).sum()

        rows.append({
            "Method":
                method,

            "Trades":
                len(returns),

            "MeanReturn":
                mean_return,

            "Median":
                median_return,

            "TotalReturn":
                total_return,

            "VsBaseMean":
                mean_return - 10.0,

            "BeatBase":
                int(beat_base),

            "EqualBase":
                int(equal_base),

            "BelowBase":
                int(below_base),
        })

    return pd.DataFrame(
        rows
    )


def main():

    print(
        "=" * 78
    )

    print(
        "H1 AFTER +10% HALF-TRAILING ANALYSIS"
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

    print(
        f"+10% stocks : {len(source)}"
    )

    print(
        "First exit  : 50% at +10%"
    )

    print(
        "Second exit : TRAIL -2/-3/-4/-5%"
    )

    print(
        "Trail start : next 1m bar "
        "after first +10% touch"
    )

    all_results = []

    for _, row in source.iterrows():

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

        rows = analyze_stock(
            row,
            bars,
        )

        all_results.extend(
            rows
        )

    result_df = pd.DataFrame(
        all_results
    )

    if result_df.empty:
        print(
            "No results."
        )
        return

    summary = make_summary(
        result_df
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()

    print(
        "=" * 78
    )

    print(
        "STRATEGY COMPARISON"
    )

    print(
        "=" * 78
    )

    display = (
        summary.copy()
    )

    for col in [
        "MeanReturn",
        "Median",
        "TotalReturn",
        "VsBaseMean",
    ]:
        display[col] = (
            display[col]
            .map(
                lambda x:
                    f"{x:.2f}%"
            )
        )

    print(
        display.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Per-stock comparison
    # --------------------------------------------------------

    print()

    print(
        "=" * 78
    )

    print(
        "STOCK COMPARISON"
    )

    print(
        "=" * 78
    )

    pivot = (
        result_df.pivot_table(
            index=[
                "DetectionDate",
                "Code",
                "Name",
                "Rank",
                "HitPlus10Time",
            ],
            columns="Method",
            values="CombinedReturnPct",
            aggfunc="first",
        )
        .reset_index()
    )

    print(
        pivot.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Trailing detail
    # --------------------------------------------------------

    print()

    print(
        "=" * 78
    )

    print(
        "TRAILING EXIT DETAIL"
    )

    print(
        "=" * 78
    )

    trail_detail = result_df[
        result_df["Method"]
        != "BASE_TAKE10"
    ][[
        "DetectionDate",
        "Code",
        "Name",
        "Method",
        "HitPlus10Time",
        "TrailPeakPct",
        "TrailExitType",
        "TrailExitTime",
        "SecondHalfReturnPct",
        "CombinedReturnPct",
    ]]

    print(
        trail_detail.to_string(
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