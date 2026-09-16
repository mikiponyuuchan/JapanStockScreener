
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


PANEL_PATH = Path(
    "data/analysis/j1_next_open_panel.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/j1_real_trade_520_549.csv"
)

CHANGE_MIN = 5.20
CHANGE_MAX = 5.50

TAKE_PCT = 3.0
STOP_PCT = -3.0


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def download_5m(
    code,
    date_text,
):
    ticker = f"{code}.T"

    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    end = (
        start
        + timedelta(days=1)
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
            interval="5m",
            progress=False,
            auto_adjust=False,
            threads=False,
        )

    except Exception as exc:
        print(
            f"DOWNLOAD ERROR "
            f"{code} "
            f"{date_text} : "
            f"{exc}"
        )
        return None

    if (
        df is None
        or df.empty
    ):
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


def time_text(ts):
    if ts is None:
        return ""

    return pd.Timestamp(
        ts
    ).strftime(
        "%H:%M"
    )


def analyze_trade(
    bars,
):
    if (
        bars is None
        or bars.empty
    ):
        return None

    work = bars.copy()

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

    open_ = pd.to_numeric(
        work["Open"],
        errors="coerce",
    )

    valid = (
        high.notna()
        & low.notna()
        & close.notna()
        & open_.notna()
    )

    work = work[
        valid
    ].copy()

    if work.empty:
        return None

    open_ = pd.to_numeric(
        work["Open"],
        errors="coerce",
    )

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

    entry_price = float(
        open_.iloc[0]
    )

    take_price = (
        entry_price
        * (1.0 + TAKE_PCT / 100)
    )

    stop_price = (
        entry_price
        * (1.0 + STOP_PCT / 100)
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
            last_close
            / entry_price
            - 1.0
        ) * 100

    max_high_pct = (
        float(high.max())
        / entry_price
        - 1.0
    ) * 100

    min_low_pct = (
        float(low.min())
        / entry_price
        - 1.0
    ) * 100

    last_close = float(
        close.iloc[-1]
    )

    close_pct = (
        last_close
        / entry_price
        - 1.0
    ) * 100

    return {
        "EntryPrice":
            entry_price,
        "TakePrice":
            take_price,
        "StopPrice":
            stop_price,
        "HitPlus3Time":
            time_text(
                take_time
            ),
        "HitMinus3Time":
            time_text(
                stop_time
            ),
        "ExitType":
            exit_type,
        "ReturnPct":
            return_pct,
        "MaxHighPct":
            max_high_pct,
        "MinLowPct":
            min_low_pct,
        "ClosePct":
            close_pct,
    }


def main():
    if not PANEL_PATH.exists():
        print(
            f"Not found : "
            f"{PANEL_PATH}"
        )
        return

    df = pd.read_csv(
        PANEL_PATH,
        dtype={
            "Code": str,
        },
        low_memory=False,
    )

    required = [
        "DetectionDate",
        "Code",
        "Name",
        "Change1",
        "DetectionVolumeVsPre5",
        "NextOpenGapPct",
        "EntryDayHighPct",
    ]

    missing = [
        c
        for c in required
        if c not in df.columns
    ]

    if missing:
        print(
            "Missing columns : "
            + ", ".join(
                missing
            )
        )
        return

    for c in [
        "Change1",
        "DetectionVolumeVsPre5",
        "NextOpenGapPct",
        "EntryDayHighPct",
    ]:
        df[c] = pd.to_numeric(
            df[c],
            errors="coerce",
        )

    x = df[
        df["EntryDayHighPct"]
        .notna()
        & (
            df["Change1"]
            >= CHANGE_MIN
        )
        & (
            df["Change1"]
            < CHANGE_MAX
        )
    ].copy()

    if x.empty:
        print(
            "No target rows."
        )
        return

    x["Code"] = (
        x["Code"]
        .map(
            normalize_code
        )
    )

    rows = []

    cache = {}

    for _, row in x.iterrows():

        detection_date = str(
            row[
                "DetectionDate"
            ]
        ).strip()

        code = normalize_code(
            row["Code"]
        )

        # Day1 is the next trading day.
        # Use the actual confirmed date
        # already represented in the panel.
        # Search forward up to 7 calendar days.
        base = datetime.strptime(
            detection_date,
            "%Y-%m-%d",
        )

        trade_date = None
        bars = None

        for offset in range(
            1,
            8,
        ):
            candidate = (
                base
                + timedelta(
                    days=offset
                )
            )

            candidate_text = (
                candidate.strftime(
                    "%Y-%m-%d"
                )
            )

            key = (
                code,
                candidate_text,
            )

            if key not in cache:
                cache[key] = (
                    download_5m(
                        code,
                        candidate_text,
                    )
                )

            candidate_bars = (
                cache[key]
            )

            if (
                candidate_bars
                is not None
                and not
                candidate_bars.empty
            ):
                trade_date = (
                    candidate_text
                )
                bars = (
                    candidate_bars
                )
                break

        if (
            trade_date is None
            or bars is None
        ):
            print(
                f"NO DATA : "
                f"{detection_date} "
                f"{code}"
            )
            continue

        result = (
            analyze_trade(
                bars
            )
        )

        if result is None:
            print(
                f"NO BARS : "
                f"{detection_date} "
                f"{code}"
            )
            continue

        out = {
            "DetectionDate":
                detection_date,
            "TradeDate":
                trade_date,
            "Code":
                code,
            "Name":
                row["Name"],
            "Change1":
                row["Change1"],
            "DetectionVolumeVsPre5":
                row[
                    "DetectionVolumeVsPre5"
                ],
            "NextOpenGapPct":
                row[
                    "NextOpenGapPct"
                ],
        }

        out.update(
            result
        )

        rows.append(
            out
        )

        print(
            f"{detection_date} "
            f"{code} "
            f"{result['ExitType']} "
            f"{result['ReturnPct']}"
        )

    if not rows:
        print(
            "No completed trades."
        )
        return

    out_df = pd.DataFrame(
        rows
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print(
        "J1 REAL TRADE "
        "5.20-5.49"
    )
    print("=" * 70)

    print(
        "Total       :",
        len(out_df),
    )

    counts = (
        out_df["ExitType"]
        .value_counts()
    )

    for name in [
        "TAKE",
        "STOP",
        "CLOSE",
        "SAME_BAR",
    ]:
        print(
            f"{name:11s}:",
            int(
                counts.get(
                    name,
                    0,
                )
            ),
        )

    ret = pd.to_numeric(
        out_df["ReturnPct"],
        errors="coerce",
    ).dropna()

    print()
    print(
        "Valid return:",
        len(ret),
    )

    if len(ret):

        print(
            "Win rate    :",
            f"{(ret > 0).mean() * 100:.1f}%",
        )

        print(
            "Mean return :",
            f"{ret.mean():.2f}%",
        )

        print(
            "Median      :",
            f"{ret.median():.2f}%",
        )

        print(
            "Total return:",
            f"{ret.sum():.2f}%",
        )

    print()
    print(
        "Saved       :",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()
