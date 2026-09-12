import argparse
import time
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_backtest_panel.csv"
)

OUTPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_backtest_preprice.csv"
)


def normalize_code(value):
    s = str(value).strip()

    if s.endswith(".0"):
        s = s[:-2]

    return s


def get_pre_returns(code, detection_date):
    ticker = f"{code}.T"

    target = pd.Timestamp(
        detection_date
    )

    start = (
        target
        - pd.Timedelta(days=45)
    )

    end = (
        target
        + pd.Timedelta(days=1)
    )

    try:
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return None, None

    if df is None or df.empty:
        return None, None

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        try:
            close = df["Close"].iloc[:, 0]
        except Exception:
            return None, None
    else:
        if "Close" not in df.columns:
            return None, None

        close = df["Close"]

    close = pd.to_numeric(
        close,
        errors="coerce",
    ).dropna()

    close.index = pd.to_datetime(
        close.index
    ).tz_localize(None)

    close = close[
        close.index <= target
    ]

    if close.empty:
        return None, None

    base = float(
        close.iloc[-1]
    )

    pre5 = None
    pre20 = None

    if len(close) >= 6:
        old = float(
            close.iloc[-6]
        )

        if old != 0:
            pre5 = (
                base / old - 1
            ) * 100

    if len(close) >= 21:
        old = float(
            close.iloc[-21]
        )

        if old != 0:
            pre20 = (
                base / old - 1
            ) * 100

    return pre5, pre20


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
    )

    args = parser.parse_args()

    df = pd.read_csv(
        INPUT,
        dtype={"Code": str},
    )

    df["Code"] = (
        df["Code"]
        .map(normalize_code)
    )

    keys = (
        df[
            [
                "DetectionDate",
                "Code",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    cache = {}

    total = len(keys)

    print("=" * 78)
    print("EARNINGS PRE-PRICE ANALYSIS")
    print("=" * 78)
    print("Targets :", total)

    for i, row in keys.iterrows():
        key = (
            row["DetectionDate"],
            row["Code"],
        )

        pre5, pre20 = get_pre_returns(
            row["Code"],
            row["DetectionDate"],
        )

        cache[key] = (
            pre5,
            pre20,
        )

        if (
            (i + 1) % 20 == 0
            or i + 1 == total
        ):
            print(
                f"{i + 1} / {total}"
            )

        time.sleep(
            args.sleep
        )

    df["Pre5Pct"] = df.apply(
        lambda r: cache.get(
            (
                r["DetectionDate"],
                r["Code"],
            ),
            (None, None),
        )[0],
        axis=1,
    )

    df["Pre20Pct"] = df.apply(
        lambda r: cache.get(
            (
                r["DetectionDate"],
                r["Code"],
            ),
            (None, None),
        )[1],
        axis=1,
    )

    df.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("Pre5 available  :", df["Pre5Pct"].notna().sum())
    print("Pre20 available :", df["Pre20Pct"].notna().sum())
    print("Saved :", OUTPUT)


if __name__ == "__main__":
    main()
