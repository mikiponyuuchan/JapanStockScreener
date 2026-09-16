from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(
    "data/analysis/short_sale_trigger"
)

PANEL_PATH = (
    BASE_DIR
    / "202606_202608_intraday_5m_panel.csv"
)

CACHE_DIR = (
    BASE_DIR
    / "intraday_5m_cache"
)

OUTPUT_PATH = (
    BASE_DIR
    / "202607_202608_bottom_rebound_panel.csv"
)

SUMMARY_PATH = (
    BASE_DIR
    / "202607_202608_bottom_rebound_summary.csv"
)

TIME_PATH = (
    BASE_DIR
    / "202607_202608_bottom_time_summary.csv"
)


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def to_jst_timestamp(value):
    ts = pd.Timestamp(value)

    if ts.tzinfo is not None:
        try:
            ts = ts.tz_convert(
                "Asia/Tokyo"
            )
        except Exception:
            pass

    return ts


def clock_minutes(value):
    ts = to_jst_timestamp(value)

    return (
        ts.hour * 60
        + ts.minute
    )


def fmt_time(value):
    ts = to_jst_timestamp(value)

    return ts.strftime(
        "%H:%M"
    )


def rv(value):
    if pd.isna(value):
        return np.nan

    return round(
        float(value),
        2,
    )


def rate(series, threshold):
    s = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if s.empty:
        return np.nan

    return round(
        (
            s >= threshold
        ).mean()
        * 100.0,
        1,
    )


def load_cache(code, date_text):
    path = (
        CACHE_DIR
        / f"{date_text}_{code}.csv"
    )

    if not path.exists():
        return None

    try:
        df = pd.read_csv(
            path,
            index_col=0,
            parse_dates=True,
        )
    except Exception:
        return None

    if df.empty:
        return None

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

    for col in needed:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=needed
    )

    if df.empty:
        return None

    return df


def analyze_one(row):
    code = normalize_code(
        row["Code"]
    )

    date_text = str(
        row["NextDate"]
    )[:10]

    df = load_cache(
        code,
        date_text,
    )

    if df is None:
        return None

    entry = float(
        df.iloc[0]["Open"]
    )

    low_pos = (
        df["Low"]
        .astype(float)
        .values
        .argmin()
    )

    low_row = df.iloc[
        low_pos
    ]

    low_time = df.index[
        low_pos
    ]

    low_price = float(
        low_row["Low"]
    )

    after_low = df.iloc[
        low_pos:
    ]

    high_after_pos = (
        after_low["High"]
        .astype(float)
        .values
        .argmax()
    )

    high_after_row = (
        after_low.iloc[
            high_after_pos
        ]
    )

    high_after_time = (
        after_low.index[
            high_after_pos
        ]
    )

    high_after_price = float(
        high_after_row["High"]
    )

    low_from_open = (
        low_price / entry - 1.0
    ) * 100.0

    high_after_low = (
        high_after_price
        / low_price
        - 1.0
    ) * 100.0

    high_after_open = (
        high_after_price
        / entry
        - 1.0
    ) * 100.0

    low_minutes = (
        clock_minutes(low_time)
        - 9 * 60
    )

    low_to_high_minutes = (
        clock_minutes(
            high_after_time
        )
        - clock_minutes(
            low_time
        )
    )

    low_clock = (
        clock_minutes(
            low_time
        )
    )

    if low_clock <= 9 * 60 + 30:
        low_bucket = "<=09:30"
    elif low_clock <= 10 * 60:
        low_bucket = "09:31-10:00"
    elif low_clock <= 10 * 60 + 30:
        low_bucket = "10:01-10:30"
    elif low_clock <= 11 * 60 + 30:
        low_bucket = "10:31-11:30"
    else:
        low_bucket = "AFTER_11:30"

    return {
        "SourceMonth":
            str(row["SourceMonth"]),

        "TriggerDate":
            row["TriggerDate"],

        "Code":
            code,

        "Name":
            row["Name"],

        "TriggerTime":
            row["TriggerTime"],

        "NextDate":
            date_text,

        "NextOpenPct":
            rv(
                row["NextOpenPct"]
            ),

        "EntryOpen":
            rv(entry),

        "DayLowTime":
            fmt_time(
                low_time
            ),

        "MinutesToLow":
            int(low_minutes),

        "LowTimeBucket":
            low_bucket,

        "LowFromOpenPct":
            rv(
                low_from_open
            ),

        "HighAfterLowTime":
            fmt_time(
                high_after_time
            ),

        "MinutesLowToHigh":
            int(
                low_to_high_minutes
            ),

        "HighAfterLowPct":
            rv(
                high_after_low
            ),

        "HighAfterLowFromOpenPct":
            rv(
                high_after_open
            ),

        "LowBy0930":
            low_clock
            <= 9 * 60 + 30,

        "LowBy1000":
            low_clock
            <= 10 * 60,

        "LowBy1030":
            low_clock
            <= 10 * 60 + 30,

        "LowBy1130":
            low_clock
            <= 11 * 60 + 30,
    }


