
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


PLAN_DIR = Path("data/trading")

TRACKING_PATH = Path(
    "data/tracking/j1_trade_ver1_tracking.csv"
)

TAKE_PCT = 3.0
STOP_PCT = -5.0


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def download_5m(code, date_text):
    ticker = f"{code}.T"

    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    end = start + timedelta(days=1)

    try:
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="5m",
            progress=False,
            auto_adjust=False,
            threads=False,
        )

    except Exception as exc:
        print(
            f"DOWNLOAD ERROR "
            f"{code} {date_text} : {exc}"
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

    idx = pd.to_datetime(df.index)

    try:
        if idx.tz is not None:
            idx = (
                idx
                .tz_convert("Asia/Tokyo")
                .tz_localize(None)
            )
    except Exception:
        try:
            idx = idx.tz_localize(None)
        except Exception:
            pass

    df = df.copy()
    df.index = idx

    return df


def time_text(ts):
    if ts is None:
        return ""

    return pd.Timestamp(
        ts
    ).strftime("%H:%M")


def analyze_trade(bars):
    if bars is None or bars.empty:
        return None

    work = bars.copy()

    for col in [
        "Open",
        "High",
        "Low",
        "Close",
    ]:
        work[col] = pd.to_numeric(
            work[col],
            errors="coerce",
        )

    work = work.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    if work.empty:
        return None

    entry_price = float(
        work["Open"].iloc[0]
    )

    high = work["High"]
    low = work["Low"]
    close = work["Close"]

    take_price = (
        entry_price
        * (1.0 + TAKE_PCT / 100)
    )

    stop_price = (
        entry_price
        * (1.0 + STOP_PCT / 100)
    )

    take_hits = work[
        high >= take_price
    ]

    stop_hits = work[
        low <= stop_price
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

    if (
        take_time is not None
        and stop_time is not None
    ):
        if take_time < stop_time:
            exit_type = "TAKE"
            return_pct = TAKE_PCT

        elif stop_time < take_time:
            exit_type = "STOP"
            return_pct = STOP_PCT

        else:
            exit_type = "SAME_BAR"
            return_pct = pd.NA

    elif take_time is not None:
        exit_type = "TAKE"
        return_pct = TAKE_PCT

    elif stop_time is not None:
        exit_type = "STOP"
        return_pct = STOP_PCT

    else:
        exit_type = "CLOSE"

        last_close = float(
            close.iloc[-1]
        )

        return_pct = (
            last_close
            / entry_price
            - 1.0
        ) * 100

    max_high_pct = (
        float(high.max())
        / entry_price
        - 1.0
    ) * 100

    min_low_pct = (
        float(low.min())
        / entry_price
        - 1.0
    ) * 100

    last_close = float(
        close.iloc[-1]
    )

    close_pct = (
        last_close
        / entry_price
        - 1.0
    ) * 100

    return {
        "EntryPrice":
            entry_price,
        "TakePrice":
            take_price,
        "StopPrice":
            stop_price,
        "HitPlus3Time":
            time_text(take_time),
        "HitMinus5Time":
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
    }


def load_plans():
    files = sorted(
        PLAN_DIR.glob(
            "*_j1_trade_plan.csv"
        )
    )

    if not files:
        return pd.DataFrame()

    frames = []

    for path in files:
        try:
            df = pd.read_csv(
                path,
                dtype={"Code": str},
                encoding="utf-8-sig",
                low_memory=False,
            )
        except Exception as exc:
            print(
                f"READ ERROR : "
                f"{path} : {exc}"
            )
            continue

        if df.empty:
            continue

        frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        ignore_index=True,
    )


def load_existing():
    if not TRACKING_PATH.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(
            TRACKING_PATH,
            dtype={"Code": str},
            encoding="utf-8-sig",
            low_memory=False,
        )
    except Exception:
        return pd.DataFrame()


def main():
    plans = load_plans()

    if plans.empty:
        print("No J1 Trade Ver1 plans.")
        return

    required = [
        "DetectionDate",
        "Code",
        "Name",
        "Change1",
        "DetectionVolumeVsPre5",
    ]

    missing = [
        col
        for col in required
        if col not in plans.columns
    ]

    if missing:
        print(
            "Missing columns :",
            missing,
        )
        return

    plans["Code"] = (
        plans["Code"]
        .map(normalize_code)
    )

    existing = load_existing()

    done_keys = set()

    if not existing.empty:
        for _, row in existing.iterrows():
            done_keys.add(
                (
                    str(row["DetectionDate"]),
                    normalize_code(
                        row["Code"]
                    ),
                )
            )

    rows = []

    for _, row in plans.iterrows():
        detection_date = str(
            row["DetectionDate"]
        ).strip()

        code = normalize_code(
            row["Code"]
        )

        key = (
            detection_date,
            code,
        )

        if key in done_keys:
            continue

        base = datetime.strptime(
            detection_date,
            "%Y-%m-%d",
        )

        trade_date = None
        bars = None

        for offset in range(1, 8):
            candidate = (
                base
                + timedelta(
                    days=offset
                )
            )

            if candidate.weekday() >= 5:
                continue

            candidate_text = (
                candidate.strftime(
                    "%Y-%m-%d"
                )
            )

            candidate_bars = (
                download_5m(
                    code,
                    candidate_text,
                )
            )

            if (
                candidate_bars is not None
                and not candidate_bars.empty
            ):
                trade_date = (
                    candidate_text
                )
                bars = (
                    candidate_bars
                )
                break

        if (
            trade_date is None
            or bars is None
        ):
            print(
                f"PENDING : "
                f"{detection_date} "
                f"{code}"
            )
            continue

        result = analyze_trade(
            bars
        )

        if result is None:
            print(
                f"NO BARS : "
                f"{detection_date} "
                f"{code}"
            )
            continue

        base_price = pd.to_numeric(
            row.get("BasePrice"),
            errors="coerce",
        )

        next_open_gap_pct = pd.NA

        if (
            pd.notna(base_price)
            and base_price > 0
        ):
            next_open_gap_pct = (
                result["EntryPrice"]
                / float(base_price)
                - 1.0
            ) * 100

        out = {
            "StrategyVersion":
                "J1-Trade-Ver1",
            "DetectionDate":
                detection_date,
            "TradeDate":
                trade_date,
            "Code":
                code,
            "Name":
                row["Name"],
            "BasePrice":
                base_price,
            "Change1":
                row["Change1"],
            "DetectionVolumeVsPre5":
                row[
                    "DetectionVolumeVsPre5"
                ],
            "NextOpenGapPct":
                next_open_gap_pct,
            "TakeProfitPct":
                TAKE_PCT,
            "StopLossPct":
                STOP_PCT,
        }

        out.update(
            result
        )

        rows.append(out)

        print(
            f"{detection_date} "
            f"{code} "
            f"{result['ExitType']} "
            f"{result['ReturnPct']}"
        )

    if not rows:
        print(
            "No new completed trades."
        )
        return

    incoming = pd.DataFrame(
        rows
    )

    if existing.empty:
        combined = incoming.copy()
    else:
        combined = pd.concat(
            [
                existing,
                incoming,
            ],
            ignore_index=True,
        )

    combined["Code"] = (
        combined["Code"]
        .map(normalize_code)
    )

    combined = combined.drop_duplicates(
        subset=[
            "StrategyVersion",
            "DetectionDate",
            "Code",
        ],
        keep="last",
    )

    combined = combined.sort_values(
        [
            "DetectionDate",
            "Code",
        ]
    )

    TRACKING_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_csv(
        TRACKING_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print("J1 TRADE VER1 TRACKING")
    print("=" * 70)
    print(
        "New rows    :",
        len(incoming),
    )
    print(
        "Total rows  :",
        len(combined),
    )

    ret = pd.to_numeric(
        combined["ReturnPct"],
        errors="coerce",
    ).dropna()

    if len(ret):
        print(
            "Win rate    :",
            f"{(ret > 0).mean() * 100:.1f}%"
        )
        print(
            "Mean return :",
            f"{ret.mean():.2f}%"
        )
        print(
            "Median      :",
            f"{ret.median():.2f}%"
        )
        print(
            "Total return:",
            f"{ret.sum():.2f}%"
        )

    print(
        "Saved       :",
        TRACKING_PATH,
    )


if __name__ == "__main__":
    main()
