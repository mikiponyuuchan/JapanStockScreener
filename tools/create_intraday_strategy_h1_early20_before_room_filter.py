from pathlib import Path
import csv

import pandas as pd


MORNING_DIR = Path("data/analysis/morning")

OUTPUT_PATH = Path(
    "data/tracking/intraday_strategy_h1_early20.csv"
)

START_DATE = "2026-09-07"

# 09:20～09:25の最も早い取得データを使用
TARGET_START_MIN = 9 * 60 + 20
TARGET_END_MIN = 9 * 60 + 25

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
    "LimitUpPrice",
    "LimitUpRoomPct",
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


def get_normal_limit_up_price(prev_close):
    """
    Calculate the normal TSE daily upper price limit
    from the reference price (normally previous close).

    NOTE:
    This handles the normal daily price-limit table only.
    Temporary expanded price limits are not handled.
    """
    try:
        price = float(prev_close)
    except (TypeError, ValueError):
        return None

    if pd.isna(price) or price <= 0:
        return None

    bands = [
        (100, 30),
        (200, 50),
        (500, 80),
        (700, 100),
        (1000, 150),
        (1500, 300),
        (2000, 400),
        (3000, 500),
        (5000, 700),
        (7000, 1000),
        (10000, 1500),
        (15000, 3000),
        (20000, 4000),
        (30000, 5000),
        (50000, 7000),
        (70000, 10000),
        (100000, 15000),
        (150000, 30000),
        (200000, 40000),
        (300000, 50000),
        (500000, 70000),
        (700000, 100000),
        (1000000, 150000),
        (1500000, 300000),
        (2000000, 400000),
        (3000000, 500000),
        (5000000, 700000),
        (7000000, 1000000),
        (10000000, 1500000),
        (15000000, 3000000),
        (20000000, 4000000),
        (30000000, 5000000),
        (50000000, 7000000),
    ]

    for upper, width in bands:
        if price < upper:
            return price + width

    return price + 10000000


def calc_limit_up_room_pct(snapshot_price, limit_up_price):
    try:
        price = float(snapshot_price)
        limit_price = float(limit_up_price)
    except (TypeError, ValueError):
        return None

    if (
        pd.isna(price)
        or pd.isna(limit_price)
        or price <= 0
    ):
        return None

    return (
        limit_price / price - 1.0
    ) * 100.0


def read_panel(path):
    try:
        df = pd.read_csv(
            path,
            dtype={"Code": str},
            low_memory=False,
        )
    except Exception as exc:
        print(
            f"READ ERROR : {path} : {exc}"
        )
        return None

    required = [
        "Code",
        "Name",
        "MorningPrice",
        "PrevClose",
        "MorningChangePct",
        "MorningVolumeVsPrev5",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if df.empty or missing:
        return None

    return df


def select_panels(files):
    candidates = []

    for path in files:

        parts = path.stem.split("_")

        if len(parts) < 2:
            continue

        snapshot_date = parts[0]
        hhmm = parts[1]

        if snapshot_date < START_DATE:
            continue

        if (
            len(hhmm) != 4
            or not hhmm.isdigit()
        ):
            continue

        hour = int(hhmm[:2])
        minute_only = int(hhmm[2:])

        minute = (
            hour * 60
            + minute_only
        )

        if not (
            TARGET_START_MIN
            <= minute
            <= TARGET_END_MIN
        ):
            continue

        df = read_panel(path)

        if df is None:
            continue

        snapshot_time = (
            f"{hour:02d}:"
            f"{minute_only:02d}:00"
        )

        candidates.append(
            (
                snapshot_date,
                minute,
                snapshot_time,
                path,
                df,
            )
        )

    # Earliest panel per date
    selected = {}

    for item in sorted(
        candidates,
        key=lambda x: (
            x[0],
            x[1],
            str(x[3]),
        ),
    ):
        date = item[0]

        if date not in selected:
            selected[date] = item

    return list(
        selected.values()
    )


def build_top3(
    snapshot_date,
    snapshot_time,
    df,
):
    work = df.copy()

    work["CodeX"] = (
        work["Code"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    work["NameX"] = (
        work["Name"]
        .astype(str)
    )

    work["PriceX"] = pd.to_numeric(
        work["MorningPrice"],
        errors="coerce",
    )

    work["PrevCloseX"] = pd.to_numeric(
        work["PrevClose"],
        errors="coerce",
    )

    work["LimitUpPriceX"] = (
        work["PrevCloseX"]
        .map(get_normal_limit_up_price)
    )

    work["LimitUpRoomPctX"] = [
        calc_limit_up_room_pct(price, limit_price)
        for price, limit_price in zip(
            work["PriceX"],
            work["LimitUpPriceX"],
        )
    ]

    work["ChangeX"] = pd.to_numeric(
        work["MorningChangePct"],
        errors="coerce",
    )

    work["VolumeX"] = pd.to_numeric(
        work["MorningVolumeVsPrev5"],
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

    top3 = (
        valid
        .sort_values(
            ["CxV", "ChangeX"],
            ascending=[
                False,
                False,
            ],
        )
        .head(TOP_N)
    )

    rows = []

    for rank, (_, row) in enumerate(
        top3.iterrows(),
        start=1,
    ):
        rows.append(
            {
                "StrategyVersion":
                    "H1-Early20",
                "DataType":
                    "VALIDATION",
                "DetectionDate":
                    snapshot_date,
                "SnapshotTime":
                    snapshot_time,
                "Code":
                    row["CodeX"],
                "Name":
                    row["NameX"],
                "Rank":
                    rank,
                "SnapshotPrice":
                    row["PriceX"],
                "Change":
                    row["ChangeX"],
                "VolumeRatio":
                    row["VolumeX"],
                "CxV":
                    row["CxV"],
                "LimitUpPrice":
                    row["LimitUpPriceX"],
                "LimitUpRoomPct":
                    row["LimitUpRoomPctX"],
                "TakeProfitPct":
                    TAKE_PROFIT_PCT,
                "StopLossPct":
                    STOP_LOSS_PCT,
                "HitPlus10Time":
                    "",
                "HitMinus3Time":
                    "",
                "ExitType":
                    "",
                "ReturnPct":
                    "",
                "MaxHighPct":
                    "",
                "MinLowPct":
                    "",
                "ClosePct":
                    "",
            }
        )

    return rows


def load_existing():
    if not OUTPUT_PATH.exists():
        return pd.DataFrame(
            columns=OUTPUT_COLUMNS
        )

    return pd.read_csv(
        OUTPUT_PATH,
        dtype={"Code": str},
        low_memory=False,
    )


def main():

    files = sorted(
        MORNING_DIR.glob(
            "*_morning_panel.csv"
        )
    )

    panels = select_panels(files)

    if not panels:
        print(
            "No 09:20-09:25 "
            "morning panels."
        )
        return

    new_rows = []

    for (
        snapshot_date,
        _,
        snapshot_time,
        path,
        df,
    ) in panels:

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
                f"CxV={row['CxV']:.2f} "
                f"LimitUp={row['LimitUpPrice']:.0f} "
                f"Room={row['LimitUpRoomPct']:.2f}%"
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
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    # Keep existing outcome data
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

    print()
    print("=" * 50)
    print("H1-Early20 VALIDATION")
    print("=" * 50)
    print(
        f"Total : {len(combined)}"
    )
    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
