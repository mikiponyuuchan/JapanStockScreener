from pathlib import Path
import pandas as pd

from intraday.h1_low_cxv_selector import select_h1_low_cxv


SOURCE_PATH = Path("data/tracking/h1_top10_tracking.csv")
OUTPUT_PATH = Path("data/tracking/h1_low_cxv_tracking.csv")
FORWARD_START = "2026-10-21"

OUTCOME_COLUMNS = [
    "HitPlus10Time",
    "HitMinus3Time",
    "ExitType",
    "ReturnPct",
    "MaxHighPct",
    "MinLowPct",
    "ClosePct",
]


def build_low_cxv(source):
    work = source.copy()

    work["DetectionDate"] = (
        work["DetectionDate"].astype(str)
    )

    work = work[
        work["DetectionDate"] >= FORWARD_START
    ].copy()

    if work.empty:
        return work

    work["Rank"] = pd.to_numeric(
        work["Rank"], errors="coerce"
    )

    rows = []

    for (date, snapshot), group in work.groupby(
        ["DetectionDate", "SnapshotTime"],
        sort=True,
    ):
        top10 = group.sort_values("Rank").head(10).copy()

        if len(top10) != 10:
            print(f"SKIP incomplete TOP10: {date} {snapshot}")
            continue

        top10["CodeX"] = top10["Code"].astype(str)
        top10["ChangeX"] = top10["Change"]

        selected = select_h1_low_cxv(top10)

        for _, item in selected.iterrows():
            row = item.to_dict()
            row["StrategyVersion"] = "H1-LOW-CxV"
            row["DataType"] = "FORWARD"
            row["Rank"] = int(item["LowCxVRank"])
            row["RankGroup"] = "LOW-CxV"
            for col in OUTCOME_COLUMNS:
                row[col] = ""
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=source.columns)

    result = pd.DataFrame(rows)

    return result.reindex(columns=source.columns)


def main():
    if not SOURCE_PATH.exists():
        print(f"Source not found: {SOURCE_PATH}")
        return

    source = pd.read_csv(
        SOURCE_PATH,
        dtype={"Code": str, "SnapshotTime": str},
        low_memory=False,
    )

    incoming = build_low_cxv(source)

    if incoming.empty:
        print("No LOW-CxV candidates from 2026-10-21 onward.")
        return

    if OUTPUT_PATH.exists():
        existing = pd.read_csv(
            OUTPUT_PATH,
            dtype={"Code": str, "SnapshotTime": str},
            low_memory=False,
        )
    else:
        existing = pd.DataFrame(columns=incoming.columns)

    key = [
        "StrategyVersion",
        "DetectionDate",
        "SnapshotTime",
        "Code",
    ]

    combined = pd.concat(
        [existing, incoming],
        ignore_index=True,
    )

    combined = combined.drop_duplicates(
        subset=key,
        keep="first",
    )

    combined = combined.sort_values(
        ["DetectionDate", "SnapshotTime", "Rank"]
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    combined.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"LOW-CxV saved: {OUTPUT_PATH}")
    print(f"Total rows: {len(combined)}")


if __name__ == "__main__":
    main()
