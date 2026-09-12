from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PROGRESS = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_progress_panel_v2.csv"
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
    / "earnings_progress_return_panel.csv"
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

    def mean(col):
        return df[col].mean()

    def median(col):
        return df[col].median()

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

    print(
        f"{label:<22} "
        f"N={len(df):>3}  "
        f"09:30={mean('Next0930Pct'):+6.2f}  "
        f"High={mean('NextHighPct'):+6.2f}  "
        f"HighMed={median('NextHighPct'):+6.2f}  "
        f"+5={high5:5.1f}%  "
        f"+10={high10:5.1f}%  "
        f"Close={mean('NextClosePct'):+6.2f}  "
        f"Close+={close_plus:5.1f}%"
    )


def main():
    progress = pd.read_csv(
        PROGRESS,
        dtype={
            "Code": str,
        },
    )

    backtest = pd.read_csv(
        BACKTEST,
        dtype={
            "Code": str,
        },
    )

    # Normalize return column names for analysis.
    backtest["Next0930Pct"] = backtest[
        "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387"
    ]

    backtest["NextHighPct"] = backtest[
        "\u7fcc\u65e5\u9ad8\u5024\u7387"
    ]

    backtest["NextClosePct"] = backtest[
        "\u7fcc\u65e5\u7d42\u5024\u7387"
    ]

    progress["Code"] = normalize_code(
        progress["Code"]
    )

    backtest["Code"] = normalize_code(
        backtest["Code"]
    )

    progress = progress[
        progress["ParseStatus"]
        .eq("OK")
    ].copy()

    progress[
        "DetectionDate"
    ] = pd.to_datetime(
        progress["DetectionDate"]
    ).dt.strftime("%Y-%m-%d")

    backtest[
        "DetectionDate"
    ] = pd.to_datetime(
        backtest["DetectionDate"]
    ).dt.strftime("%Y-%m-%d")

    keep = [
        "DetectionDate",
        "Code",
        "Quarter",
        "OperatingProgress",
        "OperatingProgressExcess",
        "NetProgress",
        "NetProgressExcess",
    ]

    merged = backtest.merge(
        progress[keep],
        on=[
            "DetectionDate",
            "Code",
        ],
        how="inner",
    )

    merged[
        "MinProgressExcess"
    ] = merged[
        [
            "OperatingProgressExcess",
            "NetProgressExcess",
        ]
    ].min(
        axis=1
    )

    merged[
        "MinGrowth4"
    ] = merged[
        [
            "SalesYoY",
            "OperatingYoY",
            "OrdinaryYoY",
            "NetYoY",
        ]
    ].min(
        axis=1
    )

    merged.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 100)
    print("EARNINGS PROGRESS VS NEXT DAY")
    print("=" * 100)

    print(
        "Progress OK :",
        len(progress),
    )

    print(
        "Merged      :",
        len(merged),
    )

    print()

    print("=" * 100)
    print("ALL QUARTERLY")
    print("=" * 100)

    stats(
        merged,
        "ALL",
    )

    print()
    print("MinProgressExcess distribution")
    print(
        merged[
            "MinProgressExcess"
        ].describe().to_string()
    )

    print()
    print("=" * 100)
    print("FIXED DESCRIPTIVE BANDS")
    print("=" * 100)

    bands = [
        (
            "< -10",
            merged[
                "MinProgressExcess"
            ] < -10,
        ),
        (
            "-10 to <0",
            (
                merged[
                    "MinProgressExcess"
                ] >= -10
            )
            & (
                merged[
                    "MinProgressExcess"
                ] < 0
            ),
        ),
        (
            "0 to <10",
            (
                merged[
                    "MinProgressExcess"
                ] >= 0
            )
            & (
                merged[
                    "MinProgressExcess"
                ] < 10
            ),
        ),
        (
            "10 to <20",
            (
                merged[
                    "MinProgressExcess"
                ] >= 10
            )
            & (
                merged[
                    "MinProgressExcess"
                ] < 20
            ),
        ),
        (
            ">= 20",
            merged[
                "MinProgressExcess"
            ] >= 20,
        ),
    ]

    for label, mask in bands:
        stats(
            merged[mask],
            label,
        )

    if "Rating" in merged.columns:
        print()
        print("=" * 100)
        print("STRONG_GOOD ONLY")
        print("=" * 100)

        sg = merged[
            merged["Rating"]
            .eq("STRONG_GOOD")
        ]

        stats(
            sg,
            "SG ALL",
        )

        for label, mask in bands:
            idx = merged.index[
                mask
            ]

            part = sg[
                sg.index.isin(idx)
            ]

            stats(
                part,
                label,
            )

    if "MinGrowth4" in merged.columns:
        print()
        print("=" * 100)
        print("BALANCED GROWTH MIN20")
        print("=" * 100)

        bg = merged[
            (
                merged["Rating"]
                .eq("STRONG_GOOD")
            )
            & (
                merged["MinGrowth4"]
                >= 20
            )
        ]

        stats(
            bg,
            "MIN20 ALL",
        )

        for label, mask in bands:
            idx = merged.index[
                mask
            ]

            part = bg[
                bg.index.isin(idx)
            ]

            stats(
                part,
                label,
            )

    print()
    print(
        "Saved :",
        OUTPUT,
    )


if __name__ == "__main__":
    main()
