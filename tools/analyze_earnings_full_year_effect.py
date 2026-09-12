from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

FULL_YEAR = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_full_year_panel.csv"
)

BACKTEST = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_backtest_panel.csv"
)

OUTPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_full_year_return_panel.csv"
)


def normalize_code(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )


def stats(df, label):
    if df.empty:
        return

    high5 = (
        df["NextHighPct"]
        .ge(5.0)
        .mean()
        * 100
    )

    high10 = (
        df["NextHighPct"]
        .ge(10.0)
        .mean()
        * 100
    )

    close_plus = (
        df["NextClosePct"]
        .gt(0)
        .mean()
        * 100
    )

    dates = (
        df["DetectionDate"]
        .nunique()
    )

    print(
        f"{label:<20} "
        f"N={len(df):>2}  "
        f"Days={dates:>2}  "
        f"09:30={df['Next0930Pct'].mean():+6.2f}  "
        f"High={df['NextHighPct'].mean():+6.2f}  "
        f"HighMed={df['NextHighPct'].median():+6.2f}  "
        f"+5={high5:5.1f}%  "
        f"+10={high10:5.1f}%  "
        f"Close={df['NextClosePct'].mean():+6.2f}  "
        f"Close+={close_plus:5.1f}%"
    )


def main():
    fy = pd.read_csv(
        FULL_YEAR,
        dtype={
            "Code": str,
        },
    )

    bt = pd.read_csv(
        BACKTEST,
        dtype={
            "Code": str,
        },
    )

    fy["Code"] = normalize_code(
        fy["Code"]
    )

    bt["Code"] = normalize_code(
        bt["Code"]
    )

    fy = fy[
        fy["ParseStatus"]
        .eq("OK")
        & fy["MinForecastGrowth4"]
        .notna()
    ].copy()

    fy["DetectionDate"] = pd.to_datetime(
        fy["DetectionDate"]
    ).dt.strftime("%Y-%m-%d")

    bt["DetectionDate"] = pd.to_datetime(
        bt["DetectionDate"]
    ).dt.strftime("%Y-%m-%d")

    bt["Next0930Pct"] = bt[
        "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387"
    ]

    bt["NextHighPct"] = bt[
        "\u7fcc\u65e5\u9ad8\u5024\u7387"
    ]

    bt["NextClosePct"] = bt[
        "\u7fcc\u65e5\u7d42\u5024\u7387"
    ]

    merged = fy.merge(
        bt,
        on=[
            "DetectionDate",
            "Code",
        ],
        how="inner",
        suffixes=(
            "_FY",
            "_BT",
        ),
    )

    merged.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 100)
    print("FULL-YEAR FORECAST VS NEXT DAY")
    print("=" * 100)

    print(
        "Growth eligible :",
        len(fy),
    )

    print(
        "Merged          :",
        len(merged),
    )

    print()

    stats(
        merged,
        "ALL",
    )

    print()
    print("=" * 100)
    print("FIXED FORECAST-GROWTH BANDS")
    print("=" * 100)

    bands = [
        (
            "< 0",
            merged[
                "MinForecastGrowth4"
            ] < 0,
        ),
        (
            "0 to <10",
            (
                merged[
                    "MinForecastGrowth4"
                ] >= 0
            )
            & (
                merged[
                    "MinForecastGrowth4"
                ] < 10
            ),
        ),
        (
            "10 to <20",
            (
                merged[
                    "MinForecastGrowth4"
                ] >= 10
            )
            & (
                merged[
                    "MinForecastGrowth4"
                ] < 20
            ),
        ),
        (
            ">= 20",
            merged[
                "MinForecastGrowth4"
            ] >= 20,
        ),
    ]

    for label, mask in bands:
        stats(
            merged[mask],
            label,
        )

    print()
    print("=" * 100)
    print("STRONG_GOOD ONLY")
    print("=" * 100)

    sg = merged[
        merged["Rating_FY"]
        .eq("STRONG_GOOD")
    ]

    stats(
        sg,
        "SG ALL",
    )

    for label, mask in bands:
        part = sg[
            sg.index.isin(
                merged.index[mask]
            )
        ]

        stats(
            part,
            label,
        )

    print()
    print("=" * 100)
    print("DATE COUNTS")
    print("=" * 100)

    print(
        merged[
            "DetectionDate"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "Saved :",
        OUTPUT,
    )


if __name__ == "__main__":
    main()
