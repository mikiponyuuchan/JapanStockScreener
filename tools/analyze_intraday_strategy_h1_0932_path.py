from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


INPUT_PATH = Path(
    "data/analysis/intraday_strategy_h1_0931_candle.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/intraday_strategy_h1_0932_path.csv"
)

LOWER_LIMIT = -3.0
UPPER_LIMIT = 1.0


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
            f"DOWNLOAD ERROR : "
            f"{date_text} {code} {exc}"
        )
        return None

    if df is None or df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
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

    return pd.Timestamp(ts).strftime("%H:%M")


def first_hit_time(work, price, pct):
    target = price * (1.0 + pct / 100.0)

    if pct >= 0:
        hits = work[
            pd.to_numeric(
                work["High"],
                errors="coerce",
            ) >= target
        ]
    else:
        hits = work[
            pd.to_numeric(
                work["Low"],
                errors="coerce",
            ) <= target
        ]

    if hits.empty:
        return None

    return hits.index[0]


def analyze_stock(row, bars):
    date_text = str(row["DetectionDate"])

    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    ).replace(
        hour=9,
        minute=32,
        second=0,
    )

    work = bars[
        bars.index >= start
    ].copy()

    if work.empty:
        return None

    work = work[
        work.index.time
        <= datetime.strptime(
            "15:30",
            "%H:%M",
        ).time()
    ].copy()

    if work.empty:
        return None

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

    # 09:32足の始値でエントリー
    entry_price = float(
        work.iloc[0]["Open"]
    )

    if entry_price <= 0:
        return None

    entry_time = work.index[0]

    max_high_pct = (
        float(work["High"].max())
        / entry_price
        - 1.0
    ) * 100.0

    min_low_pct = (
        float(work["Low"].min())
        / entry_price
        - 1.0
    ) * 100.0

    hit1 = first_hit_time(
        work,
        entry_price,
        1.0,
    )
    hit2 = first_hit_time(
        work,
        entry_price,
        2.0,
    )
    hit3 = first_hit_time(
        work,
        entry_price,
        3.0,
    )
    hit5 = first_hit_time(
        work,
        entry_price,
        5.0,
    )
    hit10 = first_hit_time(
        work,
        entry_price,
        10.0,
    )
    stop3 = first_hit_time(
        work,
        entry_price,
        -3.0,
    )

    # STOP到達前にどこまで上昇したか
    pre_stop_max_pct = pd.NA

    if stop3 is not None:
        before_stop = work[
            work.index < stop3
        ]

        if not before_stop.empty:
            pre_stop_max_pct = (
                float(
                    before_stop["High"].max()
                )
                / entry_price
                - 1.0
            ) * 100.0
        else:
            pre_stop_max_pct = 0.0

    close_price = float(
        work.iloc[-1]["Close"]
    )

    close_pct = (
        close_price
        / entry_price
        - 1.0
    ) * 100.0

    return {
        "DetectionDate":
            row["DetectionDate"],
        "Code":
            row["Code"],
        "Name":
            row["Name"],
        "Rank":
            row["Rank"],
        "Change":
            row["Change"],
        "VolumeRatio":
            row.get(
                "VolumeRatio",
                pd.NA,
            ),
        "CxV":
            row["CxV"],
        "Close0931Pct":
            row["Close0931Pct"],
        "Entry0932Time":
            time_text(entry_time),
        "Entry0932Price":
            entry_price,
        "MFE":
            max_high_pct,
        "MAE":
            min_low_pct,
        "HitPlus1Time":
            time_text(hit1),
        "HitPlus2Time":
            time_text(hit2),
        "HitPlus3Time":
            time_text(hit3),
        "HitPlus5Time":
            time_text(hit5),
        "HitPlus10Time":
            time_text(hit10),
        "HitMinus3Time":
            time_text(stop3),
        "PreStopMaxPct":
            pre_stop_max_pct,
        "ClosePct":
            close_pct,
        "ExitType0932":
            row["ExitType0932"],
        "ReturnPct0932":
            row["ReturnPct0932"],
    }


