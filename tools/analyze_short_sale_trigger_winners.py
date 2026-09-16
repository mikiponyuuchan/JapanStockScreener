import argparse
from pathlib import Path

import numpy as np
import pandas as pd


SOURCE_DIR = Path("data/analysis/short_sale_trigger")


def rv(value):
    if pd.isna(value):
        return np.nan
    return round(float(value), 2)


def rate(series, condition):
    s = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if s.empty:
        return np.nan

    return round(
        condition(s).mean() * 100.0,
        1,
    )


def summarize_group(group):
    return {
        "N":
            len(group),

        "DayChangeMean":
            rv(group["DayChangePct"].mean()),

        "DayChangeMedian":
            rv(group["DayChangePct"].median()),

        "LowPctMean":
            rv(group["LowPct"].mean()),

        "LowPctMedian":
            rv(group["LowPct"].median()),

        "LowToCloseMean":
            rv(group["LowToClosePct"].mean()),

        "LowToCloseMedian":
            rv(group["LowToClosePct"].median()),

        "NextOpenMean":
            rv(group["NextOpenPct"].mean()),

        "NextOpenMedian":
            rv(group["NextOpenPct"].median()),

        "NextOpenGD0Rate":
            rate(
                group["NextOpenPct"],
                lambda s: s < 0,
            ),

        "NextOpenGD3Rate":
            rate(
                group["NextOpenPct"],
                lambda s: s <= -3,
            ),

        "NextOpenGD5Rate":
            rate(
                group["NextOpenPct"],
                lambda s: s <= -5,
            ),

        "NextHighFromOpenMean":
            rv(
                group[
                    "NextHighFromOpenPct"
                ].mean()
            ),

        "NextLowFromOpenMean":
            rv(
                group[
                    "NextLowFromOpenPct"
                ].mean()
            ),

        "NextCloseFromOpenMean":
            rv(
                group[
                    "NextCloseFromOpenPct"
                ].mean()
            ),
    }


def compare_winners(df, level):
    valid = df[
        pd.to_numeric(
            df["NextHighFromOpenPct"],
            errors="coerce",
        ).notna()
    ].copy()

    high = pd.to_numeric(
        valid["NextHighFromOpenPct"],
        errors="coerce",
    )

    winner = valid[
        high >= level
    ]

    non_winner = valid[
        high < level
    ]

    rows = []

    for label, group in [
        ("WINNER", winner),
        ("NON_WINNER", non_winner),
    ]:
        row = {
            "Target":
                f"+{level:.0f}",
            "Group":
                label,
        }

        row.update(
            summarize_group(group)
        )

        rows.append(row)

    return pd.DataFrame(rows)


def make_open_band_summary(df):
    work = df.copy()

    open_pct = pd.to_numeric(
        work["NextOpenPct"],
        errors="coerce",
    )

    work["OpenBand"] = pd.cut(
        open_pct,
        bins=[
            -np.inf,
            -5.0,
            -3.0,
            0.0,
            3.0,
            5.0,
            np.inf,
        ],
        right=False,
        labels=[
            "<=-5",
            "-5-<-3",
            "-3-<0",
            "0-<3",
            "3-<5",
            ">=5",
        ],
    )

    rows = []

    order = [
        "<=-5",
        "-5-<-3",
        "-3-<0",
        "0-<3",
        "3-<5",
        ">=5",
    ]

    for band in order:
        group = work[
            work["OpenBand"].astype(str)
            == band
        ]

        if group.empty:
            continue

        high = pd.to_numeric(
            group["NextHighFromOpenPct"],
            errors="coerce",
        ).dropna()

        low = pd.to_numeric(
            group["NextLowFromOpenPct"],
            errors="coerce",
        ).dropna()

        close = pd.to_numeric(
            group["NextCloseFromOpenPct"],
            errors="coerce",
        ).dropna()

        rows.append(
            {
                "OpenBand":
                    band,
                "N":
                    len(group),

                "NextOpenMean":
                    rv(
                        group[
                            "NextOpenPct"
                        ].mean()
                    ),

                "HighMean":
                    rv(high.mean()),

                "HighMedian":
                    rv(high.median()),

                "High3Rate":
                    round(
                        (high >= 3.0).mean()
                        * 100.0,
                        1,
                    )
                    if not high.empty
                    else np.nan,

                "High5Rate":
                    round(
                        (high >= 5.0).mean()
                        * 100.0,
                        1,
                    )
                    if not high.empty
                    else np.nan,

                "High10Rate":
                    round(
                        (high >= 10.0).mean()
                        * 100.0,
                        1,
                    )
                    if not high.empty
                    else np.nan,

                "LowMean":
                    rv(low.mean()),

                "CloseMean":
                    rv(close.mean()),

                "CloseMedian":
                    rv(close.median()),
            }
        )

    return pd.DataFrame(rows)


