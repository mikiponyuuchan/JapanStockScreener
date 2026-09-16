from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path("data/analysis/short_sale_trigger")

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
    / "202607_202608_0930_reversal_panel.csv"
)

SUMMARY_PATH = (
    BASE_DIR
    / "202607_202608_0930_reversal_summary.csv"
)


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def to_jst(value):
    ts = pd.Timestamp(value)

    if ts.tzinfo is not None:
        try:
            ts = ts.tz_convert("Asia/Tokyo")
        except Exception:
            pass

    return ts


def clock_minutes(value):
    ts = to_jst(value)
    return ts.hour * 60 + ts.minute


def fmt_time(value):
    return to_jst(value).strftime("%H:%M")


def rv(value):
    if pd.isna(value):
        return np.nan

    return round(float(value), 2)


def pct(a, b):
    if pd.isna(a) or pd.isna(b):
        return np.nan

    if float(b) == 0:
        return np.nan

    return (
        float(a) / float(b) - 1.0
    ) * 100.0


def rate(series, threshold):
    s = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if s.empty:
        return np.nan

    return round(
        (s >= threshold).mean()
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
        col in df.columns
        for col in needed
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



def judge_tp_sl(df, entry, tp_pct, sl_pct):
    tp_price = entry * (1.0 + tp_pct / 100.0)
    sl_price = entry * (1.0 - sl_pct / 100.0)

    for idx, row in df.iterrows():
        high = float(row["High"])
        low = float(row["Low"])

        hit_tp = high >= tp_price
        hit_sl = low <= sl_price

        if hit_tp and hit_sl:
            return "SAME_BAR"

        if hit_tp:
            return "TP"

        if hit_sl:
            return "SL"

    return "NONE"


def analyze_one(row):
    code = normalize_code(row["Code"])
    date_text = str(row["NextDate"])[:10]

    df = load_cache(
        code,
        date_text,
    )

    if df is None:
        return None

    minutes = pd.Series(
        [
            clock_minutes(x)
            for x in df.index
        ],
        index=df.index,
    )

    # Yahoo 5m timestamps represent the start of each bar.
    # At exactly 09:30, the 09:30 bar is not completed yet.
    # Therefore use only bars starting before 09:30.
    morning = df[
        (minutes >= 9 * 60)
        & (minutes < 9 * 60 + 30)
    ].copy()

    # Future evaluation starts from the 09:30 bar.
    after = df[
        minutes >= 9 * 60 + 30
    ].copy()

    if morning.empty or after.empty:
        return None

    entry_open = float(
        morning.iloc[0]["Open"]
    )

    low_pos = (
        morning["Low"]
        .astype(float)
        .values
        .argmin()
    )

    low_row = morning.iloc[
        low_pos
    ]

    low_time = morning.index[
        low_pos
    ]

    low_price = float(
        low_row["Low"]
    )

    bar0930 = morning.iloc[-1]
    time0930 = morning.index[-1]

    price0930 = float(
        bar0930["Close"]
    )

    low_from_open = pct(
        low_price,
        entry_open,
    )

    rebound_to_0930 = pct(
        price0930,
        low_price,
    )

    price0930_from_open = pct(
        price0930,
        entry_open,
    )

    minutes_since_low = (
        clock_minutes(time0930)
        - clock_minutes(low_time)
    )

    after_high = float(
        after["High"].max()
    )

    after_low = float(
        after["Low"].min()
    )

    after_close = float(
        after.iloc[-1]["Close"]
    )

    # 09:30 bar Open is the tradable reference price
    # available at the start of the 09:30 bar.
    entry0930 = float(
        after.iloc[0]["Open"]
    )

    # All post-09:30 performance metrics use the same
    # tradable 09:30 Open reference.
    after_high_pct = pct(
        after_high,
        entry0930,
    )

    after_low_pct = pct(
        after_low,
        entry0930,
    )

    after_close_pct = pct(
        after_close,
        entry0930,
    )

    tp3_sl3 = judge_tp_sl(
        after,
        entry0930,
        3.0,
        3.0,
    )

    tp5_sl3 = judge_tp_sl(
        after,
        entry0930,
        5.0,
        3.0,
    )

    tp3_sl5 = judge_tp_sl(
        after,
        entry0930,
        3.0,
        5.0,
    )

    tp5_sl5 = judge_tp_sl(
        after,
        entry0930,
        5.0,
        5.0,
    )

    return {
        "SourceMonth":
            str(row["SourceMonth"]),

        "TriggerDate":
            row["TriggerDate"],

        "Code":
            code,

        "Name":
            row["Name"],

        "NextDate":
            date_text,

        "NextOpenPct":
            rv(row["NextOpenPct"]),

        "Open5m":
            rv(entry_open),

        "LowTo0930Time":
            fmt_time(low_time),

        "LowTo0930FromOpenPct":
            rv(low_from_open),

        "Price0930":
            rv(price0930),

        "ReboundLowTo0930Pct":
            rv(rebound_to_0930),

        "Price0930FromOpenPct":
            rv(price0930_from_open),

        "MinutesSinceLow":
            int(minutes_since_low),

        "After0930HighPct":
            rv(after_high_pct),

        "After0930LowPct":
            rv(after_low_pct),

        "After0930ClosePct":
            rv(after_close_pct),

        "Entry0930":
            rv(entry0930),

        "TP3_SL3":
            tp3_sl3,

        "TP5_SL3":
            tp5_sl3,

        "TP3_SL5":
            tp3_sl5,

        "TP5_SL5":
            tp5_sl5,
    }


def summarize_group(name, x):
    if x.empty:
        return None

    return {
        "Group":
            name,

        "N":
            len(x),

        "MorningLowMean":
            rv(
                x[
                    "LowTo0930FromOpenPct"
                ].mean()
            ),

        "MorningLowMedian":
            rv(
                x[
                    "LowTo0930FromOpenPct"
                ].median()
            ),

        "Rebound0930Mean":
            rv(
                x[
                    "ReboundLowTo0930Pct"
                ].mean()
            ),

        "Rebound0930Median":
            rv(
                x[
                    "ReboundLowTo0930Pct"
                ].median()
            ),

        "MinutesSinceLowMedian":
            rv(
                x[
                    "MinutesSinceLow"
                ].median()
            ),

        "AfterHighMean":
            rv(
                x[
                    "After0930HighPct"
                ].mean()
            ),

        "AfterHighMedian":
            rv(
                x[
                    "After0930HighPct"
                ].median()
            ),

        "AfterHigh3Rate":
            rate(
                x[
                    "After0930HighPct"
                ],
                3.0,
            ),

        "AfterHigh5Rate":
            rate(
                x[
                    "After0930HighPct"
                ],
                5.0,
            ),

        "AfterHigh10Rate":
            rate(
                x[
                    "After0930HighPct"
                ],
                10.0,
            ),

        "AfterLowMean":
            rv(
                x[
                    "After0930LowPct"
                ].mean()
            ),

        "AfterLowMedian":
            rv(
                x[
                    "After0930LowPct"
                ].median()
            ),

        "AfterCloseMean":
            rv(
                x[
                    "After0930ClosePct"
                ].mean()
            ),

        "AfterCloseMedian":
            rv(
                x[
                    "After0930ClosePct"
                ].median()
            ),
    }


def make_summary(df):
    rows = []

    groups = [
        (
            "ALL",
            df,
        ),
        (
            "202607",
            df[
                df["SourceMonth"]
                .astype(str)
                == "202607"
            ],
        ),
        (
            "202608",
            df[
                df["SourceMonth"]
                .astype(str)
                == "202608"
            ],
        ),
        (
            "Rebound<2",
            df[
                df[
                    "ReboundLowTo0930Pct"
                ]
                < 2.0
            ],
        ),
        (
            "Rebound2-5",
            df[
                (
                    df[
                        "ReboundLowTo0930Pct"
                    ]
                    >= 2.0
                )
                &
                (
                    df[
                        "ReboundLowTo0930Pct"
                    ]
                    < 5.0
                )
            ],
        ),
        (
            "Rebound>=5",
            df[
                df[
                    "ReboundLowTo0930Pct"
                ]
                >= 5.0
            ],
        ),
        (
            "LowAge0-5",
            df[
                df["MinutesSinceLow"]
                <= 5
            ],
        ),
        (
            "LowAge10-20",
            df[
                (
                    df["MinutesSinceLow"]
                    >= 10
                )
                &
                (
                    df["MinutesSinceLow"]
                    <= 20
                )
            ],
        ),
        (
            "LowAge>=25",
            df[
                df["MinutesSinceLow"]
                >= 25
            ],
        ),
    ]

    for name, x in groups:
        row = summarize_group(
            name,
            x,
        )

        if row is not None:
            rows.append(row)

    return pd.DataFrame(rows)




def realized_return(result, tp_pct, sl_pct, close_pct):
    if result == "TP":
        return float(tp_pct)

    if result == "SL":
        return -float(sl_pct)

    if result == "NONE":
        return float(close_pct)

    return np.nan


def make_tp_sl_summary(df):
    rows = []

    cases = [
        "TP3_SL3",
        "TP5_SL3",
        "TP3_SL5",
        "TP5_SL5",
    ]

    groups = [
        ("ALL", df),
        (
            "202607",
            df[
                df["SourceMonth"].astype(str)
                == "202607"
            ],
        ),
        (
            "202608",
            df[
                df["SourceMonth"].astype(str)
                == "202608"
            ],
        ),
    ]

    for group_name, x in groups:
        if x.empty:
            continue

        for case in cases:
            counts = (
                x[case]
                .value_counts()
            )

            n = len(x)

            tp = int(
                counts.get("TP", 0)
            )

            sl = int(
                counts.get("SL", 0)
            )

            same_bar = int(
                counts.get(
                    "SAME_BAR",
                    0,
                )
            )

            none = int(
                counts.get("NONE", 0)
            )

            rows.append(
                {
                    "Group":
                        group_name,

                    "Case":
                        case,

                    "N":
                        n,

                    "TP":
                        tp,

                    "SL":
                        sl,

                    "SAME_BAR":
                        same_bar,

                    "NONE":
                        none,

                    "TPRate":
                        round(
                            tp / n
                            * 100.0,
                            1,
                        ),

                    "SLRate":
                        round(
                            sl / n
                            * 100.0,
                            1,
                        ),

                    "SameBarRate":
                        round(
                            same_bar / n
                            * 100.0,
                            1,
                        ),
                }
            )

    return pd.DataFrame(rows)



def make_realized_summary(df):
    rows = []

    cases = [
        ("TP3_SL3", 3.0, 3.0),
        ("TP5_SL3", 5.0, 3.0),
        ("TP3_SL5", 3.0, 5.0),
        ("TP5_SL5", 5.0, 5.0),
    ]

    groups = [
        ("ALL", df),
        (
            "202607",
            df[
                df["SourceMonth"].astype(str)
                == "202607"
            ],
        ),
        (
            "202608",
            df[
                df["SourceMonth"].astype(str)
                == "202608"
            ],
        ),
    ]

    for group_name, x in groups:
        if x.empty:
            continue

        for case, tp_pct, sl_pct in cases:
            col = f"{case}_ReturnPct"

            s = pd.to_numeric(
                x[col],
                errors="coerce",
            ).dropna()

            if s.empty:
                continue

            rows.append(
                {
                    "Group":
                        group_name,

                    "Case":
                        case,

                    "N":
                        len(s),

                    "MeanReturn":
                        round(
                            s.mean(),
                            2,
                        ),

                    "MedianReturn":
                        round(
                            s.median(),
                            2,
                        ),

                    "WinRate":
                        round(
                            (s > 0).mean()
                            * 100.0,
                            1,
                        ),

                    "LossRate":
                        round(
                            (s < 0).mean()
                            * 100.0,
                            1,
                        ),

                    "FlatRate":
                        round(
                            (s == 0).mean()
                            * 100.0,
                            1,
                        ),

                    "TotalReturn":
                        round(
                            s.sum(),
                            2,
                        ),

                    "BestReturn":
                        round(
                            s.max(),
                            2,
                        ),

                    "WorstReturn":
                        round(
                            s.min(),
                            2,
                        ),
                }
            )

    return pd.DataFrame(rows)


def main():
    panel = pd.read_csv(
        PANEL_PATH
    )

    panel = panel[
        panel["Status"]
        == "OK"
    ].copy()

    print("=" * 78)
    print(
        "SHORT SALE TRIGGER "
        "09:30 REVERSAL ANALYSIS"
    )
    print("=" * 78)

    print(
        "Cached targets :",
        len(panel),
    )

    rows = []

    for _, row in panel.iterrows():
        result = analyze_one(row)

        if result is not None:
            rows.append(result)

    df = pd.DataFrame(rows)

    print(
        "Analyzed       :",
        len(df),
    )

    if df.empty:
        return

    realized_cases = [
        ("TP3_SL3", 3.0, 3.0),
        ("TP5_SL3", 5.0, 3.0),
        ("TP3_SL5", 3.0, 5.0),
        ("TP5_SL5", 5.0, 5.0),
    ]

    for case, tp_pct, sl_pct in realized_cases:
        col = f"{case}_ReturnPct"

        df[col] = df.apply(
            lambda r: realized_return(
                r[case],
                tp_pct,
                sl_pct,
                r["After0930ClosePct"],
            ),
            axis=1,
        )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    summary = make_summary(df)

    tp_sl_summary = make_tp_sl_summary(
        df
    )

    realized_summary = make_realized_summary(
        df
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 78)
    print("09:30 SUMMARY")
    print("=" * 78)

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 78)
    print("09:30 TP / SL FIRST HIT")
    print("=" * 78)

    print(
        tp_sl_summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 78)
    print("09:30 REALIZED RETURN")
    print("=" * 78)

    print(
        realized_summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 78)
    print("SAVED")
    print("=" * 78)

    print(
        "Panel   :",
        OUTPUT_PATH,
    )

    print(
        "Summary :",
        SUMMARY_PATH,
    )


if __name__ == "__main__":
    main()
