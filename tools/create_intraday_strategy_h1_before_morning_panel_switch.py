from pathlib import Path
import csv

import pandas as pd


SNAPSHOT_DIR = Path("data/tracking/morning_snapshots")
OUTPUT_PATH = Path("data/tracking/intraday_strategy_h1.csv")

FORWARD_START = "2026-09-04"

TARGET_START_MIN = 9 * 60 + 30
TARGET_END_MIN = 9 * 60 + 35

TOP_N = 3

TAKE_PROFIT_PCT = 10.0
STOP_LOSS_PCT = -3.0

OUTPUT_COLUMNS = [
    "StrategyVersion",
    "DataType",
    "DetectionDate",
    "SnapshotTime",
    "Code",
    "Name",
    "Rank",
    "SnapshotPrice",
    "Change",
    "VolumeRatio",
    "CxV",
    "TakeProfitPct",
    "StopLossPct",
    "HitPlus10Time",
    "HitMinus3Time",
    "ExitType",
    "ReturnPct",
    "MaxHighPct",
    "MinLowPct",
    "ClosePct",
]


def time_to_minutes(value):
    text = str(value).strip()

    try:
        parts = text.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None


def read_snapshot(path):
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        print(f"READ ERROR : {path} : {exc}")
        return None

    if df.empty or len(df.columns) < 23:
        return None

    return df


def select_target_snapshot(files):
    candidates = []

    for path in files:
        df = read_snapshot(path)

        if df is None:
            continue

        snapshot_date = str(df.iloc[0, 0]).strip()
        snapshot_time = str(df.iloc[0, 1]).strip()

        minute = time_to_minutes(snapshot_time)

        if minute is None:
            continue

        if not (
            TARGET_START_MIN
            <= minute
            <= TARGET_END_MIN
        ):
            continue

        candidates.append(
            (
                snapshot_date,
                minute,
                snapshot_time,
                path,
                df,
            )
        )

    if not candidates:
        return []

    # One snapshot per date.
    # If multiple snapshots exist in the target window,
    # use the earliest one.
    selected = {}

    for item in sorted(
        candidates,
        key=lambda x: (x[0], x[1]),
    ):
        date = item[0]

        if date not in selected:
            selected[date] = item

    return list(selected.values())


def build_top3(snapshot_date, snapshot_time, df):
    work = df.copy()

    work["CodeX"] = work.iloc[:, 2].astype(str)
    work["NameX"] = work.iloc[:, 3].astype(str)

    work["PriceX"] = pd.to_numeric(
        work.iloc[:, 5],
        errors="coerce",
    )

    work["ChangeX"] = pd.to_numeric(
        work.iloc[:, 6],
        errors="coerce",
    )

    work["VolumeX"] = pd.to_numeric(
        work.iloc[:, 22],
        errors="coerce",
    )

    work["CxV"] = (
        work["ChangeX"]
        * work["VolumeX"]
    )

    valid = work[
        work["PriceX"].notna()
        & work["ChangeX"].notna()
        & work["VolumeX"].notna()
        & work["CxV"].notna()
    ].copy()

    top3 = valid.sort_values(
        ["CxV", "ChangeX"],
        ascending=[False, False],
    ).head(TOP_N)

    rows = []

    for rank, (_, row) in enumerate(
        top3.iterrows(),
        start=1,
    ):
        data_type = (
            "FORWARD"
            if snapshot_date >= FORWARD_START
            else "DEVELOPMENT"
        )

        rows.append(
            {
                "StrategyVersion": "H1",
                "DataType": data_type,
                "DetectionDate": snapshot_date,
                "SnapshotTime": snapshot_time,
                "Code": row["CodeX"],
                "Name": row["NameX"],
                "Rank": rank,
                "SnapshotPrice": row["PriceX"],
                "Change": row["ChangeX"],
                "VolumeRatio": row["VolumeX"],
                "CxV": row["CxV"],
                "TakeProfitPct": TAKE_PROFIT_PCT,
                "StopLossPct": STOP_LOSS_PCT,
                "HitPlus10Time": "",
                "HitMinus3Time": "",
                "ExitType": "",
                "ReturnPct": "",
                "MaxHighPct": "",
                "MinLowPct": "",
                "ClosePct": "",
            }
        )

    return rows


def load_existing():
    if not OUTPUT_PATH.exists():
        return pd.DataFrame(
            columns=OUTPUT_COLUMNS
        )

    try:
        return pd.read_csv(
            OUTPUT_PATH,
            dtype={
                "Code": str,
            },
        )
    except Exception:
        return pd.DataFrame(
            columns=OUTPUT_COLUMNS
        )


def main():
    files = sorted(
        SNAPSHOT_DIR.glob("*_top20.csv")
    )

    if not files:
        print("No snapshot files.")
        return

    snapshots = select_target_snapshot(files)

    if not snapshots:
        print("No 09:30-09:35 snapshots.")
        return

    new_rows = []

    for (
        snapshot_date,
        _,
        snapshot_time,
        path,
        df,
    ) in snapshots:

        rows = build_top3(
            snapshot_date,
            snapshot_time,
            df,
        )

        new_rows.extend(rows)

        print(
            f"{snapshot_date} "
            f"{snapshot_time} "
            f"TOP3={len(rows)}"
        )

        for row in rows:
            print(
                f"  {row['Rank']} "
                f"{row['Code']} "
                f"CxV={row['CxV']:.2f}"
            )

    if not new_rows:
        print("No candidates.")
        return

    existing = load_existing()

    incoming = pd.DataFrame(
        new_rows,
        columns=OUTPUT_COLUMNS,
    )

    combined = pd.concat(
        [existing, incoming],
        ignore_index=True,
    )

    combined["Code"] = (
        combined["Code"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )

    # Preserve already-updated outcome fields.
    # Existing rows are kept first.
    combined = combined.drop_duplicates(
        subset=[
            "StrategyVersion",
            "DetectionDate",
            "SnapshotTime",
            "Code",
        ],
        keep="first",
    )

    combined = combined.sort_values(
        [
            "DetectionDate",
            "SnapshotTime",
            "Rank",
        ]
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
    )

    forward = combined[
        combined["DataType"] == "FORWARD"
    ]

    development = combined[
        combined["DataType"] == "DEVELOPMENT"
    ]

    print()
    print("=" * 50)
    print("H1 TRACKING")
    print("=" * 50)
    print(f"Development : {len(development)}")
    print(f"Forward     : {len(forward)}")
    print(f"Total       : {len(combined)}")
    print(f"Saved       : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