def make_time_winner_summary(df):
    rows = []

    order = [
        "09:00-09:59",
        "10:00-12:59",
        "13:00-14:29",
        "14:30-15:30",
    ]

    for bucket in order:
        group = df[
            df["TriggerTimeBucket"]
            == bucket
        ]

        if group.empty:
            continue

        high = pd.to_numeric(
            group["NextHighFromOpenPct"],
            errors="coerce",
        ).dropna()

        rows.append(
            {
                "TriggerTimeBucket":
                    bucket,
                "N":
                    len(group),
                "HighMean":
                    rv(high.mean()),
                "HighMedian":
                    rv(high.median()),
                "High3Rate":
                    round(
                        (high >= 3.0).mean()
                        * 100.0,
                        1,
                    ),
                "High5Rate":
                    round(
                        (high >= 5.0).mean()
                        * 100.0,
                        1,
                    ),
            }
        )

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--month",
        required=True,
        help="YYYYMM",
    )

    args = parser.parse_args()

    panel_path = (
        SOURCE_DIR
        / (
            f"{args.month}_"
            "short_sale_trigger_panel.csv"
        )
    )

    if not panel_path.exists():
        raise SystemExit(
            f"Panel not found: {panel_path}"
        )

    df = pd.read_csv(
        panel_path
    )

    print("=" * 76)
    print("SHORT SALE TRIGGER WINNER ANALYSIS")
    print("=" * 76)
    print("Month :", args.month)
    print("Rows  :", len(df))

    comparison = pd.concat(
        [
            compare_winners(
                df,
                3.0,
            ),
            compare_winners(
                df,
                5.0,
            ),
        ],
        ignore_index=True,
    )

    open_summary = (
        make_open_band_summary(df)
    )

    time_summary = (
        make_time_winner_summary(df)
    )

    comparison_path = (
        SOURCE_DIR
        / (
            f"{args.month}_"
            "winner_comparison.csv"
        )
    )

    open_path = (
        SOURCE_DIR
        / (
            f"{args.month}_"
            "next_open_band_summary.csv"
        )
    )

    time_path = (
        SOURCE_DIR
        / (
            f"{args.month}_"
            "winner_time_summary.csv"
        )
    )

    comparison.to_csv(
        comparison_path,
        index=False,
        encoding="utf-8-sig",
    )

    open_summary.to_csv(
        open_path,
        index=False,
        encoding="utf-8-sig",
    )

    time_summary.to_csv(
        time_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 76)
    print("WINNER VS NON-WINNER")
    print("=" * 76)
    print(
        comparison.to_string(
            index=False
        )
    )

    print()
    print("=" * 76)
    print("NEXT OPEN BAND")
    print("=" * 76)
    print(
        open_summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 76)
    print("TRIGGER TIME")
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
    print("Winner :", comparison_path)
    print("Open   :", open_path)
    print("Time   :", time_path)


if __name__ == "__main__":
    main()
