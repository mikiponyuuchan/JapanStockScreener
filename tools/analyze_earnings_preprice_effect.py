from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_backtest_preprice.csv"
)

HIGH = "\u7fcc\u65e5\u9ad8\u5024\u7387"
M0930 = "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387"
CLOSE = "\u7fcc\u65e5\u7d42\u5024\u7387"


def show(label, part):
    if part.empty:
        print(
            f"{label:<18} N=0"
        )
        return

    high = pd.to_numeric(
        part[HIGH],
        errors="coerce",
    )

    m0930 = pd.to_numeric(
        part[M0930],
        errors="coerce",
    )

    close = pd.to_numeric(
        part[CLOSE],
        errors="coerce",
    )

    print(
        f"{label:<18}"
        f" N={len(part):2d}"
        f" Days={part['DetectionDate'].nunique():2d}"
        f" Pre5={part['Pre5Pct'].mean():7.2f}%"
        f" Pre20={part['Pre20Pct'].mean():7.2f}%"
        f" 09:30={m0930.mean():7.2f}%"
        f" High={high.mean():7.2f}%"
        f" +5={(high >= 5).mean() * 100:6.1f}%"
        f" +10={(high >= 10).mean() * 100:6.1f}%"
        f" Close={close.mean():7.2f}%"
    )


def analyze_group(title, df):
    print()
    print("=" * 112)
    print(title)
    print("=" * 112)

    show(
        "ALL",
        df,
    )

    print()
    print("Pre5 bands")

    bands5 = [
        ("< 0%", df["Pre5Pct"] < 0),
        (
            "0 to <5%",
            (df["Pre5Pct"] >= 0)
            & (df["Pre5Pct"] < 5),
        ),
        (
            "5 to <10%",
            (df["Pre5Pct"] >= 5)
            & (df["Pre5Pct"] < 10),
        ),
        (
            ">= 10%",
            df["Pre5Pct"] >= 10,
        ),
    ]

    for label, mask in bands5:
        show(
            label,
            df[mask],
        )

    print()
    print("Pre20 bands")

    bands20 = [
        ("< 0%", df["Pre20Pct"] < 0),
        (
            "0 to <10%",
            (df["Pre20Pct"] >= 0)
            & (df["Pre20Pct"] < 10),
        ),
        (
            "10 to <20%",
            (df["Pre20Pct"] >= 10)
            & (df["Pre20Pct"] < 20),
        ),
        (
            ">= 20%",
            df["Pre20Pct"] >= 20,
        ),
    ]

    for label, mask in bands20:
        show(
            label,
            df[mask],
        )


def main():
    df = pd.read_csv(
        INPUT,
        dtype={"Code": str},
    )

    for col in [
        "SalesYoY",
        "OperatingYoY",
        "OrdinaryYoY",
        "NetYoY",
        "Pre5Pct",
        "Pre20Pct",
        HIGH,
        M0930,
        CLOSE,
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    strong = df[
        df["Rating"] == "STRONG_GOOD"
    ].copy()

    strong["MinGrowth4"] = strong[
        [
            "SalesYoY",
            "OperatingYoY",
            "OrdinaryYoY",
            "NetYoY",
        ]
    ].min(axis=1)

    min20 = strong[
        strong["MinGrowth4"] >= 20
    ].copy()

    analyze_group(
        "STRONG_GOOD",
        strong,
    )

    analyze_group(
        "MIN20",
        min20,
    )

    print()
    print("=" * 112)
    print("MIN20 INDIVIDUAL CASES")
    print("=" * 112)

    cols = [
        "DetectionDate",
        "Code",
        "Name",
        "MinGrowth4",
        "Pre5Pct",
        "Pre20Pct",
        M0930,
        HIGH,
        CLOSE,
    ]

    print(
        min20[cols]
        .sort_values(
            [
                "DetectionDate",
                HIGH,
            ],
            ascending=[
                True,
                False,
            ],
        )
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
