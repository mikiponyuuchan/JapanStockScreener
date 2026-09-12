from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_backtest_panel.csv"
)

HIGH = "\u7fcc\u65e5\u9ad8\u5024\u7387"
M0930 = "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387"
CLOSE = "\u7fcc\u65e5\u7d42\u5024\u7387"


def pct(series, condition):
    s = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if s.empty:
        return float("nan")

    return condition(s).mean() * 100


def stats(label, df):
    if df.empty:
        print(
            f"{label:<14} N=0"
        )
        return

    h = pd.to_numeric(
        df[HIGH],
        errors="coerce",
    )

    m = pd.to_numeric(
        df[M0930],
        errors="coerce",
    )

    c = pd.to_numeric(
        df[CLOSE],
        errors="coerce",
    )

    print(
        f"{label:<14}"
        f" N={len(df):3d}"
        f" Days={df['DetectionDate'].nunique():2d}"
        f" 09:30={m.mean():6.2f}%"
        f" High={h.mean():6.2f}%"
        f" +5={pct(h, lambda x: x >= 5):5.1f}%"
        f" +10={pct(h, lambda x: x >= 10):5.1f}%"
        f" Close={c.mean():6.2f}%"
    )


def daily_stats(label, df):
    print()
    print("=" * 100)
    print(label)
    print("=" * 100)

    if df.empty:
        print("N=0")
        return

    for date, part in df.groupby(
        "DetectionDate",
        sort=True,
    ):
        h = pd.to_numeric(
            part[HIGH],
            errors="coerce",
        )

        m = pd.to_numeric(
            part[M0930],
            errors="coerce",
        )

        c = pd.to_numeric(
            part[CLOSE],
            errors="coerce",
        )

        print(
            f"{date}"
            f" N={len(part):2d}"
            f" 09:30={m.mean():6.2f}%"
            f" High={h.mean():6.2f}%"
            f" +5={pct(h, lambda x: x >= 5):5.1f}%"
            f" Close={c.mean():6.2f}%"
        )


def main():
    df = pd.read_csv(
        INPUT,
        dtype={"Code": str},
    )

    df = df[
        df["Rating"] == "STRONG_GOOD"
    ].copy()

    for col in [
        "SalesYoY",
        "OperatingYoY",
        "OrdinaryYoY",
        "NetYoY",
        HIGH,
        M0930,
        CLOSE,
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df["MinGrowth4"] = df[
        [
            "SalesYoY",
            "OperatingYoY",
            "OrdinaryYoY",
            "NetYoY",
        ]
    ].min(axis=1)

    revision_yes = (
        df["Revision"].astype(str)
        == "\u6709"
    )

    conditions = {
        "BASE": df.index == df.index,

        "MIN20":
            df["MinGrowth4"] >= 20,

        "SALES20":
            df["SalesYoY"] >= 20,

        "MIN20_S20":
            (df["MinGrowth4"] >= 20)
            & (df["SalesYoY"] >= 20),

        "MIN20_OR_R":
            (df["MinGrowth4"] >= 20)
            | revision_yes,

        "MIN20_AND_R":
            (df["MinGrowth4"] >= 20)
            & revision_yes,
    }

    print("=" * 100)
    print("EARNINGS CONDITION COMPARISON")
    print("=" * 100)

    print(
        "STRONG_GOOD total :",
        len(df),
    )

    print()

    for label, mask in conditions.items():
        stats(
            label,
            df[mask],
        )

    for label, mask in conditions.items():
        daily_stats(
            label,
            df[mask],
        )


if __name__ == "__main__":
    main()
