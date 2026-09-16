from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


TRACKING_PATH = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/h1_exit_strategy_comparison.csv"
)


STRATEGIES = {
    "BASE": {
        "take": 10.0,
        "trigger": None,
        "lock": -3.0,
    },
    "FIXED5": {
        "take": 5.0,
        "trigger": None,
        "lock": -3.0,
    },
    "BE5": {
        "take": None,
        "trigger": 5.0,
        "lock": 0.0,
    },
    "LOCK2": {
        "take": None,
        "trigger": 5.0,
        "lock": 2.0,
    },
    "LOCK3": {
        "take": None,
        "trigger": 5.0,
        "lock": 3.0,
    },
}


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def parse_snapshot(date_text, time_text):
    text = (
        f"{str(date_text).strip()} "
        f"{str(time_text).strip()}"
    )

    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]:
        try:
            return datetime.strptime(
                text,
                fmt,
            )
        except ValueError:
            pass

    return None


def evaluation_start(date_text, time_text):
    current = parse_snapshot(
        date_text,
        time_text,
    )

    if current is None:
        return None

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
            f"DOWNLOAD ERROR : "
            f"{date_text} {code} {exc}"
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


def analyze_strategy(
    bars,
    entry,
    strategy_name,
):
    config = STRATEGIES[strategy_name]

    take = config["take"]
    trigger = config["trigger"]
    lock = config["lock"]

    stop_level = -3.0
    trigger_active = False

    max_high = None
    min_low = None

    trigger_time = None

    for ts, bar in bars.iterrows():

        high_pct = pct(
            bar["High"],
            entry,
        )

        low_pct = pct(
            bar["Low"],
            entry,
        )

        if (
            max_high is None
            or high_pct > max_high
        ):
            max_high = high_pct

        if (
            min_low is None
            or low_pct < min_low
        ):
            min_low = low_pct

        # --------------------------------
        # Fixed profit target
        # --------------------------------
        if take is not None:

            hit_take = (
                high_pct >= take
            )

            hit_stop = (
                low_pct <= stop_level
            )

            if hit_take and hit_stop:
                return {
                    "ExitType":
                        "SAME_BAR",
                    "ReturnPct":
                        pd.NA,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime":
                        "",
                    "MaxHighPct":
                        max_high,
                    "MinLowPct":
                        min_low,
                }

            if hit_stop:
                return {
                    "ExitType":
                        "STOP",
                    "ReturnPct":
                        stop_level,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime":
                        "",
                    "MaxHighPct":
                        max_high,
                    "MinLowPct":
                        min_low,
                }

            if hit_take:
                return {
                    "ExitType":
                        "TAKE",
                    "ReturnPct":
                        take,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime":
                        "",
                    "MaxHighPct":
                        max_high,
                    "MinLowPct":
                        min_low,
                }

            continue

        # --------------------------------
        # Trigger / lock strategy
        # --------------------------------
        if not trigger_active:

            hit_trigger = (
                high_pct >= trigger
            )

            hit_stop = (
                low_pct <= -3.0
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
                        max_high,
                    "MinLowPct":
                        min_low,
                }

            if hit_stop:
                return {
                    "ExitType":
                        "STOP",
                    "ReturnPct":
                        -3.0,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime":
                        "",
                    "MaxHighPct":
                        max_high,
                    "MinLowPct":
                        min_low,
                }

            if hit_trigger:
                trigger_active = True
                stop_level = lock
                trigger_time = ts

                # Do not allow the newly raised
                # stop to execute in the same bar.
                # Intrabar order is unknown.
                continue

        else:
            if low_pct <= stop_level:
                return {
                    "ExitType":
                        "LOCK",
                    "ReturnPct":
                        stop_level,
                    "ExitTime":
                        ts.strftime("%H:%M"),
                    "TriggerTime":
                        trigger_time.strftime(
                            "%H:%M"
                        ),
                    "MaxHighPct":
                        max_high,
                    "MinLowPct":
                        min_low,
                }

    last_close = float(
        bars["Close"].iloc[-1]
    )

    return {
        "ExitType":
            "CLOSE",
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
            max_high,
        "MinLowPct":
            min_low,
    }


def print_summary(result):

    print()
    print("=" * 72)
    print("H1 EXIT STRATEGY COMPARISON")
    print("=" * 72)

    for strategy in STRATEGIES:

        work = result[
            result["Strategy"]
            == strategy
        ].copy()

        ret = pd.to_numeric(
            work["ReturnPct"],
            errors="coerce",
        ).dropna()

        if ret.empty:
            print()
            print(
                f"{strategy:<8} "
                f"N=0"
            )
            continue

        plus = (
            ret > 0
        ).mean() * 100

        print()
        print(
            f"{strategy:<8} "
            f"N={len(ret):2d} "
            f"Mean={ret.mean():7.2f}% "
            f"Median={ret.median():7.2f}% "
            f"Plus={plus:6.1f}% "
            f"Total={ret.sum():8.2f}%"
        )

        exits = (
            work["ExitType"]
            .value_counts()
        )

        print(
            exits.to_string()
        )


def main():

    if not TRACKING_PATH.exists():
        print(
            f"Not found : {TRACKING_PATH}"
        )
        return

    df = pd.read_csv(
        TRACKING_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    # Completed FORWARD rows only
    work = df[
        df["DataType"]
        == "FORWARD"
    ].copy()

    work = work[
        work["ExitType"]
        .notna()
        & (
            work["ExitType"]
            .astype(str)
            .str.strip()
            .str.len()
            > 0
        )
    ].copy()

    if work.empty:
        print(
            "No completed FORWARD rows."
        )
        return

    print(
        f"H1 Forward rows : {len(work)}"
    )

    rows = []
    cache = {}

    for _, row in work.iterrows():

        code = normalize_code(
            row["Code"]
        )

        date_text = str(
            row["DetectionDate"]
        ).strip()

        start = evaluation_start(
            date_text,
            row["SnapshotTime"],
        )

        if start is None:
            print(
                f"INVALID TIME : "
                f"{date_text} {code}"
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
                f"NO DATA : "
                f"{date_text} {code}"
            )
            continue

        bars = bars[
            bars.index >= start
        ].copy()

        if bars.empty:
            print(
                f"NO BARS : "
                f"{date_text} {code}"
            )
            continue

        entry = pd.to_numeric(
            row["SnapshotPrice"],
            errors="coerce",
        )

        if pd.isna(entry) or entry <= 0:
            continue

        print(
            f"{date_text} {code}",
            end=" ",
        )

        for strategy in STRATEGIES:

            result = analyze_strategy(
                bars,
                float(entry),
                strategy,
            )

            rows.append(
                {
                    "DetectionDate":
                        date_text,
                    "SnapshotTime":
                        row["SnapshotTime"],
                    "Code":
                        code,
                    "Name":
                        row["Name"],
                    "Rank":
                        row["Rank"],
                    "SnapshotPrice":
                        entry,
                    "Change":
                        row["Change"],
                    "CxV":
                        row["CxV"],
                    "LimitUpRoomPct":
                        row.get(
                            "LimitUpRoomPct",
                            pd.NA,
                        ),
                    "Strategy":
                        strategy,
                    **result,
                }
            )

        print("OK")

    if not rows:
        print("No results.")
        return

    result = pd.DataFrame(rows)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print_summary(result)

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
