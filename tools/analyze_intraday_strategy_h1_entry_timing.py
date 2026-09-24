from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


TRACKING_FILE = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

OUTPUT_FILE = Path(
    "data/analysis/intraday_strategy_h1_entry_timing.csv"
)

TAKE_PCT = 10.0
STOP_PCT = -3.0

WAIT_TIMES = [
    "09:31",
    "09:32",
    "09:33",
    "09:35",
]


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def parse_snapshot_time(value):
    text = str(value).strip()

    for fmt in [
        "%H:%M:%S",
        "%H:%M",
    ]:
        try:
            return datetime.strptime(
                text,
                fmt,
            ).time()
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


def evaluate_trade(
    bars,
    entry_price,
    start_time,
):
    if (
        bars is None
        or bars.empty
        or pd.isna(entry_price)
        or entry_price <= 0
        or start_time is None
    ):
        return None

    work = bars[
        bars.index >= start_time
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

    take_price = (
        entry_price
        * (1 + TAKE_PCT / 100)
    )

    stop_price = (
        entry_price
        * (1 + STOP_PCT / 100)
    )

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
            return_pct = TAKE_PCT

        elif stop_time < take_time:
            exit_type = "STOP"
            return_pct = STOP_PCT

        else:
            exit_type = "SAME_BAR"
            return_pct = pd.NA

    elif take_time is not None:
        exit_type = "TAKE"
        return_pct = TAKE_PCT

    elif stop_time is not None:
        exit_type = "STOP"
        return_pct = STOP_PCT

    else:
        exit_type = "CLOSE"

        last_close = float(
            close.iloc[-1]
        )

        return_pct = (
            last_close / entry_price - 1
        ) * 100

    return {
        "ExitType": exit_type,
        "ReturnPct": return_pct,
        "MaxHighPct": (
            float(high.max())
            / entry_price
            - 1
        ) * 100,
        "MinLowPct": (
            float(low.min())
            / entry_price
            - 1
        ) * 100,
        "ClosePct": (
            float(close.iloc[-1])
            / entry_price
            - 1
        ) * 100,
    }


def get_wait_entry(
    bars,
    date_text,
    hhmm,
):
    target = datetime.strptime(
        f"{date_text} {hhmm}",
        "%Y-%m-%d %H:%M",
    )

    hit = bars[
        bars.index >= target
    ]

    if hit.empty:
        return None, None

    first_time = hit.index[0]

    price = pd.to_numeric(
        hit.iloc[0]["Open"],
        errors="coerce",
    )

    if pd.isna(price) or price <= 0:
        return None, None

    return float(price), first_time


def get_dip_entry(
    bars,
    snapshot_price,
    start_time,
    dip_pct,
):
    target_price = (
        snapshot_price
        * (1 - dip_pct / 100)
    )

    work = bars[
        bars.index >= start_time
    ]

    if work.empty:
        return None, None

    low = pd.to_numeric(
        work["Low"],
        errors="coerce",
    )

    hits = work[
        low <= target_price
    ]

    if hits.empty:
        return None, None

    hit_time = hits.index[0]

    # 約定した1分足では高値・安値の
    # 時系列が不明なため、その次の足から判定。
    evaluation_time = (
        hit_time
        + timedelta(minutes=1)
    )

    return (
        float(target_price),
        evaluation_time,
    )


def add_result(
    output,
    row,
    method,
    entry_price,
    start_time,
    result,
):
    record = {
        "DetectionDate":
            row["DetectionDate"],
        "SnapshotTime":
            row["SnapshotTime"],
        "Code":
            normalize_code(row["Code"]),
        "Name":
            row["Name"],
        "Rank":
            row["Rank"],
        "Change":
            row["Change"],
        "VolumeRatio":
            row["VolumeRatio"],
        "CxV":
            row["CxV"],
        "Method":
            method,
        "EntryPrice":
            entry_price,
        "EvaluationStart":
            (
                start_time.strftime(
                    "%H:%M"
                )
                if start_time is not None
                else ""
            ),
        "Filled":
            result is not None,
    }

    if result is None:
        record.update({
            "ExitType": "",
            "ReturnPct": pd.NA,
            "MaxHighPct": pd.NA,
            "MinLowPct": pd.NA,
            "ClosePct": pd.NA,
        })
    else:
        record.update(result)

    output.append(record)


def print_summary(result_df):
    print()
    print("=" * 72)
    print("H1 ENTRY TIMING COMPARISON")
    print("=" * 72)

    for method in [
        "CURRENT",
        "T0931",
        "T0932",
        "T0933",
        "T0935",
        "DIP1",
        "DIP2",
    ]:
        x = result_df[
            result_df["Method"] == method
        ].copy()

        filled = x[
            x["Filled"] == True
        ].copy()

        returns = pd.to_numeric(
            filled["ReturnPct"],
            errors="coerce",
        ).dropna()

        print()
        print(f"[{method}]")
        print(
            f"Filled      : "
            f"{len(filled)} / {len(x)}"
        )

        if returns.empty:
            print("No valid results")
            continue

        print(
            f"Mean return : "
            f"{returns.mean():.2f}%"
        )

        print(
            f"Median      : "
            f"{returns.median():.2f}%"
        )

        print(
            f"Win rate    : "
            f"{(returns > 0).mean() * 100:.1f}%"
        )

        print(
            f"Total return: "
            f"{returns.sum():.2f}%"
        )

        exits = (
            filled["ExitType"]
            .value_counts()
        )

        print(
            "Exit types  : "
            + ", ".join(
                f"{k}={v}"
                for k, v
                in exits.items()
            )
        )


def main():
    print("=" * 72)
    print("H1 ENTRY TIMING ANALYSIS")
    print("=" * 72)

    if not TRACKING_FILE.exists():
        raise RuntimeError(
            f"Not found : {TRACKING_FILE}"
        )

    df = pd.read_csv(
        TRACKING_FILE,
        dtype={"Code": str},
        low_memory=False,
    )

    if "DataType" in df.columns:
        df = df[
            df["DataType"]
            .astype(str)
            .str.upper()
            .eq("FORWARD")
        ].copy()

    df = df[
        pd.to_numeric(
            df["ReturnPct"],
            errors="coerce",
        ).notna()
    ].copy()

    print(
        f"Forward completed : {len(df)}"
    )

    output = []

    for _, row in df.iterrows():
        date_text = str(
            row["DetectionDate"]
        )

        code = normalize_code(
            row["Code"]
        )

        snapshot_price = pd.to_numeric(
            row["SnapshotPrice"],
            errors="coerce",
        )

        if (
            pd.isna(snapshot_price)
            or snapshot_price <= 0
        ):
            continue

        bars = download_1m(
            code,
            date_text,
        )

        if bars is None or bars.empty:
            print(
                f"NO BARS : "
                f"{date_text} {code}"
            )
            continue

        current_start = evaluation_start(
            date_text,
            str(row["SnapshotTime"]),
        )

        result = evaluate_trade(
            bars,
            float(snapshot_price),
            current_start,
        )

        add_result(
            output,
            row,
            "CURRENT",
            float(snapshot_price),
            current_start,
            result,
        )

        for hhmm in WAIT_TIMES:
            entry_price, start_time = (
                get_wait_entry(
                    bars,
                    date_text,
                    hhmm,
                )
            )

            if entry_price is None:
                add_result(
                    output,
                    row,
                    "T" + hhmm.replace(
                        ":",
                        "",
                    ),
                    pd.NA,
                    None,
                    None,
                )
                continue

            result = evaluate_trade(
                bars,
                entry_price,
                start_time,
            )

            add_result(
                output,
                row,
                "T" + hhmm.replace(
                    ":",
                    "",
                ),
                entry_price,
                start_time,
                result,
            )

        for dip_pct in [1, 2]:
            entry_price, start_time = (
                get_dip_entry(
                    bars,
                    float(snapshot_price),
                    current_start,
                    dip_pct,
                )
            )

            method = f"DIP{dip_pct}"

            if entry_price is None:
                add_result(
                    output,
                    row,
                    method,
                    pd.NA,
                    None,
                    None,
                )
                continue

            result = evaluate_trade(
                bars,
                entry_price,
                start_time,
            )

            add_result(
                output,
                row,
                method,
                entry_price,
                start_time,
                result,
            )

    result_df = pd.DataFrame(
        output
    )

    if result_df.empty:
        print("No results")
        return

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print_summary(result_df)

    print()
    print(
        f"Saved : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()