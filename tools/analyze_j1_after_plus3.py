
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


PANEL_PATH = Path(
    "data/analysis/j1_next_open_panel.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/j1_take_compare_520_549.csv"
)

CHANGE_MIN = 5.20
CHANGE_MAX = 5.50

TAKE_LEVELS = [
    2.0,
    3.0,
    4.0,
    5.0,
    7.0,
]

STOP_PCT = -5.0


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


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
            f"DOWNLOAD ERROR "
            f"{code} {date_text} : {exc}"
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
        c in df.columns
        for c in needed
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


def analyze_one(
    bars,
    take_pct,
):
    work = bars.copy()

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
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    if work.empty:
        return None

    entry = float(
        work["Open"].iloc[0]
    )

    take_price = (
        entry
        * (1 + take_pct / 100)
    )

    stop_price = (
        entry
        * (1 + STOP_PCT / 100)
    )

    take_hits = work[
        work["High"] >= take_price
    ]

    stop_hits = work[
        work["Low"] <= stop_price
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
            ret = take_pct

        elif stop_time < take_time:
            exit_type = "STOP"
            ret = STOP_PCT

        else:
            exit_type = "SAME_BAR"
            ret = pd.NA

    elif take_time is not None:
        exit_type = "TAKE"
        ret = take_pct

    elif stop_time is not None:
        exit_type = "STOP"
        ret = STOP_PCT

    else:
        exit_type = "CLOSE"

        ret = (
            float(work["Close"].iloc[-1])
            / entry
            - 1
        ) * 100

    return {
        "ExitType": exit_type,
        "ReturnPct": ret,
        "TakeTime": (
            ""
            if take_time is None
            else pd.Timestamp(
                take_time
            ).strftime("%H:%M")
        ),
        "StopTime": (
            ""
            if stop_time is None
            else pd.Timestamp(
                stop_time
            ).strftime("%H:%M")
        ),
    }



def first_hit_time(work, entry, pct):
    target = entry * (1 + pct / 100)

    hits = work[
        work["High"] >= target
    ]

    if hits.empty:
        return None

    return hits.index[0]


def fmt_time(ts):
    if ts is None:
        return ""

    return pd.Timestamp(
        ts
    ).strftime("%H:%M")


def main():
    compare_path = Path(
        "data/analysis/j1_take_compare_520_549.csv"
    )

    output_path = Path(
        "data/analysis/j1_after_plus3.csv"
    )

    c = pd.read_csv(
        compare_path,
        dtype={"Code": str},
        low_memory=False,
    )

    c["TakeProfitPct"] = pd.to_numeric(
        c["TakeProfitPct"],
        errors="coerce",
    )

    targets = c[
        (c["TakeProfitPct"] == 3)
        & (c["ExitType"] == "TAKE")
    ].copy()

    targets = targets.drop_duplicates(
        subset=[
            "DetectionDate",
            "Code",
        ]
    )

    print("=" * 90)
    print("J1 AFTER +3 ANALYSIS")
    print("=" * 90)
    print("Targets :", len(targets))
    print()

    rows = []

    for _, row in targets.iterrows():

        detection_date = str(
            row["DetectionDate"]
        )

        code = normalize_code(
            row["Code"]
        )

        base = datetime.strptime(
            detection_date,
            "%Y-%m-%d",
        )

        bars = None
        trade_date = None

        for offset in range(1, 8):

            candidate = (
                base
                + timedelta(days=offset)
            )

            if candidate.weekday() >= 5:
                continue

            date_text = (
                candidate.strftime(
                    "%Y-%m-%d"
                )
            )

            candidate_bars = (
                download_5m(
                    code,
                    date_text,
                )
            )

            if (
                candidate_bars is not None
                and not candidate_bars.empty
            ):
                bars = candidate_bars
                trade_date = date_text
                break

        if bars is None:
            print(
                f"NO DATA : "
                f"{detection_date} {code}"
            )
            continue

        work = bars.copy()

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
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )

        if work.empty:
            continue

        entry = float(
            work["Open"].iloc[0]
        )

        t3 = first_hit_time(
            work,
            entry,
            3,
        )

        if t3 is None:
            continue

        t4 = first_hit_time(
            work,
            entry,
            4,
        )

        t5 = first_hit_time(
            work,
            entry,
            5,
        )

        t7 = first_hit_time(
            work,
            entry,
            7,
        )

        t10 = first_hit_time(
            work,
            entry,
            10,
        )

        max_pct = (
            float(work["High"].max())
            / entry
            - 1
        ) * 100

        close_pct = (
            float(work["Close"].iloc[-1])
            / entry
            - 1
        ) * 100

        after3 = work[
            work.index >= t3
        ].copy()

        after3_min_pct = (
            float(after3["Low"].min())
            / entry
            - 1
        ) * 100

        after3_drawdown_pct = (
            after3_min_pct
            - 3.0
        )

        rows.append(
            {
                "DetectionDate":
                    detection_date,
                "TradeDate":
                    trade_date,
                "Code":
                    code,
                "Name":
                    row["Name"],
                "NextOpenGapPct":
                    row["NextOpenGapPct"],
                "EntryPrice":
                    entry,
                "Plus3Time":
                    fmt_time(t3),
                "Plus4Time":
                    fmt_time(t4),
                "Plus5Time":
                    fmt_time(t5),
                "Plus7Time":
                    fmt_time(t7),
                "Plus10Time":
                    fmt_time(t10),
                "MaxPct":
                    max_pct,
                "ClosePct":
                    close_pct,
                "After3MinPct":
                    after3_min_pct,
                "After3DrawdownPct":
                    after3_drawdown_pct,
            }
        )

    out = pd.DataFrame(rows)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 120)
    print("RESULT")
    print("=" * 120)

    if out.empty:
        print("No rows.")
        return

    cols = [
        "DetectionDate",
        "Code",
        "Name",
        "NextOpenGapPct",
        "Plus3Time",
        "Plus4Time",
        "Plus5Time",
        "Plus7Time",
        "Plus10Time",
        "MaxPct",
        "After3MinPct",
        "After3DrawdownPct",
        "ClosePct",
    ]

    print(
        out[cols]
        .round(2)
        .to_string(index=False)
    )

    print()
    print("Saved :", output_path)


if __name__ == "__main__":
    main()
