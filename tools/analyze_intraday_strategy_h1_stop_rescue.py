from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


TRACKING_PATH = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/h1_stop_rescue_analysis.csv"
)

STOP3_PCT = -3.0
STOP6_PCT = -6.0
TAKE_PCT = 10.0


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

    # Snapshot minute itself is not used.
    # Evaluation starts from the next
    # completed 1-minute bar.
    return bar + timedelta(
        minutes=1
    )


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
            f"{date_text} {code} : "
            f"{exc}"
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
        "Volume",
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


def pct(
    price,
    entry,
):
    return (
        float(price)
        / float(entry)
        - 1
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
        "Volume",
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


def analyze_stop3_case(
    bars,
    entry,
):

    first_stop_time = None
    stop_position = None

    pre_stop_max_high = None
    pre_stop_max_volume = None
    pre_stop_cum_volume = 0.0

    # ---------------------------------
    # Information available no later
    # than the first -3% stop bar.
    # ---------------------------------
    for pos, (ts, bar) in enumerate(
        bars.iterrows()
    ):

        high_pct = pct(
            bar["High"],
            entry,
        )

        low_pct = pct(
            bar["Low"],
            entry,
        )

        pre_stop_max_high = (
            high_pct
            if pre_stop_max_high is None
            else max(
                pre_stop_max_high,
                high_pct,
            )
        )

        volume = pd.to_numeric(
            bar["Volume"],
            errors="coerce",
        )

        if pd.notna(volume):
            pre_stop_cum_volume += (
                float(volume)
            )

            pre_stop_max_volume = (
                float(volume)
                if (
                    pre_stop_max_volume
                    is None
                )
                else max(
                    pre_stop_max_volume,
                    float(volume),
                )
            )

        if low_pct <= STOP3_PCT:
            first_stop_time = ts
            stop_position = pos
            break

    if first_stop_time is None:
        return None

    start_time = bars.index[0]

    minutes_to_stop = (
        first_stop_time
        - start_time
    ).total_seconds() / 60.0

    # ---------------------------------
    # Everything below this point is
    # OUTCOME information.
    # Do not use it as an entry-time
    # classification feature.
    # ---------------------------------
    after = bars.iloc[
        stop_position:
    ].copy()

    after_max_high_pct = (
        (
            after["High"].max()
            / float(entry)
            - 1
        )
        * 100
    )

    hit_plus10_after_stop = bool(
        after_max_high_pct
        >= TAKE_PCT
    )

    stop6_exit = "CLOSE"
    stop6_return = pct(
        bars["Close"].iloc[-1],
        entry,
    )
    stop6_exit_time = (
        bars.index[-1]
        .strftime("%H:%M")
    )

    # Start evaluating the wider stop
    # from the original evaluation
    # window. This reproduces the
    # STOP6 strategy independently.
    for ts, bar in bars.iterrows():

        high_pct = pct(
            bar["High"],
            entry,
        )

        low_pct = pct(
            bar["Low"],
            entry,
        )

        hit_take = (
            high_pct >= TAKE_PCT
        )

        hit_stop6 = (
            low_pct <= STOP6_PCT
        )

        if hit_take and hit_stop6:
            stop6_exit = "SAME_BAR"
            stop6_return = pd.NA
            stop6_exit_time = (
                ts.strftime("%H:%M")
            )
            break

        if hit_stop6:
            stop6_exit = "STOP"
            stop6_return = STOP6_PCT
            stop6_exit_time = (
                ts.strftime("%H:%M")
            )
            break

        if hit_take:
            stop6_exit = "TAKE"
            stop6_return = TAKE_PCT
            stop6_exit_time = (
                ts.strftime("%H:%M")
            )
            break

    if (
        stop6_exit == "TAKE"
        and pd.notna(stop6_return)
        and float(stop6_return)
        >= TAKE_PCT
    ):
        rescue_result = "RESCUED"
    else:
        rescue_result = (
            "NOT_RESCUED"
        )

    return {
        "FirstStop3Time":
            first_stop_time.strftime(
                "%H:%M"
            ),
        "MinutesToStop":
            minutes_to_stop,
        "PreStopMaxHighPct":
            pre_stop_max_high,
        "PreStopMaxVolume":
            pre_stop_max_volume,
        "PreStopCumVolume":
            pre_stop_cum_volume,
        "AfterStopMaxHighPct":
            after_max_high_pct,
        "HitPlus10AfterStop":
            hit_plus10_after_stop,
        "STOP6Exit":
            stop6_exit,
        "STOP6Return":
            stop6_return,
        "STOP6ExitTime":
            stop6_exit_time,
        "RescueResult":
            rescue_result,
    }


def main():

    if not TRACKING_PATH.exists():
        print(
            f"Not found : "
            f"{TRACKING_PATH}"
        )
        return

    source = pd.read_csv(
        TRACKING_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    forward = source[
        source["DataType"]
        .eq("FORWARD")
    ].copy()

    # We specifically analyze the
    # existing H1 -3% STOP cases.
    forward = forward[
        forward["ExitType"]
        .astype(str)
        .str.strip()
        .eq("STOP")
    ].copy()

    forward["Code"] = (
        forward["Code"]
        .map(normalize_code)
    )

    print(
        f"H1 STOP3 rows : "
        f"{len(forward)}"
    )

    results = []
    cache = {}

    for _, row in (
        forward.iterrows()
    ):

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

        if (
            pd.isna(entry)
            or entry <= 0
        ):
            print(
                f"{date_text} "
                f"{code} BAD ENTRY"
            )
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
            continue

        analysis = (
            analyze_stop3_case(
                work,
                float(entry),
            )
        )

        if analysis is None:
            print(
                f"{date_text} "
                f"{code} "
                f"NO STOP3"
            )
            continue

        item = {
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
        }

        item.update(
            analysis
        )

        results.append(
            item
        )

        print(
            f"{date_text} "
            f"{code} "
            f"{analysis['RescueResult']}"
        )

    result_df = pd.DataFrame(
        results
    )

    if result_df.empty:
        print(
            "No results."
        )
        return

    print()
    print("=" * 76)
    print(
        "H1 STOP -3% RESCUE ANALYSIS"
    )
    print("=" * 76)

    print(
        f"STOP3 cases : "
        f"{len(result_df)}"
    )

    rescued = result_df[
        result_df["RescueResult"]
        == "RESCUED"
    ]

    not_rescued = result_df[
        result_df["RescueResult"]
        == "NOT_RESCUED"
    ]

    print(
        f"RESCUED     : "
        f"{len(rescued)}"
    )

    print(
        f"NOT_RESCUED : "
        f"{len(not_rescued)}"
    )

    print()
    print("=" * 76)
    print(
        "FEATURE COMPARISON"
    )
    print("=" * 76)

    features = [
        "Rank",
        "Change",
        "CxV",
        "MinutesToStop",
        "PreStopMaxHighPct",
        "PreStopMaxVolume",
        "PreStopCumVolume",
    ]

    for group_name, part in [
        ("RESCUED", rescued),
        (
            "NOT_RESCUED",
            not_rescued,
        ),
    ]:

        print()
        print(
            f"[{group_name}]"
        )

        if part.empty:
            print("N=0")
            continue

        for col in features:

            values = pd.to_numeric(
                part[col],
                errors="coerce",
            ).dropna()

            if values.empty:
                continue

            print(
                f"{col:<20} "
                f"N={len(values):2d} "
                f"Mean="
                f"{values.mean():9.2f} "
                f"Median="
                f"{values.median():9.2f} "
                f"Min="
                f"{values.min():9.2f} "
                f"Max="
                f"{values.max():9.2f}"
            )

    print()
    print("=" * 76)
    print(
        "INDIVIDUAL STOP3 CASES"
    )
    print("=" * 76)

    show_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Change",
        "CxV",
        "FirstStop3Time",
        "MinutesToStop",
        "PreStopMaxHighPct",
        "PreStopMaxVolume",
        "PreStopCumVolume",
        "AfterStopMaxHighPct",
        "STOP6Exit",
        "STOP6Return",
        "STOP6ExitTime",
        "RescueResult",
    ]

    print(
        result_df[
            show_cols
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

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
