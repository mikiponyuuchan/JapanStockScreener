from pathlib import Path
import re
import pandas as pd

from intraday.h1_low_cxv_selector import select_h1_low_cxv

OUTPUT_PATH = Path("data/tracking/h1_low_cxv_tracking.csv")
FORWARD_START = "2026-10-21"

COLUMNS = [
    "StrategyVersion", "DataType", "DetectionDate",
    "SnapshotTime", "Code", "Name", "Rank", "RankGroup",
    "SnapshotPrice", "Change", "VolumeRatio", "CxV",
    "LimitUpPrice", "LimitUpRoomPct",
    "TakeProfitPct", "StopLossPct",
    "HitPlus10Time", "HitMinus3Time", "ExitType",
    "ReturnPct", "MaxHighPct", "MinLowPct", "ClosePct",
]


def record_low_cxv(h1_candidates, snapshot, panel_path):
    filename = Path(panel_path).name

    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})_(\d{4})_morning_panel\.csv",
        filename,
    )

    if match is None:
        raise ValueError(f"Unexpected panel filename: {filename}")

    date, hhmm = match.groups()

    if date < FORWARD_START:
        print("LOW-CxV tracking: before forward start, skipped")
        return 0

    if hhmm != "0930":
        raise ValueError(f"Not a 09:30 panel: {filename}")

    selected = select_h1_low_cxv(h1_candidates)

    rows = []

    for _, item in selected.iterrows():
        code = str(item["CodeX"]).strip()
        base = snapshot.get(code)

        if not base:
            print(f"LOW-CxV missing 09:30 snapshot: {code}")
            continue

        price = pd.to_numeric(base.get("Price"), errors="coerce")

        if pd.isna(price) or price <= 0:
            print(f"LOW-CxV invalid price: {code}")
            continue

        rows.append({
            "StrategyVersion": "H1-LOW-CxV",
            "DataType": "FORWARD",
            "DetectionDate": date,
            "SnapshotTime": "09:30",
            "Code": code,
            "Name": str(item.get("NameX", "")),
            "Rank": int(item["LowCxVRank"]),
            "RankGroup": "LOW-CxV",
            "SnapshotPrice": float(price),
            "Change": float(item["ChangeX"]),
            "VolumeRatio": float(item["VolumeX"]),
            "CxV": float(item["CxV"]),
            "LimitUpPrice": "",
            "LimitUpRoomPct": "",
            "TakeProfitPct": 10.0,
            "StopLossPct": -3.0,
            "HitPlus10Time": "",
            "HitMinus3Time": "",
            "ExitType": "",
            "ReturnPct": "",
            "MaxHighPct": "",
            "MinLowPct": "",
            "ClosePct": "",
        })

    if not rows:
        print("LOW-CxV tracking: no valid candidates")
        return 0

    incoming = pd.DataFrame(rows, columns=COLUMNS)

    if OUTPUT_PATH.exists():
        existing = pd.read_csv(
            OUTPUT_PATH,
            dtype={"Code": str, "SnapshotTime": str},
        )
    else:
        existing = pd.DataFrame(columns=COLUMNS)

    keys = [
        "StrategyVersion", "DetectionDate",
        "SnapshotTime", "Code",
    ]

    combined = pd.concat(
        [existing, incoming], ignore_index=True
    ).drop_duplicates(subset=keys, keep="first")

    combined = combined.sort_values(
        ["DetectionDate", "SnapshotTime", "Rank"]
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(
        OUTPUT_PATH, index=False, encoding="utf-8-sig"
    )

    print(f"LOW-CxV tracking saved: {len(rows)} candidates")
    return len(rows)
