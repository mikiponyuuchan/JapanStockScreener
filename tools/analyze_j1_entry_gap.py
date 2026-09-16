from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "data/analysis/j1_take_compare_520_549.csv"
)

TAKE_PCT = 3.0
STOP_PCT = -5.0


def gap_group(v):
    if pd.isna(v):
        return "NA"
    if v < -3:
        return "01 GD <-3"
    if v < -2:
        return "02 GD -3~-2"
    if v < -1:
        return "03 GD -2~-1"
    if v < 0:
        return "04 GD -1~0"
    if v < 1:
        return "05 GU 0~1"
    if v < 2:
        return "06 GU 1~2"
    if v < 3:
        return "07 GU 2~3"
    if v < 5:
        return "08 GU 3~5"
    if v < 7:
        return "09 GU 5~7"
    if v < 10:
        return "10 GU 7~10"
    return "11 GU 10+"


def main():

    df = pd.read_csv(
        INPUT_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    for col in [
        "TakeProfitPct",
        "StopLossPct",
        "NextOpenGapPct",
        "ReturnPct",
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    x = df[
        (df["TakeProfitPct"] == TAKE_PCT)
        & (df["StopLossPct"] == STOP_PCT)
    ].copy()

    x["GapGroup"] = (
        x["NextOpenGapPct"]
        .map(gap_group)
    )

    print("=" * 90)
    print("J1 ENTRY FILTER BY NEXT OPEN GAP")
    print("Change1 5.20-5.49")
    print("TP +3 / SL -5")
    print("=" * 90)

    for group_name, g in x.groupby(
        "GapGroup",
        sort=True,
    ):

        ret = pd.to_numeric(
            g["ReturnPct"],
            errors="coerce",
        ).dropna()

        print()
        print("=" * 90)
        print(group_name)
        print("=" * 90)

        print("N        :", len(g))

        if len(ret):
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

        cols = [
            "DetectionDate",
            "Code",
            "Name",
            "NextOpenGapPct",
            "ExitType",
            "ReturnPct",
            "TakeTime",
            "StopTime",
        ]

        print(
            g[cols]
            .sort_values("NextOpenGapPct")
            .to_string(
                index=False,
                float_format=lambda v: f"{v:.2f}",
            )
        )


if __name__ == "__main__":
    main()
