import argparse
from pathlib import Path

import pandas as pd


def capped_score(value, full_value, points):
    value = pd.to_numeric(
        value,
        errors="coerce",
    )

    if pd.isna(value):
        return 0.0

    value = max(
        0.0,
        min(float(value), full_value),
    )

    return (
        value / full_value
    ) * points


def calculate_strength(row, cols):
    sales = pd.to_numeric(
        row[cols["sales"]],
        errors="coerce",
    )
    operating = pd.to_numeric(
        row[cols["operating"]],
        errors="coerce",
    )
    ordinary = pd.to_numeric(
        row[cols["ordinary"]],
        errors="coerce",
    )
    net = pd.to_numeric(
        row[cols["net"]],
        errors="coerce",
    )

    score = 0.0

    score += capped_score(
        sales,
        50.0,
        20.0,
    )

    score += capped_score(
        operating,
        100.0,
        20.0,
    )

    score += capped_score(
        ordinary,
        100.0,
        20.0,
    )

    score += capped_score(
        net,
        100.0,
        20.0,
    )

    profits = [
        x
        for x in [
            operating,
            ordinary,
            net,
        ]
        if not pd.isna(x)
    ]

    if len(profits) == 3:
        min_profit = min(profits)

        score += capped_score(
            min_profit,
            50.0,
            20.0,
        )

    revision = str(
        row[cols["revision"]]
    ).strip()

    if revision == "\u6709":
        score += 10.0

    return round(
        score,
        1,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
    )

    args = parser.parse_args()

    path = Path(
        "results"
    ) / (
        f"{args.date}_"
        "earnings_catalyst.xlsx"
    )

    df = pd.read_excel(
        path
    )

    cols = {
        "code": df.columns[0],
        "name": df.columns[1],
        "sales": df.columns[3],
        "operating": df.columns[4],
        "ordinary": df.columns[5],
        "net": df.columns[6],
        "rating": df.columns[7],
        "revision": df.columns[8],
    }

    df["StrengthScore"] = df.apply(
        calculate_strength,
        axis=1,
        cols=cols,
    )

    eligible = df[
        df[cols["rating"]].isin(
            [
                "STRONG_GOOD",
                "GOOD",
            ]
        )
    ].copy()

    eligible = eligible.sort_values(
        [
            "StrengthScore",
            cols["sales"],
            cols["operating"],
        ],
        ascending=[
            False,
            False,
            False,
        ],
    )

    eligible["Priority"] = "WATCH"

    if len(eligible) > 0:
        eligible.iloc[
            0:min(3, len(eligible)),
            eligible.columns.get_loc(
                "Priority"
            ),
        ] = "PRIORITY_1"

    if len(eligible) > 3:
        eligible.iloc[
            3:min(8, len(eligible)),
            eligible.columns.get_loc(
                "Priority"
            ),
        ] = "PRIORITY_2"

    print(
        "=" * 78
    )
    print(
        "EARNINGS STRENGTH RANKING"
    )
    print(
        "=" * 78
    )
    print(
        "Date       :",
        args.date,
    )
    print(
        "Candidates :",
        len(eligible),
    )
    print()

    display = eligible[
        [
            cols["code"],
            cols["name"],
            cols["sales"],
            cols["operating"],
            cols["ordinary"],
            cols["net"],
            cols["rating"],
            cols["revision"],
            "StrengthScore",
            "Priority",
        ]
    ]

    print(
        display.to_string(
            index=False
        )
    )

    out_dir = Path(
        "data/analysis"
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_path = (
        out_dir
        / (
            f"{args.date}_"
            "earnings_strength_ranking.csv"
        )
    )

    eligible.to_csv(
        out_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "=" * 78
    )

    p1 = eligible[
        eligible["Priority"]
        == "PRIORITY_1"
    ]

    print(
        "PRIORITY_1"
    )
    print(
        "=" * 78
    )

    if p1.empty:
        print(
            "No candidates."
        )
    else:
        for rank, (_, row) in enumerate(
            p1.iterrows(),
            start=1,
        ):
            print(
                rank,
                row[cols["code"]],
                row[cols["name"]],
                "Score=",
                row["StrengthScore"],
            )

    print()
    print(
        "Saved :",
        out_path,
    )


if __name__ == "__main__":
    main()
