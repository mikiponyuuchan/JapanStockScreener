from pathlib import Path
from datetime import date
import sys

import pandas as pd

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from services.yahoo_service import _download_history_batch


TRACKING_FILE = Path("data/tracking/j_type_tracking.csv")
MAX_DAYS = 5


def normalize_history(df):
    if df is None or df.empty:
        return None

    x = df.copy()

    if "Date" in x.columns:
        x["Date"] = pd.to_datetime(
            x["Date"],
            errors="coerce",
        )
        x = x.set_index("Date")

    x.index = pd.to_datetime(
        x.index,
        errors="coerce",
    )

    if getattr(x.index, "tz", None) is not None:
        x.index = x.index.tz_localize(None)

    x = x[
        ~x.index.isna()
    ].sort_index()

    return x


def ensure_columns(df):
    for day_no in range(1, MAX_DAYS + 1):
        for field in [
            "Open",
            "High",
            "Low",
            "Close",
            "OpenPct",
            "HighPct",
            "LowPct",
            "ClosePct",
        ]:
            col = f"Day{day_no}{field}"

            if col not in df.columns:
                df[col] = pd.NA

    for col in [
        "MaxHigh5Pct",
        "MinLow5Pct",
        "PeakDay5",
    ]:
        if col not in df.columns:
            df[col] = pd.NA

    return df


def pct(value, base):
    if (
        pd.isna(value)
        or pd.isna(base)
        or float(base) == 0
    ):
        return None

    return (
        float(value) / float(base) - 1.0
    ) * 100.0


def update_one_row(row, history, today):
    x = normalize_history(history)

    if x is None:
        return row, 0

    detection_date = pd.Timestamp(
        row["DetectionDate"]
    ).normalize()

    # Strict confirmed-data rule:
    # only dates AFTER detection and BEFORE today.
    future = x[
        (x.index.normalize() > detection_date)
        & (x.index.normalize() < today)
    ].copy()

    if future.empty:
        return row, 0

    # One row per trading date.
    future["_TradeDate"] = future.index.normalize()

    future = (
        future
        .sort_index()
        .drop_duplicates(
            subset=["_TradeDate"],
            keep="last",
        )
        .head(MAX_DAYS)
    )

    base = pd.to_numeric(
        row["BasePrice"],
        errors="coerce",
    )

    updated = 0

    for day_no, (_, bar) in enumerate(
        future.iterrows(),
        start=1,
    ):
        if day_no > MAX_DAYS:
            break

        close_col = f"Day{day_no}Close"

        # Never overwrite a confirmed DayN.
        if pd.notna(row.get(close_col)):
            continue

        values = {}

        for field in [
            "Open",
            "High",
            "Low",
            "Close",
        ]:
            value = pd.to_numeric(
                bar.get(field),
                errors="coerce",
            )

            values[field] = value

            row[f"Day{day_no}{field}"] = value
            row[f"Day{day_no}{field}Pct"] = pct(
                value,
                base,
            )

        if pd.notna(values["Close"]):
            updated += 1

    return row, updated


def calculate_summary(row):
    # Summary is calculated only after all 5 confirmed days exist.
    close_cols = [
        f"Day{i}Close"
        for i in range(1, MAX_DAYS + 1)
    ]

    if any(
        pd.isna(row.get(col))
        for col in close_cols
    ):
        return row

    high_pcts = []

    for day_no in range(1, MAX_DAYS + 1):
        value = pd.to_numeric(
            row.get(f"Day{day_no}HighPct"),
            errors="coerce",
        )

        if pd.notna(value):
            high_pcts.append(
                (day_no, float(value))
            )

    low_pcts = []

    for day_no in range(1, MAX_DAYS + 1):
        value = pd.to_numeric(
            row.get(f"Day{day_no}LowPct"),
            errors="coerce",
        )

        if pd.notna(value):
            low_pcts.append(
                (day_no, float(value))
            )

    if high_pcts:
        peak_day, max_high = max(
            high_pcts,
            key=lambda x: x[1],
        )

        row["MaxHigh5Pct"] = max_high
        row["PeakDay5"] = peak_day

    if low_pcts:
        _, min_low = min(
            low_pcts,
            key=lambda x: x[1],
        )

        row["MinLow5Pct"] = min_low

    return row


def main():
    if not TRACKING_FILE.exists():
        print(
            "Tracking file not found:",
            TRACKING_FILE,
        )
        return

    df = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig",
        low_memory=False,
    )

    required = [
        "JVersion",
        "DetectionDate",
        "Code",
        "Name",
        "BasePrice",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        print(
            "Missing columns:",
            missing,
        )
        return

    df = ensure_columns(df)

    df["Code"] = (
        df["Code"]
        .astype(str)
        .str.strip()
    )

    today = pd.Timestamp(
        date.today()
    ).normalize()

    # Only unfinished rows need Yahoo history.
    unfinished_mask = df["Day5Close"].isna()

    codes = sorted(
        df.loc[
            unfinished_mask,
            "Code",
        ]
        .dropna()
        .unique()
        .tolist()
    )

    print("=" * 72)
    print("J1 CONFIRMED DAILY TRACKING")
    print("=" * 72)
    print("Tracking rows      :", len(df))
    print("Unfinished rows    :", int(unfinished_mask.sum()))
    print("Yahoo codes        :", len(codes))
    print("Today excluded     :", today.date())

    if not codes:
        print("Nothing to update.")
        return

    history_map = _download_history_batch(
        codes,
        period="3mo",
        batch_size=100,
    )

    total_updates = 0
    updated_rows = 0

    for idx in df.index:
        if pd.notna(df.at[idx, "Day5Close"]):
            continue

        code = df.at[idx, "Code"]
        history = history_map.get(code)

        old_count = sum(
            pd.notna(
                df.at[idx, f"Day{i}Close"]
            )
            for i in range(1, MAX_DAYS + 1)
        )

        row, updates = update_one_row(
            df.loc[idx].copy(),
            history,
            today,
        )

        row = calculate_summary(row)

        for col in df.columns:
            if col in row.index:
                df.at[idx, col] = row[col]

        new_count = sum(
            pd.notna(
                df.at[idx, f"Day{i}Close"]
            )
            for i in range(1, MAX_DAYS + 1)
        )

        if new_count > old_count:
            updated_rows += 1
            total_updates += updates

    df.to_csv(
        TRACKING_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    completed = int(
        df["Day5Close"].notna().sum()
    )

    print()
    print("Updated rows       :", updated_rows)
    print("New confirmed days :", total_updates)
    print("Day5 completed     :", completed)
    print("Saved              :", TRACKING_FILE)


if __name__ == "__main__":
    main()