def make_month_summary(df):
    rows = []

    for month in [
        "202607",
        "202608",
        "ALL",
    ]:
        if month == "ALL":
            x = df.copy()
        else:
            x = df[
                df[
                    "SourceMonth"
                ].astype(str)
                == month
            ]

        if x.empty:
            continue

        rows.append(
            {
                "Month":
                    month,

                "N":
                    len(x),

                "MinutesToLowMean":
                    rv(
                        x[
                            "MinutesToLow"
                        ].mean()
                    ),

                "MinutesToLowMedian":
                    rv(
                        x[
                            "MinutesToLow"
                        ].median()
                    ),

                "LowBy0930Rate":
                    round(
                        x[
                            "LowBy0930"
                        ].mean()
                        * 100.0,
                        1,
                    ),

                "LowBy1000Rate":
                    round(
                        x[
                            "LowBy1000"
                        ].mean()
                        * 100.0,
                        1,
                    ),

                "LowBy1030Rate":
                    round(
                        x[
                            "LowBy1030"
                        ].mean()
                        * 100.0,
                        1,
                    ),

                "LowBy1130Rate":
                    round(
                        x[
                            "LowBy1130"
                        ].mean()
                        * 100.0,
                        1,
                    ),

                "LowFromOpenMean":
                    rv(
                        x[
                            "LowFromOpenPct"
                        ].mean()
                    ),

                "LowFromOpenMedian":
                    rv(
                        x[
                            "LowFromOpenPct"
                        ].median()
                    ),

                "HighAfterLowMean":
                    rv(
                        x[
                            "HighAfterLowPct"
                        ].mean()
                    ),

                "HighAfterLowMedian":
                    rv(
                        x[
                            "HighAfterLowPct"
                        ].median()
                    ),

                "Rebound3Rate":
                    rate(
                        x[
                            "HighAfterLowPct"
                        ],
                        3.0,
                    ),

                "Rebound5Rate":
                    rate(
                        x[
                            "HighAfterLowPct"
                        ],
                        5.0,
                    ),

                "Rebound10Rate":
                    rate(
                        x[
                            "HighAfterLowPct"
                        ],
                        10.0,
                    ),

                "MinutesLowToHighMean":
                    rv(
                        x[
                            "MinutesLowToHigh"
                        ].mean()
                    ),

                "MinutesLowToHighMedian":
                    rv(
                        x[
                            "MinutesLowToHigh"
                        ].median()
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def make_time_summary(df):
    order = [
        "<=09:30",
        "09:31-10:00",
        "10:01-10:30",
        "10:31-11:30",
        "AFTER_11:30",
    ]

    rows = []

    for bucket in order:
        x = df[
            df["LowTimeBucket"]
            == bucket
        ]

        if x.empty:
            continue

        rows.append(
            {
                "LowTimeBucket":
                    bucket,

                "N":
                    len(x),

                "LowFromOpenMean":
                    rv(
                        x[
                            "LowFromOpenPct"
                        ].mean()
                    ),

                "HighAfterLowMean":
                    rv(
                        x[
                            "HighAfterLowPct"
                        ].mean()
                    ),

                "HighAfterLowMedian":
                    rv(
                        x[
                            "HighAfterLowPct"
                        ].median()
                    ),

                "Rebound3Rate":
                    rate(
                        x[
                            "HighAfterLowPct"
                        ],
                        3.0,
                    ),

                "Rebound5Rate":
                    rate(
                        x[
                            "HighAfterLowPct"
                        ],
                        5.0,
                    ),

                "Rebound10Rate":
                    rate(
                        x[
                            "HighAfterLowPct"
                        ],
                        10.0,
                    ),

                "MinutesLowToHighMedian":
                    rv(
                        x[
                            "MinutesLowToHigh"
                        ].median()
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def main():
    panel = pd.read_csv(
        PANEL_PATH
    )

    panel = panel[
        panel["Status"]
        == "OK"
    ].copy()

    print("=" * 76)
    print(
        "SHORT SALE TRIGGER "
        "BOTTOM / REBOUND ANALYSIS"
    )
    print("=" * 76)

    print(
        "Cached targets :",
        len(panel),
    )

    rows = []

    for _, row in panel.iterrows():
        result = analyze_one(
            row
        )

        if result is not None:
            rows.append(
                result
            )

    df = pd.DataFrame(
        rows
    )

    print(
        "Analyzed       :",
        len(df),
    )

    if df.empty:
        return

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    summary = (
        make_month_summary(
            df
        )
    )

    time_summary = (
        make_time_summary(
            df
        )
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    time_summary.to_csv(
        TIME_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 76)
    print("MONTH SUMMARY")
    print("=" * 76)

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 76)
    print("LOW TIME SUMMARY")
    print("=" * 76)

    print(
        time_summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 76)
    print("SAVED")
    print("=" * 76)

    print(
        "Panel   :",
        OUTPUT_PATH,
    )

    print(
        "Summary :",
        SUMMARY_PATH,
    )

    print(
        "Time    :",
        TIME_PATH,
    )


if __name__ == "__main__":
    main()
