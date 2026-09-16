from pathlib import Path

import pandas as pd


TRACKING_PATH = Path(
    "data/tracking/intraday_strategy_h1.csv"
)


def print_summary(title, df):
    print()
    print("-" * 78)
    print(title)
    print("-" * 78)

    if df.empty:
        print("N=0")
        return

    ret = pd.to_numeric(
        df["ReturnPct"],
        errors="coerce",
    ).dropna()

    max_high = pd.to_numeric(
        df["MaxHighPct"],
        errors="coerce",
    ).dropna()

    min_low = pd.to_numeric(
        df["MinLowPct"],
        errors="coerce",
    ).dropna()

    exits = (
        df["ExitType"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    n = len(df)

    plus_rate = (
        (ret > 0).mean() * 100
        if len(ret)
        else float("nan")
    )

    take_rate = (
        (exits == "TAKE").mean() * 100
    )

    stop_rate = (
        (exits == "STOP").mean() * 100
    )

    print(
        f"N={n:2d} "
        f"Mean={ret.mean():7.2f}% "
        f"Median={ret.median():7.2f}% "
        f"Plus={plus_rate:6.1f}% "
        f"TAKE={take_rate:6.1f}% "
        f"STOP={stop_rate:6.1f}% "
        f"MaxHigh={max_high.mean():7.2f}% "
        f"MinLow={min_low.mean():7.2f}%"
    )


def print_group_table(title, df, column):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)

    for value, group in df.groupby(
        column,
        observed=True,
        sort=False,
    ):
        print_summary(
            f"{column} = {value}",
            group,
        )


def main():
    if not TRACKING_PATH.exists():
        print(
            f"Not found : {TRACKING_PATH}"
        )
        return

    df = pd.read_csv(
        TRACKING_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    if df.empty:
        print("Tracking is empty.")
        return

    exit_text = (
        df["ExitType"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    work = df[
        (df["DataType"] == "FORWARD")
        & (exit_text != "")
    ].copy()

    numeric_columns = [
        "Rank",
        "Change",
        "VolumeRatio",
        "CxV",
        "LimitUpRoomPct",
        "ReturnPct",
        "MaxHighPct",
        "MinLowPct",
        "ClosePct",
    ]

    for col in numeric_columns:
        work[col] = pd.to_numeric(
            work[col],
            errors="coerce",
        )

    print()
    print("=" * 78)
    print("H1 FORWARD ANALYSIS")
    print("=" * 78)
    print(
        f"Source       : {TRACKING_PATH}"
    )
    print(
        f"Forward done : {len(work)}"
    )
    print(
        "Room valid   : "
        f"{work['LimitUpRoomPct'].notna().sum()}"
    )

    print_summary(
        "OVERALL",
        work,
    )

    # =========================================================
    # Rank
    # =========================================================

    rank_work = work.copy()

    rank_work["RankGroup"] = (
        rank_work["Rank"]
        .map(
            lambda x:
                f"Rank {int(x)}"
                if pd.notna(x)
                else "Missing"
        )
    )

    print_group_table(
        "BY RANK",
        rank_work,
        "RankGroup",
    )

    # =========================================================
    # Change
    # =========================================================

    change_work = work[
        work["Change"].notna()
    ].copy()

    change_work["ChangeGroup"] = pd.cut(
        change_work["Change"],
        bins=[
            float("-inf"),
            5,
            10,
            20,
            float("inf"),
        ],
        labels=[
            "<5%",
            "5-10%",
            "10-20%",
            ">=20%",
        ],
        right=False,
    )

    print_group_table(
        "BY CHANGE",
        change_work,
        "ChangeGroup",
    )

    # =========================================================
    # CxV
    # =========================================================

    cxv_work = work[
        work["CxV"].notna()
    ].copy()

    cxv_work["CxVGroup"] = pd.cut(
        cxv_work["CxV"],
        bins=[
            float("-inf"),
            25,
            50,
            100,
            float("inf"),
        ],
        labels=[
            "<25",
            "25-50",
            "50-100",
            ">=100",
        ],
        right=False,
    )

    print_group_table(
        "BY CxV",
        cxv_work,
        "CxVGroup",
    )

    # =========================================================
    # Limit-up room
    # =========================================================

    room_work = work[
        work["LimitUpRoomPct"].notna()
    ].copy()

    room_work["RoomGroup"] = pd.cut(
        room_work["LimitUpRoomPct"],
        bins=[
            0,
            5,
            10,
            20,
            float("inf"),
        ],
        labels=[
            "0-5%",
            "5-10%",
            "10-20%",
            ">=20%",
        ],
        right=False,
    )

    print_group_table(
        "BY LIMIT-UP ROOM",
        room_work,
        "RoomGroup",
    )

    # =========================================================
    # Cross checks
    # =========================================================

    print()
    print("=" * 78)
    print("CROSS CHECK")
    print("=" * 78)

    cross_work = work[
        work["LimitUpRoomPct"].notna()
        & work["Change"].notna()
        & work["CxV"].notna()
    ].copy()

    checks = [
        (
            "Change >=20 & Room <10",
            (
                (cross_work["Change"] >= 20)
                & (
                    cross_work[
                        "LimitUpRoomPct"
                    ] < 10
                )
            ),
        ),
        (
            "Change >=20 & Room >=10",
            (
                (cross_work["Change"] >= 20)
                & (
                    cross_work[
                        "LimitUpRoomPct"
                    ] >= 10
                )
            ),
        ),
        (
            "CxV >=100 & Room <10",
            (
                (cross_work["CxV"] >= 100)
                & (
                    cross_work[
                        "LimitUpRoomPct"
                    ] < 10
                )
            ),
        ),
        (
            "CxV >=100 & Room >=10",
            (
                (cross_work["CxV"] >= 100)
                & (
                    cross_work[
                        "LimitUpRoomPct"
                    ] >= 10
                )
            ),
        ),
    ]

    for title, mask in checks:
        print_summary(
            title,
            cross_work[mask],
        )

    # =========================================================
    # Individual rows
    # =========================================================

    print()
    print("=" * 78)
    print("INDIVIDUAL FORWARD RESULTS")
    print("=" * 78)

    columns = [
        "DetectionDate",
        "Code",
        "Rank",
        "Change",
        "CxV",
        "LimitUpRoomPct",
        "ExitType",
        "ReturnPct",
        "MaxHighPct",
        "MinLowPct",
    ]

    print(
        work[columns]
        .sort_values(
            [
                "DetectionDate",
                "Rank",
            ]
        )
        .round(2)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
