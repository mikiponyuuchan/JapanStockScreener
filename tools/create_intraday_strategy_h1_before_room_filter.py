from pathlib import Path
import csv

import pandas as pd


SNAPSHOT_DIR = Path("data/analysis/morning")
OUTPUT_PATH = Path("data/tracking/intraday_strategy_h1.csv")

FORWARD_START = "2026-09-04"

# Morning-panel based H1 starts here.
# Older H1 rows are preserved from the original snapshot method.
MORNING_PANEL_START = "2026-09-07"

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


def time_to_minutes(value):
    text = str(value).strip()

    try:
        parts = text.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None


def read_snapshot(path):
    try:
        df = pd.read_csv(
            path,
            dtype={
                "Code": str,
            },
            low_memory=False,
        )
    except Exception as exc:
        print(f"READ ERROR : {path} : {exc}")
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


def select_target_snapshot(files):
    candidates = []

    for path in files:

        df = read_snapshot(path)

        if df is None:
            continue

        stem = path.stem

        # Example:
        # 2026-09-07_0930_morning_panel
        parts = stem.split("_")

        if len(parts) < 2:
            continue

        snapshot_date = parts[0]

        if snapshot_date < MORNING_PANEL_START:
            continue

        hhmm = parts[1]

        if len(hhmm) != 4 or not hhmm.isdigit():
            continue

        hour = int(hhmm[:2])
        minute_only = int(hhmm[2:])

        minute = hour * 60 + minute_only

        if not (
            TARGET_START_MIN
            <= minute
            <= TARGET_END_MIN
        ):
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

    if not candidates:
        return []

    # One snapshot per date.
    # If several files exist in the target window,
    # use the earliest one.
    selected = {}

    for item in sorted(
        candidates,
        key=lambda x: (x[0], x[1], str(x[3])),
    ):
        date = item[0]

        if date not in selected:
            selected[date] = item

    return list(selected.values())


def build_top3(snapshot_date, snapshot_time, df):
    work = df.copy()

    work["CodeX"] = (
        work["Code"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\\.0$",
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
                "LimitUpPrice": row["LimitUpPriceX"],
                "LimitUpRoomPct": row["LimitUpRoomPctX"],
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
        SNAPSHOT_DIR.glob("*_morning_panel.csv")
    )

    if not files:
        print("No snapshot files.")
        return

    snapshots = select_target_snapshot(files)

    if not snapshots:
        print("No 09:30-09:35 morning panels.")
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
