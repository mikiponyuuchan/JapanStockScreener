from pathlib import Path

import pandas as pd


INPUT = Path("data/analysis/intraday_top20_panel.csv")


def clean_time(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() == "nan":
        return ""

    return text


def compare(up, down):
    up = clean_time(up)
    down = clean_time(down)

    if not up and not down:
        return "NONE"

    if up and not down:
        return "UP"

    if down and not up:
        return "DOWN"

    if up < down:
        return "UP"

    if down < up:
        return "DOWN"

    return "SAME_BAR"


def simulate(row, take, stop):
    up_col = {
        3: "HitPlus3",
        5: "HitPlus5",
        10: "HitPlus10",
    }[take]

    down_col = {
        3: "HitMinus3",
        5: "HitMinus5",
    }[stop]

    result = compare(
        row.get(up_col, ""),
        row.get(down_col, "")
    )

    if result == "UP":
        return float(take), "TAKE"

    if result == "DOWN":
        return -float(stop), "STOP"

    if result == "SAME_BAR":
        return float("nan"), "SAME_BAR"

    close_pct = pd.to_numeric(
        row.get("ClosePct"),
        errors="coerce"
    )

    return close_pct, "CLOSE"


def summarize(df, take, stop):
    returns = []
    exits = []

    for _, row in df.iterrows():
        ret, exit_type = simulate(
            row,
            take,
            stop
        )

        returns.append(ret)
        exits.append(exit_type)

    x = df.copy()
    x["_Return"] = returns
    x["_Exit"] = exits

    valid = x["_Return"].dropna()

    print(
        f"+{take} / -{stop}"
    )
    print("-" * 72)
    print(f"N          : {len(x)}")
    print(
        f"SAME_BAR   : "
        f"{(x['_Exit'] == 'SAME_BAR').sum()}"
    )

    if len(valid):
        print(
            f"Mean       : {valid.mean():.2f}%"
        )
        print(
            f"Median     : {valid.median():.2f}%"
        )
        print(
            f"Win rate   : "
            f"{(valid > 0).mean()*100:.1f}%"
        )
        print(
            f"Total      : {valid.sum():.2f}%"
        )

    print(
        "Exit       : "
        + ", ".join(
            f"{k}={v}"
            for k, v in
            x["_Exit"]
            .value_counts()
            .to_dict()
            .items()
        )
    )


def main():
    df = pd.read_csv(INPUT)

    # Original snapshot column 14 is Initial Score.
    # Use column position to avoid Japanese source encoding issues.
    df["Score"] = pd.to_numeric(
        df.iloc[:, 13],
        errors="coerce"
    )

    df = df[
        pd.to_numeric(
            df["MaxHighPct"],
            errors="coerce"
        ).notna()
    ].copy()

    print("=" * 72)
    print("INTRADAY TOP20 IFDONE ANALYSIS")
    print("=" * 72)
    print(f"N : {len(df)}")

    for take, stop in [
        (5, 3),
        (5, 5),
        (10, 5),
    ]:
        print()
        summarize(
            df,
            take,
            stop
        )

    print()
    print("=" * 72)
    print("BY SCORE : +5 / -5")
    print("=" * 72)

    for score in sorted(
        df["Score"]
        .dropna()
        .unique(),
        reverse=True
    ):
        g = df[
            df["Score"] == score
        ]

        print()
        print(
            f"SCORE {score:g}"
        )
        summarize(
            g,
            5,
            5
        )

    print()
    print("=" * 72)
    print("SCORE 6 ROWS")
    print("=" * 72)

    score6 = df[
        df["Score"] == 6
    ]

    for _, row in score6.iterrows():
        print(
            f"{row['SnapshotDate']} "
            f"{row['SnapshotTime']} "
            f"Code={row.iloc[2]} "
            f"Price={row['SnapshotPrice']:.2f} "
            f"High={row['MaxHighPct']:.2f}% "
            f"Low={row['MinLowPct']:.2f}% "
            f"Close={row['ClosePct']:.2f}%"
        )


if __name__ == "__main__":
    main()
