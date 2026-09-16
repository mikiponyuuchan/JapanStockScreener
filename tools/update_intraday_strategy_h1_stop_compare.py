from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


SOURCE_PATH = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

OUTPUT_PATH = Path(
    "data/tracking/intraday_strategy_h1_stop_compare.csv"
)

TAKE_PCT = 10.0

STOP_LEVELS = {
    "STOP3": -3.0,
    "STOP6": -6.0,
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


def evaluation_start(
    date_text,
    time_text,
):
    t = parse_snapshot_time(
        time_text
    )

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

    # Same rule as current H1:
    # evaluate from next 1-minute bar.
    return bar + timedelta(
        minutes=1
    )


def can_finalize(date_text):
    try:
        detection_date = (
            datetime.strptime(
                date_text,
                "%Y-%m-%d",
            ).date()
        )
    except ValueError:
        return False

    now = datetime.now()

    if detection_date < now.date():
        return True

    if detection_date > now.date():
        return False

    # Tokyo market close.
    close_time = now.replace(
        hour=15,
        minute=30,
        second=0,
        microsecond=0,
    )

    return now >= close_time


def download_1m(
    code,
    date_text,
):
    ticker = f"{code}.T"

    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    end = start + timedelta(
        days=1
    )

    try:
        df = yf.download(
            ticker,
            start=start.strftime(
                "%Y-%m-%d"
            ),
            end=end.strftime(
                "%Y-%m-%d"
            ),
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
                .tz_convert(
                    "Asia/Tokyo"
                )
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

    return df


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


def pct(price, entry):
    return (
        float(price)
        / float(entry)
        - 1.0
    ) * 100.0


def analyze_fixed(
    bars,
    entry,
    stop_pct,
):

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
            else max(
                max_high,
                high_pct,
            )
        )

        min_low = (
            low_pct
            if min_low is None
            else min(
                min_low,
                low_pct,
            )
        )

        hit_take = (
            high_pct >= TAKE_PCT
        )

        hit_stop = (
            low_pct <= stop_pct
        )

        # With 1-minute OHLC we cannot
        # determine intrabar ordering.
        if hit_take and hit_stop:
            return {
                "ExitType":
                    "SAME_BAR",
                "ReturnPct":
                    pd.NA,
                "ExitTime":
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
                    stop_pct,
                "ExitTime":
                    ts.strftime("%H:%M"),
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
                    TAKE_PCT,
                "ExitTime":
                    ts.strftime("%H:%M"),
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
            pct(
                last_close,
                entry,
            ),
        "ExitTime":
            bars.index[-1].strftime(
                "%H:%M"
            ),
        "MaxHighPct":
            max_high,
        "MinLowPct":
            min_low,
    }


def load_existing():

    if not OUTPUT_PATH.exists():
        return pd.DataFrame()

    return pd.read_csv(
        OUTPUT_PATH,
        dtype={"Code": str},
        low_memory=False,
    )


def main():

    if not SOURCE_PATH.exists():
        print(
            f"Not found : {SOURCE_PATH}"
        )
        return

    source = pd.read_csv(
        SOURCE_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    source["Code"] = (
        source["Code"]
        .map(normalize_code)
    )

    forward = source[
        source["DataType"]
        .eq("FORWARD")
    ].copy()

    print(
        f"H1 Forward rows : "
        f"{len(forward)}"
    )

    existing = load_existing()

    if not existing.empty:
        existing["Code"] = (
            existing["Code"]
            .map(normalize_code)
        )

    new_rows = []
    cache = {}

    updated = 0
    skipped = 0
    errors = 0

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

        if not can_finalize(
            date_text
        ):
            skipped += 1
            continue

        # One result per H1 snapshot.
        if not existing.empty:

            same = (
                existing[
                    "DetectionDate"
                ]
                .astype(str)
                .eq(date_text)
                & existing[
                    "SnapshotTime"
                ]
                .astype(str)
                .eq(time_text)
                & existing[
                    "Code"
                ]
                .astype(str)
                .eq(code)
            )

            if same.any():
                skipped += 1
                continue

        entry = pd.to_numeric(
            row["SnapshotPrice"],
            errors="coerce",
        )

        if (
            pd.isna(entry)
            or entry <= 0
        ):
            print(
                f"{date_text} "
                f"{code} BAD ENTRY"
            )
            errors += 1
            continue

        key = (
            code,
            date_text,
        )

        if key not in cache:
            cache[key] = (
                download_1m(
                    code,
                    date_text,
                )
            )

        bars = cache[key]

        if bars is None:
            print(
                f"{date_text} "
                f"{code} NO DATA"
            )
            errors += 1
            continue

        work = prepare_bars(
            bars,
            date_text,
            time_text,
        )

        if work is None:
            print(
                f"{date_text} "
                f"{code} NO BARS"
            )
            errors += 1
            continue

        stop3 = analyze_fixed(
            work,
            float(entry),
            STOP_LEVELS["STOP3"],
        )

        stop6 = analyze_fixed(
            work,
            float(entry),
            STOP_LEVELS["STOP6"],
        )

        ret3 = pd.to_numeric(
            stop3["ReturnPct"],
            errors="coerce",
        )

        ret6 = pd.to_numeric(
            stop6["ReturnPct"],
            errors="coerce",
        )

        diff = (
            float(ret6 - ret3)
            if (
                pd.notna(ret3)
                and pd.notna(ret6)
            )
            else pd.NA
        )

        new_rows.append(
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
                "LimitUpRoomPct":
                    row.get(
                        "LimitUpRoomPct",
                        pd.NA,
                    ),
                "STOP3ExitType":
                    stop3["ExitType"],
                "STOP3ReturnPct":
                    stop3["ReturnPct"],
                "STOP3ExitTime":
                    stop3["ExitTime"],
                "STOP6ExitType":
                    stop6["ExitType"],
                "STOP6ReturnPct":
                    stop6["ReturnPct"],
                "STOP6ExitTime":
                    stop6["ExitTime"],
                "DiffStop6Vs3":
                    diff,
                "MaxHighPct":
                    stop3["MaxHighPct"],
                "MinLowPct":
                    stop3["MinLowPct"],
            }
        )

        updated += 1

        print(
            f"{date_text} {code} "
            f"S3={stop3['ExitType']} "
            f"{stop3['ReturnPct']} "
            f"S6={stop6['ExitType']} "
            f"{stop6['ReturnPct']}"
        )

    if new_rows:

        new_df = pd.DataFrame(
            new_rows
        )

        if existing.empty:
            result = new_df
        else:
            result = pd.concat(
                [
                    existing,
                    new_df,
                ],
                ignore_index=True,
            )

        result = (
            result
            .drop_duplicates(
                subset=[
                    "DetectionDate",
                    "SnapshotTime",
                    "Code",
                ],
                keep="last",
            )
            .sort_values(
                [
                    "DetectionDate",
                    "Rank",
                    "Code",
                ]
            )
            .reset_index(
                drop=True
            )
        )

        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result.to_csv(
            OUTPUT_PATH,
            index=False,
            encoding="utf-8-sig",
        )

    elif existing.empty:
        result = pd.DataFrame()
    else:
        result = existing

    print()
    print("=" * 64)
    print(
        "H1 STOP3 / STOP6 FORWARD TRACKING"
    )
    print("=" * 64)

    print(
        f"Updated : {updated}"
    )
    print(
        f"Skipped : {skipped}"
    )
    print(
        f"Errors  : {errors}"
    )

    if not result.empty:

        r3 = pd.to_numeric(
            result["STOP3ReturnPct"],
            errors="coerce",
        )

        r6 = pd.to_numeric(
            result["STOP6ReturnPct"],
            errors="coerce",
        )

        valid = (
            r3.notna()
            & r6.notna()
        )

        r3 = r3[valid]
        r6 = r6[valid]

        print(
            f"Total   : {len(result)}"
        )
        print(
            f"Compared: {valid.sum()}"
        )

        if valid.any():

            print()
            print(
                f"STOP3 Mean  : "
                f"{r3.mean():.2f}%"
            )
            print(
                f"STOP3 Median: "
                f"{r3.median():.2f}%"
            )
            print(
                f"STOP3 Total : "
                f"{r3.sum():.2f}%"
            )

            print()
            print(
                f"STOP6 Mean  : "
                f"{r6.mean():.2f}%"
            )
            print(
                f"STOP6 Median: "
                f"{r6.median():.2f}%"
            )
            print(
                f"STOP6 Total : "
                f"{r6.sum():.2f}%"
            )

            diff = r6 - r3

            print()
            print(
                f"Mean Diff   : "
                f"{diff.mean():.2f}%"
            )
            print(
                f"STOP6 better: "
                f"{(diff > 0).sum()}"
            )
            print(
                f"Same        : "
                f"{(diff == 0).sum()}"
            )
            print(
                f"STOP6 worse : "
                f"{(diff < 0).sum()}"
            )

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
