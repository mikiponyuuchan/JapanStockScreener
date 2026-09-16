import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


BASE_DIR = Path(
    "data/analysis/short_sale_trigger"
)

CACHE_DIR = (
    BASE_DIR
    / "intraday_5m_cache"
)

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


TP_SL_CASES = [
    (3.0, -3.0),
    (5.0, -3.0),
    (3.0, -5.0),
    (5.0, -5.0),
]


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def flatten_columns(df):
    if not isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        return df

    cols = []

    for col in df.columns:
        if isinstance(col, tuple):
            cols.append(col[0])
        else:
            cols.append(col)

    df = df.copy()
    df.columns = cols

    return df


def download_5m(code, date_text):
    cache_path = (
        CACHE_DIR
        / f"{date_text}_{code}.csv"
    )

    if cache_path.exists():
        try:
            cached = pd.read_csv(
                cache_path,
                index_col=0,
                parse_dates=True,
            )

            if not cached.empty:
                return cached

        except Exception:
            pass

    ticker = f"{code}.T"

    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    end = start + timedelta(days=1)

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

    except Exception:
        return None

    if df is None or df.empty:
        return None

    df = flatten_columns(df)

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

    df = df[needed].copy()

    df = df.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    if df.empty:
        return None

    df.to_csv(
        cache_path,
        encoding="utf-8-sig",
    )

    return df


def intraday_clock(index_value):
    ts = pd.Timestamp(index_value)

    if ts.tzinfo is not None:
        try:
            ts = ts.tz_convert(
                "Asia/Tokyo"
            )
        except Exception:
            pass

    return ts.hour * 60 + ts.minute


def calc_window(df, entry, end_minutes):
    use = df[
        [
            intraday_clock(idx)
            <= end_minutes
            for idx in df.index
        ]
    ]

    if use.empty:
        return (
            np.nan,
            np.nan,
        )

    high_pct = (
        float(use["High"].max())
        / entry
        - 1.0
    ) * 100.0

    low_pct = (
        float(use["Low"].min())
        / entry
        - 1.0
    ) * 100.0

    return (
        round(high_pct, 2),
        round(low_pct, 2),
    )


def judge_tp_sl(
    df,
    entry,
    tp_pct,
    sl_pct,
):
    tp_price = (
        entry
        * (
            1.0
            + tp_pct / 100.0
        )
    )

    sl_price = (
        entry
        * (
            1.0
            + sl_pct / 100.0
        )
    )

    for idx, row in df.iterrows():
        high = float(row["High"])
        low = float(row["Low"])

        tp_hit = high >= tp_price
        sl_hit = low <= sl_price

        if tp_hit and sl_hit:
            return (
                "SAME_BAR",
                str(idx),
            )

        if tp_hit:
            return (
                "TP",
                str(idx),
            )

        if sl_hit:
            return (
                "SL",
                str(idx),
            )

    return (
        "NONE",
        "",
    )


def build_targets(months):
    frames = []

    for month in months:
        path = (
            BASE_DIR
            / (
                f"{month}_"
                "short_sale_trigger_panel.csv"
            )
        )

        if not path.exists():
            print(
                "Missing:",
                path,
            )
            continue

        df = pd.read_csv(path)

        df["Code"] = (
            df["Code"]
            .map(normalize_code)
        )

        next_open = pd.to_numeric(
            df["NextOpenPct"],
            errors="coerce",
        )

        target = df[
            next_open <= -5.0
        ].copy()

        target["SourceMonth"] = month

        frames.append(target)

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        ignore_index=True,
    )


