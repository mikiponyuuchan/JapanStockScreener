from datetime import datetime
from pathlib import Path

import pandas as pd


BASELINE_FILE = Path("data/cache/morning_baseline.csv")
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


def _prepare_history(df):
    if df is None or df.empty:
        return None

    work = df.copy()

    if "Date" not in work.columns:
        work = work.reset_index()

    if "Date" not in work.columns:
        return None

    required = [
        "Date",
        "High",
        "Close",
        "Volume",
    ]

    for col in required:
        if col not in work.columns:
            return None

    work["Date"] = pd.to_datetime(
        work["Date"],
        errors="coerce",
    )

    work = (
        work.dropna(
            subset=[
                "Date",
                "High",
                "Close",
                "Volume",
            ]
        )
        .sort_values("Date")
        .drop_duplicates(
            subset=["Date"],
            keep="last",
        )
    )

    if work.empty:
        return None

    return work


def save_morning_baseline(
    history_map,
    stocks=None,
):
    """
    Save confirmed daily baseline data for the next morning screener.

    Safety rules:
    - Save only on weekdays after 15:30.
    - Save only when the latest Yahoo daily row is today.
    - Morning/intraday runs never overwrite the baseline.
    """

    now = datetime.now()

    if now.weekday() >= 5:
        return False

    if (
        now.hour < MARKET_CLOSE_HOUR
        or (
            now.hour == MARKET_CLOSE_HOUR
            and now.minute < MARKET_CLOSE_MINUTE
        )
    ):
        return False

    if not history_map:
        return False

    today = pd.Timestamp(
        now.date()
    )

    name_map = {}

    if (
        stocks is not None
        and not stocks.empty
    ):
        code_col = "\u30b3\u30fc\u30c9"
        name_col = "\u9298\u67c4\u540d"

        if (
            code_col in stocks.columns
            and name_col in stocks.columns
        ):
            name_map = dict(
                zip(
                    stocks[code_col].astype(str),
                    stocks[name_col].astype(str),
                )
            )

    rows = []

    latest_dates = []

    for code, raw_df in history_map.items():
        df = _prepare_history(raw_df)

        if df is None or df.empty:
            continue

        latest_date = (
            pd.Timestamp(df["Date"].iloc[-1])
            .tz_localize(None)
            .normalize()
        )

        latest_dates.append(
            latest_date
        )

        if latest_date != today:
            continue

        closes = pd.to_numeric(
            df["Close"],
            errors="coerce",
        )

        highs = pd.to_numeric(
            df["High"],
            errors="coerce",
        )

        volumes = pd.to_numeric(
            df["Volume"],
            errors="coerce",
        )

        if (
            closes.tail(25).isna().any()
            or highs.tail(30).isna().any()
            or volumes.tail(5).isna().any()
        ):
            continue

        if len(df) < 30:
            continue

        rows.append(
            {
                "Code": str(code),
                "Name": name_map.get(
                    str(code),
                    "",
                ),
                "BaseDate": latest_date.strftime(
                    "%Y-%m-%d"
                ),
                "PrevClose": float(
                    closes.iloc[-1]
                ),
                "Prev20High": float(
                    highs.tail(20).max()
                ),
                "Prev30High": float(
                    highs.tail(30).max()
                ),
                "MA5": float(
                    closes.tail(5).mean()
                ),
                "MA25": float(
                    closes.tail(25).mean()
                ),
                "Prev5AvgVolume": float(
                    volumes.tail(5).mean()
                ),
            }
        )

    if not rows:
        return False

    baseline_df = pd.DataFrame(rows)

    baseline_df = (
        baseline_df
        .drop_duplicates(
            subset=["Code"],
            keep="last",
        )
        .sort_values("Code")
        .reset_index(drop=True)
    )

    BASELINE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    baseline_df.to_csv(
        BASELINE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "Morning baseline saved : "
        f"{BASELINE_FILE} "
        f"({len(baseline_df)} stocks)"
    )

    return True
