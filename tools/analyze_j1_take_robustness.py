from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "data/analysis/j1_take_compare_520_549.csv"
)

TAKE_LEVELS = [3.0, 4.0, 5.0, 7.0]

CASES = [
    (
        "ALL 16",
        [],
    ),
    (
        "EXCLUDE 4052",
        ["4052"],
    ),
    (
        "EXCLUDE 4052 + 4960",
        ["4052", "4960"],
    ),
]


def summarize(df, title):

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    for take_pct in TAKE_LEVELS:

        g = df[
            df["TakeProfitPct"] == take_pct
        ].copy()

        ret = pd.to_numeric(
            g["ReturnPct"],
            errors="coerce",
        ).dropna()

        if ret.empty:
            continue

        print()
        print(
            f"TP +{take_pct:.0f} / SL -5"
        )
        print(
            "N        :",
            len(ret),
        )
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


def main():

    df = pd.read_csv(
        INPUT_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    df["Code"] = (
        df["Code"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    df["TakeProfitPct"] = pd.to_numeric(
        df["TakeProfitPct"],
        errors="coerce",
    )

    df["ReturnPct"] = pd.to_numeric(
        df["ReturnPct"],
        errors="coerce",
    )

    print("=" * 80)
    print("J1 TAKE ROBUSTNESS CHECK")
    print("Change1 5.20-5.49 / SL -5")
    print("=" * 80)

    for title, excluded in CASES:

        x = df[
            ~df["Code"].isin(excluded)
        ].copy()

        summarize(
            x,
            title,
        )


if __name__ == "__main__":
    main()
