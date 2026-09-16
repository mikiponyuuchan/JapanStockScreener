from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


TRACKING_PATH = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/h1_trailing_strategy_comparison.csv"
)

TRIGGER_PCT = 5.0
INITIAL_STOP_PCT = -3.0

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


def parse_snapshot_time(value):
    text = str(value).strip()

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(
                text,
                fmt,
            )
        except ValueError:
            pass

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

    bar = current.replace(
        second=0,
        microsecond=0,
    )

    return bar + timedelta(minutes=1)


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

    return df


def pct(price, entry):
    return (
        float(price) / float(entry) - 1
    ) * 100


def prepare_bars(
    bars,
    date_text,
    snapshot_time,
):
    start = evaluation_start(
        date_text,
        snapshot_time,
    )

    if start is None:
        return None

    work = bars[
        bars.index >= start
    ].copy()

    if work.empty:
        return None

    for col in [
        "Open",
        "High",
        "Low",
        "Close",
    ]:
        work[col] = pd.to_numeric(
            work[col],
            errors="coerce",
        )

    work = work.dropna(
        subset=[
            "High",
            "Low",
            "Close",
        ]
    )

    if work.empty:
        return None

    return work


def analyze_base(bars, entry):

    max_high = None
    min_low = None

    for ts, bar in bars.iterrows():

        high_pct = pct(
            bar["High"],
            entry,
        )

        low_pct = pct(
            bar["Low"],
            entry,
        )

        max_high = (
            high_pct
            if max_high is None
            else max(max_high, high_pct)
        )

        min_low = (
            low_pct
            if min_low is None
            else min(min_low, low_pct)
        )

        hit_take = high_pct >= 10.0
        hit_stop = low_pct <= -3.0

        if hit_take and hit_stop:
            return {
                "ExitType": "SAME_BAR",
                "ReturnPct": pd.NA,
                "ExitTime":
                    ts.strftime("%H:%M"),
                "TriggerTime": "",
                "MaxHighPct": max_high,
                "MinLowPct": min_low,
            }

        if hit_stop:
            return {
                "ExitType": "STOP",
                "ReturnPct": -3.0,
                "ExitTime":
                    ts.strftime("%H:%M"),
                "TriggerTime": "",
                "MaxHighPct": max_high,
                "MinLowPct": min_low,
            }

        if hit_take:
            return {
                "ExitType": "TAKE",
                "ReturnPct": 10.0,
                "ExitTime":
                    ts.strftime("%H:%M"),
                "TriggerTime": "",
                "MaxHighPct": max_high,
                "MinLowPct": min_low,
            }

    last_close = float(
        bars["Close"].iloc[-1]
    )

    return {
        "ExitType": "CLOSE",
        "ReturnPct":
            pct(last_close, entry),
        "ExitTime":
            bars.index[-1].strftime(
                "%H:%M"
            ),
        "TriggerTime": "",
        "MaxHighPct": max_high,
        "MinLowPct": min_low,
    }


def analyze_trailing(
    bars,
    entry,
    trail_pct,
):

    active = False
    trigger_time = None

    # Highest price confirmed through
    # the PREVIOUS completed 1-minute bar.
    confirmed_peak = None

    max_high_pct = None
    min_low_pct = None

    for ts, bar in bars.iterrows():

        high_price = float(
            bar["High"]
        )

        low_price = float(
            bar["Low"]
        )

        high_pct = pct(
            high_price,
            entry,
        )

        low_pct = pct(
            low_price,
            entry,
        )

        max_high_pct = (
            high_pct
            if max_high_pct is None
            else max(
                max_high_pct,
                high_pct,
            )
        )

        min_low_pct = (
            low_pct
            if min_low_pct is None
            else min(
                min_low_pct,
                low_pct,
            )
        )

        if not active:

            hit_trigger = (
                high_pct >= TRIGGER_PCT
            )

            hit_stop = (
                low_pct
                <= INITIAL_STOP_PCT
            )

            if hit_trigger and hit_stop:
                return {
                    "ExitType":
                        "SAME_BAR_TRIGGER",
                    "ReturnPct":
                        pd.NA,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime":
                        ts.strftime("%H:%M"),
                    "MaxHighPct":
                        max_high_pct,
                    "MinLowPct":
                        min_low_pct,
                }

            if hit_stop:
                return {
                    "ExitType": "STOP",
                    "ReturnPct":
                        INITIAL_STOP_PCT,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime": "",
                    "MaxHighPct":
                        max_high_pct,
                    "MinLowPct":
                        min_low_pct,
                }

            if hit_trigger:
                active = True
                trigger_time = ts

                # This high becomes usable
                # from the NEXT bar.
                confirmed_peak = high_price

                continue

        else:
            # Stop is calculated only from
            # highs confirmed before this bar.
            stop_price = (
                confirmed_peak
                * (
                    1.0
                    - trail_pct / 100.0
                )
            )

            if low_price <= stop_price:

                return_pct = pct(
                    stop_price,
                    entry,
                )

                return {
                    "ExitType": "TRAIL",
                    "ReturnPct":
                        return_pct,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime":
                        trigger_time.strftime(
                            "%H:%M"
                        ),
                    "MaxHighPct":
                        max_high_pct,
                    "MinLowPct":
                        min_low_pct,
                }

            # Current high is confirmed only
            # after this bar survives.
            if high_price > confirmed_peak:
                confirmed_peak = high_price

    last_close = float(
        bars["Close"].iloc[-1]
    )

    return {
        "ExitType": "CLOSE",
        "ReturnPct":
            pct(last_close, entry),
        "ExitTime":
            bars.index[-1].strftime(
                "%H:%M"
            ),
        "TriggerTime":
            (
                trigger_time.strftime(
                    "%H:%M"
                )
                if trigger_time is not None
                else ""
            ),
        "MaxHighPct":
            max_high_pct,
        "MinLowPct":
            min_low_pct,
    }