def summarize_case(
    result,
    column,
):
    valid = result[
        result[column].isin(
            [
                "TP",
                "SL",
                "SAME_BAR",
                "NONE",
            ]
        )
    ]

    n = len(valid)

    if n == 0:
        return {
            "Case": column,
            "N": 0,
        }

    counts = (
        valid[column]
        .value_counts()
    )

    return {
        "Case": column,
        "N": n,
        "TP":
            int(counts.get("TP", 0)),
        "SL":
            int(counts.get("SL", 0)),
        "SAME_BAR":
            int(
                counts.get(
                    "SAME_BAR",
                    0,
                )
            ),
        "NONE":
            int(
                counts.get(
                    "NONE",
                    0,
                )
            ),
        "TPRate":
            round(
                (
                    valid[column]
                    == "TP"
                ).mean()
                * 100.0,
                1,
            ),
        "SLRate":
            round(
                (
                    valid[column]
                    == "SL"
                ).mean()
                * 100.0,
                1,
            ),
        "SameBarRate":
            round(
                (
                    valid[column]
                    == "SAME_BAR"
                ).mean()
                * 100.0,
                1,
            ),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--months",
        nargs="+",
        default=[
            "202606",
            "202607",
            "202608",
        ],
    )

    args = parser.parse_args()

    targets = build_targets(
        args.months
    )

    print("=" * 76)
    print(
        "SHORT SALE TRIGGER "
        "INTRADAY 5M"
    )
    print("=" * 76)
    print(
        "Target rule : "
        "NextOpenPct <= -5%"
    )
    print(
        "Daily targets:",
        len(targets),
    )

    if targets.empty:
        return

    rows = []

    total = len(targets)

    success = 0
    unavailable = 0

    for i, row in targets.iterrows():
        code = normalize_code(
            row["Code"]
        )

        trade_date = str(
            row["NextDate"]
        )[:10]

        bars = download_5m(
            code,
            trade_date,
        )

        out = {
            "SourceMonth":
                row["SourceMonth"],
            "TriggerDate":
                row["TriggerDate"],
            "Code":
                code,
            "Name":
                row["Name"],
            "TriggerTime":
                row["TriggerTime"],
            "NextDate":
                trade_date,
            "NextOpenPct":
                row["NextOpenPct"],
            "DailyHighFromOpenPct":
                row[
                    "NextHighFromOpenPct"
                ],
            "DailyLowFromOpenPct":
                row[
                    "NextLowFromOpenPct"
                ],
            "Status":
                "",
        }

        if bars is None or bars.empty:
            out["Status"] = (
                "5M_UNAVAILABLE"
            )

            unavailable += 1
            rows.append(out)

        else:
            success += 1

            entry = float(
                bars.iloc[0]["Open"]
            )

            out["Status"] = "OK"
            out["EntryOpen5m"] = (
                round(entry, 2)
            )

            for label, minutes in [
                ("0930", 9 * 60 + 30),
                ("1000", 10 * 60),
                ("1130", 11 * 60 + 30),
                ("1530", 15 * 60 + 30),
            ]:
                high_pct, low_pct = (
                    calc_window(
                        bars,
                        entry,
                        minutes,
                    )
                )

                out[
                    f"HighTo{label}Pct"
                ] = high_pct

                out[
                    f"LowTo{label}Pct"
                ] = low_pct

            for tp, sl in TP_SL_CASES:
                key = (
                    f"TP{int(tp)}_"
                    f"SL{abs(int(sl))}"
                )

                result, hit_time = (
                    judge_tp_sl(
                        bars,
                        entry,
                        tp,
                        sl,
                    )
                )

                out[key] = result
                out[
                    f"{key}_Time"
                ] = hit_time

            rows.append(out)

        done = i + 1

        if (
            done % 20 == 0
            or done == total
        ):
            print(
                f"Analyze : "
                f"{done}/{total} "
                f"OK={success} "
                f"Unavailable="
                f"{unavailable}"
            )

        time.sleep(0.15)

    result = pd.DataFrame(rows)

    output_path = (
        BASE_DIR
        / (
            "202606_202608_"
            "intraday_5m_panel.csv"
        )
    )

    result.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 76)
    print("5M AVAILABILITY")
    print("=" * 76)
    print(
        result["Status"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    ok = result[
        result["Status"] == "OK"
    ].copy()

    if not ok.empty:
        summaries = []

        for tp, sl in TP_SL_CASES:
            key = (
                f"TP{int(tp)}_"
                f"SL{abs(int(sl))}"
            )

            summaries.append(
                summarize_case(
                    ok,
                    key,
                )
            )

        summary = pd.DataFrame(
            summaries
        )

        summary_path = (
            BASE_DIR
            / (
                "202606_202608_"
                "intraday_5m_summary.csv"
            )
        )

        summary.to_csv(
            summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        print()
        print("=" * 76)
        print("TP / SL FIRST HIT")
        print("=" * 76)
        print(
            summary.to_string(
                index=False
            )
        )

        print()
        print("=" * 76)
        print("TIME WINDOW")
        print("=" * 76)

        window_rows = []

        for label in [
            "0930",
            "1000",
            "1130",
            "1530",
        ]:
            high_col = (
                f"HighTo{label}Pct"
            )

            low_col = (
                f"LowTo{label}Pct"
            )

            high = pd.to_numeric(
                ok[high_col],
                errors="coerce",
            )

            low = pd.to_numeric(
                ok[low_col],
                errors="coerce",
            )

            window_rows.append(
                {
                    "Window":
                        label,
                    "N":
                        int(
                            high.notna()
                            .sum()
                        ),
                    "HighMean":
                        round(
                            high.mean(),
                            2,
                        ),
                    "HighMedian":
                        round(
                            high.median(),
                            2,
                        ),
                    "High3Rate":
                        round(
                            (
                                high >= 3.0
                            ).mean()
                            * 100.0,
                            1,
                        ),
                    "High5Rate":
                        round(
                            (
                                high >= 5.0
                            ).mean()
                            * 100.0,
                            1,
                        ),
                    "LowMean":
                        round(
                            low.mean(),
                            2,
                        ),
                    "LowMedian":
                        round(
                            low.median(),
                            2,
                        ),
                }
            )

        window_df = pd.DataFrame(
            window_rows
        )

        window_path = (
            BASE_DIR
            / (
                "202606_202608_"
                "intraday_5m_window.csv"
            )
        )

        window_df.to_csv(
            window_path,
            index=False,
            encoding="utf-8-sig",
        )

        print(
            window_df.to_string(
                index=False
            )
        )

        print()
        print("Summary :", summary_path)
        print("Window  :", window_path)

    print()
    print("Panel   :", output_path)


if __name__ == "__main__":
    main()
