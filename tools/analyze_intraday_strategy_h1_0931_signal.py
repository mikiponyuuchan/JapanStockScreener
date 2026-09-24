from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


TRACKING_FILE = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

OUTPUT_FILE = Path(
    "data/analysis/intraday_strategy_h1_0931_signal.csv"
)


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def download_1m(code, date_text):
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
            interval="1m",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:
        print(
            f"DOWNLOAD ERROR "
            f"{date_text} {code} : {exc}"
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

    idx = pd.to_datetime(df.index)

    try:
        if idx.tz is not None:
            idx = idx.tz_convert(
                "Asia/Tokyo"
            ).tz_localize(None)
    except Exception:
        try:
            idx = idx.tz_localize(None)
        except Exception:
            pass

    df = df.copy()
    df.index = idx

    return df


def pct(value, base):
    if (
        pd.isna(value)
        or pd.isna(base)
        or base <= 0
    ):
        return pd.NA

    return (
        float(value) / float(base) - 1
    ) * 100


def get_0931_bar(
    bars,
    date_text,
):
    target = datetime.strptime(
        f"{date_text} 09:31",
        "%Y-%m-%d %H:%M",
    )

    if target not in bars.index:
        return None

    row = bars.loc[target]

    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]

    return row


def main():
    print("=" * 76)
    print("H1 09:31 SIGNAL ANALYSIS")
    print("=" * 76)

    if not TRACKING_FILE.exists():
        raise RuntimeError(
            f"Not found : {TRACKING_FILE}"
        )

    df = pd.read_csv(
        TRACKING_FILE,
        dtype={"Code": str},
        low_memory=False,
    )

    if "DataType" in df.columns:
        df = df[
            df["DataType"]
            .astype(str)
            .str.upper()
            .eq("FORWARD")
        ].copy()

    # 結果確定済みだけを使用
    df["ReturnPctX"] = pd.to_numeric(
        df["ReturnPct"],
        errors="coerce",
    )

    df = df[
        df["ReturnPctX"].notna()
    ].copy()

    print(
        f"Forward completed : {len(df)}"
    )

    results = []

    for _, row in df.iterrows():

        date_text = str(
            row["DetectionDate"]
        )

        code = normalize_code(
            row["Code"]
        )

        snapshot_price = pd.to_numeric(
            row["SnapshotPrice"],
            errors="coerce",
        )

        if (
            pd.isna(snapshot_price)
            or snapshot_price <= 0
        ):
            continue

        bars = download_1m(
            code,
            date_text,
        )

        if bars is None or bars.empty:
            print(
                f"NO BARS : "
                f"{date_text} {code}"
            )
            continue

        bar = get_0931_bar(
            bars,
            date_text,
        )

        if bar is None:
            print(
                f"NO 09:31 BAR : "
                f"{date_text} {code}"
            )
            continue

        open_price = pd.to_numeric(
            bar.get("Open"),
            errors="coerce",
        )

        high_price = pd.to_numeric(
            bar.get("High"),
            errors="coerce",
        )

        low_price = pd.to_numeric(
            bar.get("Low"),
            errors="coerce",
        )

        close_price = pd.to_numeric(
            bar.get("Close"),
            errors="coerce",
        )

        if any(
            pd.isna(x)
            for x in [
                open_price,
                high_price,
                low_price,
                close_price,
            ]
        ):
            continue

        close_pct = pct(
            close_price,
            snapshot_price,
        )

        high_pct = pct(
            high_price,
            snapshot_price,
        )

        low_pct = pct(
            low_price,
            snapshot_price,
        )

        open_pct = pct(
            open_price,
            snapshot_price,
        )

        range_pct = (
            (
                float(high_price)
                / float(low_price)
                - 1
            )
            * 100
            if float(low_price) > 0
            else pd.NA
        )

        body_pct = pct(
            close_price,
            open_price,
        )

        results.append({
            "DetectionDate":
                date_text,
            "Code":
                code,
            "Name":
                row["Name"],
            "Rank":
                row["Rank"],
            "SnapshotPrice":
                snapshot_price,
            "Change":
                row["Change"],
            "VolumeRatio":
                row["VolumeRatio"],
            "CxV":
                row["CxV"],

            "Open0931":
                open_price,
            "High0931":
                high_price,
            "Low0931":
                low_price,
            "Close0931":
                close_price,

            "Open0931Pct":
                open_pct,
            "High0931Pct":
                high_pct,
            "Low0931Pct":
                low_pct,
            "Close0931Pct":
                close_pct,

            "Range0931Pct":
                range_pct,
            "Body0931Pct":
                body_pct,

            "HoldSnapshot0931":
                bool(
                    close_price
                    >= snapshot_price
                ),

            "Green0931":
                bool(
                    close_price
                    >= open_price
                ),

            "ExitType":
                row["ExitType"],
            "ReturnPct":
                row["ReturnPctX"],
            "MaxHighPct":
                row["MaxHighPct"],
            "MinLowPct":
                row["MinLowPct"],
            "ClosePct":
                row["ClosePct"],
        })

    out = pd.DataFrame(
        results
    )

    if out.empty:
        print("No results")
        return

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 76)
    print("09:31 BAR vs H1 RESULT")
    print("=" * 76)

    columns = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Change",
        "CxV",
        "Open0931Pct",
        "High0931Pct",
        "Low0931Pct",
        "Close0931Pct",
        "Body0931Pct",
        "HoldSnapshot0931",
        "ExitType",
        "ReturnPct",
    ]

    print(
        out[columns]
        .sort_values(
            "ReturnPct",
            ascending=False,
        )
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 76)
    print("HOLD SNAPSHOT COMPARISON")
    print("=" * 76)

    for flag in [
        True,
        False,
    ]:
        x = out[
            out["HoldSnapshot0931"]
            == flag
        ]

        returns = pd.to_numeric(
            x["ReturnPct"],
            errors="coerce",
        ).dropna()

        print()
        print(
            f"HoldSnapshot0931 = "
            f"{flag}"
        )
        print(
            f"Count       : "
            f"{len(returns)}"
        )

        if returns.empty:
            continue

        print(
            f"Mean return : "
            f"{returns.mean():.2f}%"
        )
        print(
            f"Median      : "
            f"{returns.median():.2f}%"
        )
        print(
            f"Win rate    : "
            f"{(returns > 0).mean() * 100:.1f}%"
        )

        stop_count = (
            x["ExitType"]
            .astype(str)
            .eq("STOP")
            .sum()
        )

        take_count = (
            x["ExitType"]
            .astype(str)
            .eq("TAKE")
            .sum()
        )

        print(
            f"TAKE / STOP : "
            f"{take_count} / "
            f"{stop_count}"
        )

    print()
    print(
        f"Saved : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()