def print_summary(
    name,
    frame,
):

    ret = pd.to_numeric(
        frame["ReturnPct"],
        errors="coerce",
    ).dropna()

    if ret.empty:
        print(
            f"{name:<8} N=0"
        )
        return

    plus = (
        ret.gt(0).mean() * 100
    )

    print(
        f"{name:<8} "
        f"N={len(ret):2d} "
        f"Mean={ret.mean():7.2f}% "
        f"Median={ret.median():7.2f}% "
        f"Plus={plus:6.1f}% "
        f"Total={ret.sum():8.2f}%"
    )

    print(
        frame["ExitType"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )


def main():

    if not TRACKING_PATH.exists():
        print(
            f"Not found : {TRACKING_PATH}"
        )
        return

    source = pd.read_csv(
        TRACKING_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    forward = source[
        (
            source["DataType"]
            == "FORWARD"
        )
        & (
            source["ExitType"]
            .notna()
        )
        & (
            source["ExitType"]
            .astype(str)
            .str.strip()
            .ne("")
        )
    ].copy()

    forward["Code"] = (
        forward["Code"]
        .map(normalize_code)
    )

    print(
        f"H1 Forward rows : "
        f"{len(forward)}"
    )

    all_results = []

    cache = {}

    for _, row in forward.iterrows():

        date_text = str(
            row["DetectionDate"]
        ).strip()

        time_text = str(
            row["SnapshotTime"]
        ).strip()

        code = normalize_code(
            row["Code"]
        )

        entry = pd.to_numeric(
            row["SnapshotPrice"],
            errors="coerce",
        )

        if pd.isna(entry) or entry <= 0:
            print(
                f"{date_text} {code} "
                f"BAD ENTRY"
            )
            continue

        key = (
            code,
            date_text,
        )

        if key not in cache:
            cache[key] = download_1m(
                code,
                date_text,
            )

        bars = cache[key]

        if bars is None:
            print(
                f"{date_text} {code} "
                f"NO DATA"
            )
            continue

        work = prepare_bars(
            bars,
            date_text,
            time_text,
        )

        if work is None:
            print(
                f"{date_text} {code} "
                f"NO BARS"
            )
            continue

        strategies = {
            "BASE":
                analyze_base(
                    work,
                    float(entry),
                )
        }

        for (
            name,
            trail_pct,
        ) in TRAILINGS.items():

            strategies[name] = (
                analyze_trailing(
                    work,
                    float(entry),
                    trail_pct,
                )
            )

        base_return = pd.to_numeric(
            strategies["BASE"][
                "ReturnPct"
            ],
            errors="coerce",
        )

        for name, result in (
            strategies.items()
        ):

            ret = pd.to_numeric(
                result["ReturnPct"],
                errors="coerce",
            )

            diff = (
                ret - base_return
                if (
                    pd.notna(ret)
                    and pd.notna(
                        base_return
                    )
                )
                else pd.NA
            )

            all_results.append(
                {
                    "DetectionDate":
                        date_text,
                    "SnapshotTime":
                        time_text,
                    "Code":
                        code,
                    "Name":
                        row.get(
                            "Name",
                            "",
                        ),
                    "Rank":
                        row.get(
                            "Rank",
                            pd.NA,
                        ),
                    "SnapshotPrice":
                        entry,
                    "Change":
                        row.get(
                            "Change",
                            pd.NA,
                        ),
                    "CxV":
                        row.get(
                            "CxV",
                            pd.NA,
                        ),
                    "Strategy":
                        name,
                    "ExitType":
                        result[
                            "ExitType"
                        ],
                    "ReturnPct":
                        result[
                            "ReturnPct"
                        ],
                    "DiffVsBase":
                        diff,
                    "ExitTime":
                        result[
                            "ExitTime"
                        ],
                    "TriggerTime":
                        result[
                            "TriggerTime"
                        ],
                    "MaxHighPct":
                        result[
                            "MaxHighPct"
                        ],
                    "MinLowPct":
                        result[
                            "MinLowPct"
                        ],
                }
            )

        print(
            f"{date_text} "
            f"{code} OK"
        )

    result_df = pd.DataFrame(
        all_results
    )

    if result_df.empty:
        print("No results.")
        return

    print()
    print("=" * 72)
    print(
        "H1 TRAILING STRATEGY COMPARISON"
    )
    print("=" * 72)

    order = [
        "BASE",
        "TRAIL2",
        "TRAIL3",
        "TRAIL4",
        "TRAIL5",
    ]

    for name in order:
        part = result_df[
            result_df["Strategy"]
            == name
        ]

        print()
        print_summary(
            name,
            part,
        )

    print()
    print("=" * 72)
    print("DIFFERENCE VS BASE")
    print("=" * 72)

    for name in order[1:]:

        part = result_df[
            result_df["Strategy"]
            == name
        ].copy()

        diff = pd.to_numeric(
            part["DiffVsBase"],
            errors="coerce",
        ).dropna()

        if diff.empty:
            continue

        print(
            f"{name:<8} "
            f"MeanDiff={diff.mean():7.2f}% "
            f"Improved={(diff > 0).sum():2d} "
            f"Same={(diff == 0).sum():2d} "
            f"Worse={(diff < 0).sum():2d}"
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

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
