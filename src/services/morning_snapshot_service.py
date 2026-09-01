from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf


INTRADAY_SNAPSHOT_DIR = Path(
    "data/tracking/morning_intraday_snapshots"
)


def _find_column(df, candidates):
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _get_intraday_snapshot(code, target_date):
    """
    Yahoo 1-minute data snapshot for morning validation.

    This is validation-only data.
    It does not affect screener scores.
    """

    fetch_time = datetime.now()

    result = {
        "IntradayFetchTime": fetch_time.strftime("%H:%M:%S"),
        "IntradayStatus": "",
        "HasTradeToday": False,
        "FirstTradeTime": "",
        "FirstTradePrice": pd.NA,
        "LastTradeTime": "",
        "LastTradePrice": pd.NA,
        "IntradayOpen": pd.NA,
        "IntradayHighSoFar": pd.NA,
        "IntradayLowSoFar": pd.NA,
        "IntradayVolumeSoFar": pd.NA,
    }

    try:
        ticker = f"{code}.T"

        df = yf.Ticker(
            ticker
        ).history(
            period="1d",
            interval="1m",
            auto_adjust=False,
        )

        if df is None or df.empty:
            result["IntradayStatus"] = (
                "NO_TRADE_TODAY_OR_NO_DATA"
            )
            return result

        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        for column in required_columns:
            if column not in df.columns:
                result["IntradayStatus"] = (
                    f"MISSING_COLUMN_{column}"
                )
                return result

        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )

        if df.empty:
            result["IntradayStatus"] = (
                "NO_TRADE_TODAY_OR_NO_DATA"
            )
            return result

        # Yahoo timestamp -> Japan time
        index = df.index

        if index.tz is not None:
            index = index.tz_convert(
                "Asia/Tokyo"
            )

        df = df.copy()
        df.index = index

        # Today's regular-session bars only
        today_mask = (
            pd.Series(
                df.index.date,
                index=df.index,
            )
            == target_date
        )

        df = df.loc[
            today_mask.to_numpy()
        ]

        if df.empty:
            result["IntradayStatus"] = (
                "NO_TRADE_TODAY_OR_NO_DATA"
            )
            return result

        market_mask = (
            (df.index.time >= pd.Timestamp("09:00").time())
            &
            (df.index.time <= pd.Timestamp("15:30").time())
        )

        df = df.loc[market_mask]

        if df.empty:
            result["IntradayStatus"] = (
                "NO_REGULAR_SESSION_TRADE"
            )
            return result

        first_time = df.index[0]
        last_time = df.index[-1]

        result.update(
            {
                "IntradayStatus": "OK",
                "HasTradeToday": True,
                "FirstTradeTime": (
                    first_time.strftime("%H:%M:%S")
                ),
                "FirstTradePrice": float(
                    df["Open"].iloc[0]
                ),
                "LastTradeTime": (
                    last_time.strftime("%H:%M:%S")
                ),
                "LastTradePrice": float(
                    df["Close"].iloc[-1]
                ),
                "IntradayOpen": float(
                    df["Open"].iloc[0]
                ),
                "IntradayHighSoFar": float(
                    df["High"].max()
                ),
                "IntradayLowSoFar": float(
                    df["Low"].min()
                ),
                "IntradayVolumeSoFar": float(
                    df["Volume"].sum()
                ),
            }
        )

        return result

    except Exception as e:
        result["IntradayStatus"] = (
            f"ERROR:{type(e).__name__}"
        )
        return result


def save_morning_intraday_snapshot(
    initial_move_top20,
    candidate_snapshot_file=None,
):
    """
    Re-fetch 1-minute data for the actual morning TOP20.

    The candidate list itself is not recalculated.
    This records the real market state after TOP20 selection.
    """

    if (
        initial_move_top20 is None
        or initial_move_top20.empty
    ):
        return None

    started_at = datetime.now()

    if started_at.weekday() >= 5:
        return None

    if not (9 <= started_at.hour < 10):
        return None

    code_column = _find_column(
        initial_move_top20,
        [
            "\u30b3\u30fc\u30c9",
            "Code",
            "code",
        ],
    )

    if code_column is None:
        raise RuntimeError(
            "TOP20 code column not found"
        )

    snapshot = (
        initial_move_top20
        .copy()
        .reset_index(drop=True)
    )

    intraday_rows = []

    for _, row in snapshot.iterrows():
        code = str(
            row[code_column]
        ).strip()

        # Excel/CSV numeric conversion safety
        if code.endswith(".0"):
            code = code[:-2]

        intraday = _get_intraday_snapshot(
            code,
            started_at.date(),
        )

        intraday_rows.append(
            intraday
        )

    intraday_df = pd.DataFrame(
        intraday_rows
    )

    for column in intraday_df.columns:
        snapshot[column] = (
            intraday_df[column].values
        )

    completed_at = datetime.now()

    snapshot.insert(
        0,
        "IntradaySnapshotDate",
        started_at.strftime("%Y-%m-%d"),
    )

    snapshot.insert(
        1,
        "IntradaySnapshotStartedAt",
        started_at.strftime("%H:%M:%S"),
    )

    snapshot.insert(
        2,
        "IntradaySnapshotCompletedAt",
        completed_at.strftime("%H:%M:%S"),
    )

    if candidate_snapshot_file is not None:
        snapshot.insert(
            3,
            "CandidateSnapshotFile",
            str(candidate_snapshot_file),
        )

    INTRADAY_SNAPSHOT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    date_text = started_at.strftime(
        "%Y-%m-%d"
    )

    time_text = started_at.strftime(
        "%H%M"
    )

    output_file = (
        INTRADAY_SNAPSHOT_DIR
        / f"{date_text}_{time_text}_intraday_top20.csv"
    )

    number = 2

    while output_file.exists():
        output_file = (
            INTRADAY_SNAPSHOT_DIR
            / (
                f"{date_text}_{time_text}"
                f"_intraday_top20_{number}.csv"
            )
        )
        number += 1

    snapshot.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    ok_count = int(
        (
            snapshot["IntradayStatus"]
            == "OK"
        ).sum()
    )

    print(
        "Morning intraday snapshot :",
        output_file,
    )

    print(
        "Morning intraday OK :",
        f"{ok_count}/{len(snapshot)}",
    )

    return output_file