def print_summary(result):
    print()
    print("=" * 76)
    print("H1 09:32 PATH ANALYSIS")
    print("=" * 76)

    print(
        f"Band        : "
        f"{LOWER_LIMIT:+.1f}% "
        f"to {UPPER_LIMIT:+.1f}%"
    )
    print(
        f"Analyzed    : {len(result)}"
    )

    if result.empty:
        return

    print()
    print("=" * 76)
    print("MFE / MAE")
    print("=" * 76)

    print(
        f"MFE mean    : "
        f"{result['MFE'].mean():.2f}%"
    )
    print(
        f"MFE median  : "
        f"{result['MFE'].median():.2f}%"
    )
    print(
        f"MAE mean    : "
        f"{result['MAE'].mean():.2f}%"
    )
    print(
        f"MAE median  : "
        f"{result['MAE'].median():.2f}%"
    )

    print()
    print("=" * 76)
    print("UPSIDE REACH")
    print("=" * 76)

    for pct, col in [
        (1, "HitPlus1Time"),
        (2, "HitPlus2Time"),
        (3, "HitPlus3Time"),
        (5, "HitPlus5Time"),
        (10, "HitPlus10Time"),
    ]:
        count = (
            result[col]
            .fillna("")
            .astype(str)
            .str.len()
            .gt(0)
            .sum()
        )

        rate = (
            count / len(result) * 100
            if len(result)
            else 0
        )

        print(
            f"+{pct:>2}% reached : "
            f"{count:>2} / "
            f"{len(result)} "
            f"({rate:.1f}%)"
        )

    stops = result[
        result["HitMinus3Time"]
        .fillna("")
        .astype(str)
        .str.len()
        .gt(0)
    ].copy()

    print()
    print("=" * 76)
    print("STOP PATH")
    print("=" * 76)

    print(
        f"-3% reached : "
        f"{len(stops)} / {len(result)}"
    )

    if not stops.empty:
        pre = pd.to_numeric(
            stops["PreStopMaxPct"],
            errors="coerce",
        )

        print(
            f"Before STOP MFE mean   : "
            f"{pre.mean():.2f}%"
        )
        print(
            f"Before STOP MFE median : "
            f"{pre.median():.2f}%"
        )

        print()
        print("STOP DETAIL")

        cols = [
            "DetectionDate",
            "Code",
            "Name",
            "Rank",
            "Close0931Pct",
            "CxV",
            "Entry0932Price",
            "PreStopMaxPct",
            "HitMinus3Time",
            "MFE",
            "MAE",
        ]

        print(
            stops[cols]
            .sort_values(
                "PreStopMaxPct",
                ascending=False,
            )
            .to_string(index=False)
        )

    print()
    print("=" * 76)
    print("ALL DETAIL")
    print("=" * 76)

    cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "Close0931Pct",
        "CxV",
        "Entry0932Price",
        "MFE",
        "MAE",
        "HitPlus1Time",
        "HitPlus2Time",
        "HitPlus3Time",
        "HitPlus5Time",
        "HitPlus10Time",
        "HitMinus3Time",
        "PreStopMaxPct",
        "ExitType0932",
        "ReturnPct0932",
    ]

    print(
        result[cols]
        .sort_values(
            "MFE",
            ascending=False,
        )
        .to_string(index=False)
    )


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            INPUT_PATH
        )

    df = pd.read_csv(
        INPUT_PATH,
        low_memory=False,
    )

    close0931 = pd.to_numeric(
        df["Close0931Pct"],
        errors="coerce",
    )

    target = df[
        (close0931 >= LOWER_LIMIT)
        & (close0931 < UPPER_LIMIT)
    ].copy()

    print("=" * 76)
    print("H1 09:32 PATH ANALYSIS")
    print("=" * 76)
    print(
        f"Target rows : {len(target)}"
    )
    print(
        f"Rule        : "
        f"{LOWER_LIMIT:+.1f}% "
        f"<= Close0931Pct "
        f"< {UPPER_LIMIT:+.1f}%"
    )
    print(
        "Entry       : 09:32 OPEN"
    )

    results = []

    for _, row in target.iterrows():
        code = str(row["Code"])
        date_text = str(
            row["DetectionDate"]
        )

        bars = download_1m(
            code,
            date_text,
        )

        if bars is None:
            print(
                f"NO BARS : "
                f"{date_text} {code}"
            )
            continue

        analyzed = analyze_stock(
            row,
            bars,
        )

        if analyzed is None:
            print(
                f"NO ANALYSIS : "
                f"{date_text} {code}"
            )
            continue

        results.append(analyzed)

    result = pd.DataFrame(results)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print_summary(result)

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()