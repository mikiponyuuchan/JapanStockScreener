from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


TRACKING_PATH = Path(
    "data/tracking/"
    "short_sale_trigger_rebound_ver1.csv"
)

TAKE_PCT = 5.0
STOP_PCT = -3.0

ENTRY_HOUR = 9
ENTRY_MINUTE = 30


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def normalize_intraday(df):
    if df is None or df.empty:
        return None

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        df.columns = [
            col[0]
            for col in df.columns
        ]

    needed = [
        "Open",
        "High",
        "Low",
        "Close",
    ]

    if not all(
        col in df.columns
        for col in needed
    ):
        return None

    idx = pd.to_datetime(
        df.index
    )

    try:
        if idx.tz is not None:
            idx = (
                idx
                .tz_convert(
                    "Asia/Tokyo"
                )
                .tz_localize(None)
            )
    except Exception:
        try:
            idx = idx.tz_localize(
                None
            )
        except Exception:
            pass

    out = df.copy()
    out.index = idx

    for col in needed:
        out[col] = pd.to_numeric(
            out[col],
            errors="coerce",
        )

    out = out.dropna(
        subset=needed
    )

    return out


def download_5m(code, date_text):
    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    end = (
        start
        + timedelta(days=1)
    )

    try:
        df = yf.download(
            f"{code}.T",
            start=start.strftime(
                "%Y-%m-%d"
            ),
            end=end.strftime(
                "%Y-%m-%d"
            ),
            interval="5m",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:
        print(
            f"5M ERROR "
            f"{code} {date_text} : "
            f"{exc}"
        )
        return None

    return normalize_intraday(
        df
    )


def download_daily(
    code,
    date_text,
):
    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    end = (
        start
        + timedelta(days=1)
    )

    try:
        df = yf.download(
            f"{code}.T",
            start=start.strftime(
                "%Y-%m-%d"
            ),
            end=end.strftime(
                "%Y-%m-%d"
            ),
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:
        print(
            f"DAILY ERROR "
            f"{code} {date_text} : "
            f"{exc}"
        )
        return None

    if df is None or df.empty:
        return None

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        df.columns = [
            col[0]
            for col in df.columns
        ]

    return df


def time_text(value):
    if value is None:
        return ""

    return pd.Timestamp(
        value
    ).strftime("%H:%M")


def analyze_trade(
    bars,
    daily,
):
    if bars is None or bars.empty:
        return {
            "DataStatus":
                "NO_5M_DATA",
        }

    entry_mask = (
        (bars.index.hour == ENTRY_HOUR)
        & (
            bars.index.minute
            == ENTRY_MINUTE
        )
    )

    entry_rows = bars[
        entry_mask
    ]

    if entry_rows.empty:
        return {
            "DataStatus":
                "NO_0930_BAR",
            "Last5mTime":
                time_text(
                    bars.index.max()
                ),
        }

    entry_ts = (
        entry_rows.index[0]
    )

    entry_price = float(
        entry_rows.iloc[0]["Open"]
    )

    after = bars[
        bars.index >= entry_ts
    ].copy()

    if after.empty:
        return {
            "DataStatus":
                "NO_POST0930_DATA",
        }

    take_price = (
        entry_price
        * (
            1.0
            + TAKE_PCT / 100.0
        )
    )

    stop_price = (
        entry_price
        * (
            1.0
            + STOP_PCT / 100.0
        )
    )

    take_hits = after[
        after["High"]
        >= take_price
    ]

    stop_hits = after[
        after["Low"]
        <= stop_price
    ]

    take_time = (
        take_hits.index[0]
        if not take_hits.empty
        else None
    )

    stop_time = (
        stop_hits.index[0]
        if not stop_hits.empty
        else None
    )

    last_time = after.index.max()

    max_high_pct = (
        float(
            after["High"].max()
        )
        / entry_price
        - 1.0
    ) * 100.0

    min_low_pct = (
        float(
            after["Low"].min()
        )
        / entry_price
        - 1.0
    ) * 100.0

    daily_close = None

    if (
        daily is not None
        and not daily.empty
        and "Close" in daily.columns
    ):
        value = pd.to_numeric(
            daily["Close"].iloc[-1],
            errors="coerce",
        )

        if pd.notna(value):
            daily_close = float(
                value
            )

    close_pct = pd.NA

    if (
        daily_close is not None
        and entry_price > 0
    ):
        close_pct = (
            daily_close
            / entry_price
            - 1.0
        ) * 100.0

    if (
        take_time is not None
        and stop_time is not None
    ):
        if take_time < stop_time:
            exit_type = "TAKE"
            return_pct = TAKE_PCT
            data_status = "OK"

        elif stop_time < take_time:
            exit_type = "STOP"
            return_pct = STOP_PCT
            data_status = "OK"

        else:
            exit_type = "SAME_BAR"
            return_pct = pd.NA
            data_status = "SAME_BAR"

    elif take_time is not None:
        exit_type = "TAKE"
        return_pct = TAKE_PCT
        data_status = "OK"

    elif stop_time is not None:
        exit_type = "STOP"
        return_pct = STOP_PCT
        data_status = "OK"

    else:
        # If the intraday series reaches the late
        # session, CLOSE is accepted directly.
        late_enough = (
            (
                last_time.hour > 15
            )
            or (
                last_time.hour == 15
                and last_time.minute >= 20
            )
        )

        if late_enough:
            exit_type = "CLOSE"
            return_pct = close_pct
            data_status = "OK"

        else:
            # Conservative fallback:
            # only accept CLOSE when full-day OHLC
            # proves TP and SL were not reached
            # anywhere during the day.
            safe_no_hit = False

            if (
                daily is not None
                and not daily.empty
                and "High" in daily.columns
                and "Low" in daily.columns
            ):
                day_high = pd.to_numeric(
                    daily["High"].iloc[-1],
                    errors="coerce",
                )

                day_low = pd.to_numeric(
                    daily["Low"].iloc[-1],
                    errors="coerce",
                )

                if (
                    pd.notna(day_high)
                    and pd.notna(day_low)
                    and float(day_high)
                    < take_price
                    and float(day_low)
                    > stop_price
                ):
                    safe_no_hit = True

            if safe_no_hit:
                exit_type = "CLOSE"
                return_pct = close_pct
                data_status = (
                    "OK_DAILY_CONFIRMED"
                )
            else:
                exit_type = (
                    "DATA_INCOMPLETE"
                )
                return_pct = pd.NA
                data_status = (
                    "DATA_INCOMPLETE"
                )

    return {
        "EntryPrice":
            entry_price,
        "TakePrice":
            take_price,
        "StopPrice":
            stop_price,
        "HitTakeTime":
            time_text(take_time),
        "HitStopTime":
            time_text(stop_time),
        "ExitType":
            exit_type,
        "ReturnPct":
            return_pct,
        "MaxHighPct":
            max_high_pct,
        "MinLowPct":
            min_low_pct,
        "ClosePct":
            close_pct,
        "Last5mTime":
            time_text(last_time),
        "DataStatus":
            data_status,
    }


def main():
    if not TRACKING_PATH.exists():
        print(
            "No SSR-Ver1 tracking file."
        )
        return

    df = pd.read_csv(
        TRACKING_PATH,
        dtype={
            "Code": str,
        },
        encoding="utf-8-sig",
        low_memory=False,
    )

    if df.empty:
        print(
            "SSR-Ver1 tracking is empty."
        )
        return

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    updated = 0

    for idx, row in df.iterrows():
        status = str(
            row.get(
                "DataStatus",
                "",
            )
        ).strip()

        if status not in [
            "",
            "PENDING",
            "nan",
        ]:
            continue

        trade_date = str(
            row.get(
                "TradeDate",
                "",
            )
        ).strip()

        if not trade_date:
            continue

        if trade_date > today:
            continue

        code = normalize_code(
            row["Code"]
        )

        bars = download_5m(
            code,
            trade_date,
        )

        daily = download_daily(
            code,
            trade_date,
        )

        result = analyze_trade(
            bars,
            daily,
        )

        for key, value in result.items():
            df.at[
                idx,
                key,
            ] = value

        updated += 1

        print(
            f"{trade_date} "
            f"{code} "
            f"{result.get('ExitType', '')} "
            f"{result.get('ReturnPct', '')} "
            f"[{result.get('DataStatus', '')}]"
        )

    if updated == 0:
        print(
            "No pending SSR-Ver1 trades."
        )
        return

    df["Code"] = (
        df["Code"]
        .map(normalize_code)
    )

    df = df.sort_values(
        [
            "TradeDate",
            "Code",
        ]
    )

    df.to_csv(
        TRACKING_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print("SSR VER1 FORWARD TRACKING")
    print("=" * 70)

    forward = df[
        df["DataType"]
        == "FORWARD"
    ].copy()

    valid_ret = pd.to_numeric(
        forward["ReturnPct"],
        errors="coerce",
    ).dropna()

    print(
        "Forward rows :",
        len(forward),
    )

    print(
        "Valid trades :",
        len(valid_ret),
    )

    if len(valid_ret):
        print(
            "Win rate    :",
            f"{(valid_ret > 0).mean() * 100:.1f}%"
        )
        print(
            "Mean return :",
            f"{valid_ret.mean():.2f}%"
        )
        print(
            "Median      :",
            f"{valid_ret.median():.2f}%"
        )
        print(
            "Total return:",
            f"{valid_ret.sum():.2f}%"
        )

    print()
    print("Data status")
    print(
        forward[
            "DataStatus"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print()
    print(
        "Saved       :",
        TRACKING_PATH,
    )


if __name__ == "__main__":
    main()
