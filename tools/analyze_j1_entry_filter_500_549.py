
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


PANEL_PATH = Path(
    "data/analysis/j1_next_open_panel.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/j1_entry_filter_500_549.csv"
)

CHANGE_MIN = 5.00
CHANGE_MAX = 5.50

TAKE_LEVELS = [
    3.0,
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


def main():
    df = pd.read_csv(
        PANEL_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    for col in [
        "Change1",
        "NextOpenGapPct",
        "EntryDayHighPct",
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    x = df[
        df["EntryDayHighPct"].notna()
        & (df["Change1"] >= CHANGE_MIN)
        & (df["Change1"] < CHANGE_MAX)
    ].copy()

    x["Code"] = (
        x["Code"]
        .map(normalize_code)
    )

    print("=" * 80)
    print(
        "J1 TAKE COMPARISON "
        "Change1 5.20-5.49"
    )
    print("=" * 80)

    print("Targets :", len(x))
    print()

    rows = []

    for _, row in x.iterrows():

        detection_date = str(
            row["DetectionDate"]
        )

        code = row["Code"]

        base = datetime.strptime(
            detection_date,
            "%Y-%m-%d",
        )

        bars = None
        trade_date = None

        # Search only weekdays.
        # This avoids unnecessary Yahoo
        # requests for Saturday/Sunday.
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

        print(
            f"{detection_date} "
            f"{code} "
            f"{row['Name']}"
        )

        for take_pct in TAKE_LEVELS:

            result = analyze_one(
                bars,
                take_pct,
            )

            if result is None:
                continue

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
                    "Change1":
                        row["Change1"],
                    "NextOpenGapPct":
                        row["NextOpenGapPct"],
                    "TakeProfitPct":
                        take_pct,
                    "StopLossPct":
                        STOP_PCT,
                    "ExitType":
                        result[
                            "ExitType"
                        ],
                    "ReturnPct":
                        result[
                            "ReturnPct"
                        ],
                    "TakeTime":
                        result[
                            "TakeTime"
                        ],
                    "StopTime":
                        result[
                            "StopTime"
                        ],
                }
            )

    out = pd.DataFrame(rows)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)

    for take_pct in TAKE_LEVELS:

        g = out[
            out["TakeProfitPct"]
            == take_pct
        ].copy()

        ret = pd.to_numeric(
            g["ReturnPct"],
            errors="coerce",
        ).dropna()

        counts = (
            g["ExitType"]
            .value_counts()
        )

        print()
        print(
            f"TP +{take_pct:.0f} / SL -5"
        )

        print("N        :", len(g))

        print(
            "TAKE     :",
            int(
                counts.get(
                    "TAKE",
                    0,
                )
            ),
        )

        print(
            "STOP     :",
            int(
                counts.get(
                    "STOP",
                    0,
                )
            ),
        )

        print(
            "CLOSE    :",
            int(
                counts.get(
                    "CLOSE",
                    0,
                )
            ),
        )

        print(
            "SAME_BAR :",
            int(
                counts.get(
                    "SAME_BAR",
                    0,
                )
            ),
        )

        if len(ret):

            print(
                "Win rate :",
                f"{(ret > 0).mean() * 100:.1f}%"
            )

            print(
                "Mean     :",
                f"{ret.mean():.2f}%"
            )

            print(
                "Median   :",
                f"{ret.median():.2f}%"
            )

            print(
                "Total    :",
                f"{ret.sum():.2f}%"
            )

    print()
    print(
        "Saved    :",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()


