from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


TRACKING_PATH = Path(
    "data/tracking/intraday_strategy_h1.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/h1_stop_strategy_comparison.csv"
)

TAKE_PCT = 10.0

STOP_LEVELS = {
    "STOP3": -3.0,
    "STOP4": -4.0,
    "STOP5": -5.0,
    "STOP6": -6.0,
}


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def parse_snapshot_time(value):
    text = str(value).strip()

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(
                text,
                fmt,
            )
        except ValueError:
            pass

    return None


def evaluation_start(date_text, time_text):
    t = parse_snapshot_time(time_text)

    if t is None:
        return None

    base = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    current = base.replace(
        hour=t.hour,
        minute=t.minute,
        second=t.second,
    )

    bar = current.replace(
        second=0,
        microsecond=0,
    )

    # Snapshotを含む1分足は使用しない。
    # 次の1分足から売却判定を開始する。
    return bar + timedelta(minutes=1)


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


def pct(price, entry):
    return (
        float(price) / float(entry) - 1
    ) * 100


def prepare_bars(
    bars,
    date_text,
    snapshot_time,
):
    start = evaluation_start(
        date_text,
        snapshot_time,
    )

    if start is None:
        return None

    work = bars[
        bars.index >= start
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
            "High",
            "Low",
            "Close",
        ]
    )

    if work.empty:
        return None

    return work


def analyze_stop_strategy(
    bars,
    entry,
    stop_pct,
):
    max_high_pct = None
    min_low_pct = None

    for ts, bar in bars.iterrows():

        high_pct = pct(
            bar["High"],
            entry,
        )

        low_pct = pct(
            bar["Low"],
            entry,
        )

        max_high_pct = (
            high_pct
            if max_high_pct is None
            else max(
                max_high_pct,
                high_pct,
            )
        )

        min_low_pct = (
            low_pct
            if min_low_pct is None
            else min(
                min_low_pct,
                low_pct,
            )
        )

        hit_take = (
            high_pct >= TAKE_PCT
        )

        hit_stop = (
            low_pct <= stop_pct
        )

        # 同じ1分足でTAKE/STOP両方へ到達した場合、
        # 1分足だけでは先後関係を確定できない。
        if hit_take and hit_stop:
            return {
                "ExitType": "SAME_BAR",
                "ReturnPct": pd.NA,
                "ExitTime":
                    ts.strftime("%H:%M"),
                "MaxHighPct":
                    max_high_pct,
                "MinLowPct":
                    min_low_pct,
            }

        if hit_stop:
            return {
                "ExitType": "STOP",
                "ReturnPct": stop_pct,
                "ExitTime":
                    ts.strftime("%H:%M"),
                "MaxHighPct":
                    max_high_pct,
                "MinLowPct":
                    min_low_pct,
            }

        if hit_take:
            return {
                "ExitType": "TAKE",
                "ReturnPct": TAKE_PCT,
                "ExitTime":
                    ts.strftime("%H:%M"),
                "MaxHighPct":
                    max_high_pct,
                "MinLowPct":
                    min_low_pct,
            }

    last_close = float(
        bars["Close"].iloc[-1]
    )

    return {
        "ExitType": "CLOSE",
        "ReturnPct":
            pct(last_close, entry),
        "ExitTime":
            bars.index[-1].strftime(
                "%H:%M"
            ),
        "MaxHighPct":
            max_high_pct,
        "MinLowPct":
            min_low_pct,
    }


def print_summary(
    name,
    frame,
):
    ret = pd.to_numeric(
        frame["ReturnPct"],
        errors="coerce",
    ).dropna()

    if ret.empty:
        print(
            f"{name:<8} N=0"
        )
        return

    plus = (
        ret.gt(0).mean() * 100
    )

    take_count = (
        frame["ExitType"]
        .eq("TAKE")
        .sum()
    )

    stop_count = (
        frame["ExitType"]
        .eq("STOP")
        .sum()
    )

    same_bar_count = (
        frame["ExitType"]
        .eq("SAME_BAR")
        .sum()
    )

    print(
        f"{name:<8} "
        f"N={len(ret):2d} "
        f"Mean={ret.mean():7.2f}% "
        f"Median={ret.median():7.2f}% "
        f"Plus={plus:6.1f}% "
        f"Total={ret.sum():8.2f}% "
        f"TAKE={take_count:2d} "
        f"STOP={stop_count:2d} "
        f"SAME={same_bar_count:2d} "
        f"Worst={ret.min():7.2f}%"
    )

    print(
        frame["ExitType"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )


def main():

    if not TRACKING_PATH.exists():
        print(
            f"Not found : {TRACKING_PATH}"
        )
        return

    source = pd.read_csv(
        TRACKING_PATH,
        dtype={"Code": str},
        low_memory=False,
    )

    forward = source[
        (
            source["DataType"]
            == "FORWARD"
        )
        & (
            source["ExitType"]
            .notna()
        )
        & (
            source["ExitType"]
            .astype(str)
            .str.strip()
            .ne("")
        )
    ].copy()

    forward["Code"] = (
        forward["Code"]
        .map(normalize_code)
    )

    print(
        f"H1 Forward rows : "
        f"{len(forward)}"
    )

    all_results = []
    cache = {}

    for _, row in forward.iterrows():

        date_text = str(
            row["DetectionDate"]
        ).strip()

        time_text = str(
            row["SnapshotTime"]
        ).strip()

        code = normalize_code(
            row["Code"]
        )

        entry = pd.to_numeric(
            row["SnapshotPrice"],
            errors="coerce",
        )

        if pd.isna(entry) or entry <= 0:
            print(
                f"{date_text} {code} "
                f"BAD ENTRY"
            )
            continue

        key = (
            code,
            date_text,
        )

        if key not in cache:
            cache[key] = download_1m(
                code,
                date_text,
            )

        bars = cache[key]

        if bars is None:
            print(
                f"{date_text} {code} "
                f"NO DATA"
            )
            continue

        work = prepare_bars(
            bars,
            date_text,
            time_text,
        )

        if work is None:
            print(
                f"{date_text} {code} "
                f"NO BARS"
            )
            continue

        strategies = {}

        for (
            name,
            stop_pct,
        ) in STOP_LEVELS.items():

            strategies[name] = (
                analyze_stop_strategy(
                    work,
                    float(entry),
                    stop_pct,
                )
            )

        base_return = pd.to_numeric(
            strategies["STOP3"][
                "ReturnPct"
            ],
            errors="coerce",
        )

        for name, result in (
            strategies.items()
        ):

            ret = pd.to_numeric(
                result["ReturnPct"],
                errors="coerce",
            )

            diff = (
                ret - base_return
                if (
                    pd.notna(ret)
                    and pd.notna(
                        base_return
                    )
                )
                else pd.NA
            )

            all_results.append(
                {
                    "DetectionDate":
                        date_text,
                    "SnapshotTime":
                        time_text,
                    "Code":
                        code,
                    "Name":
                        row.get(
                            "Name",
                            "",
                        ),
                    "Rank":
                        row.get(
                            "Rank",
                            pd.NA,
                        ),
                    "SnapshotPrice":
                        entry,
                    "Change":
                        row.get(
                            "Change",
                            pd.NA,
                        ),
                    "CxV":
                        row.get(
                            "CxV",
                            pd.NA,
                        ),
                    "Strategy":
                        name,
                    "StopPct":
                        STOP_LEVELS[name],
                    "TakePct":
                        TAKE_PCT,
                    "ExitType":
                        result[
                            "ExitType"
                        ],
                    "ReturnPct":
                        result[
                            "ReturnPct"
                        ],
                    "DiffVsSTOP3":
                        diff,
                    "ExitTime":
                        result[
                            "ExitTime"
                        ],
                    "MaxHighPct":
                        result[
                            "MaxHighPct"
                        ],
                    "MinLowPct":
                        result[
                            "MinLowPct"
                        ],
                }
            )

        print(
            f"{date_text} "
            f"{code} OK"
        )

    result_df = pd.DataFrame(
        all_results
    )

    if result_df.empty:
        print("No results.")
        return

    print()
    print("=" * 76)
    print(
        "H1 STOP STRATEGY COMPARISON"
    )
    print("=" * 76)
    print(
        "TAKE fixed at +10%"
    )

    order = [
        "STOP3",
        "STOP4",
        "STOP5",
        "STOP6",
    ]

    for name in order:
        part = result_df[
            result_df["Strategy"]
            == name
        ]

        print()
        print_summary(
            name,
            part,
        )

    print()
    print("=" * 76)
    print("DIFFERENCE VS STOP3")
    print("=" * 76)

    for name in order[1:]:

        part = result_df[
            result_df["Strategy"]
            == name
        ].copy()

        diff = pd.to_numeric(
            part["DiffVsSTOP3"],
            errors="coerce",
        ).dropna()

        if diff.empty:
            continue

        print(
            f"{name:<8} "
            f"MeanDiff={diff.mean():7.2f}% "
            f"Improved={(diff > 0).sum():2d} "
            f"Same={(diff == 0).sum():2d} "
            f"Worse={(diff < 0).sum():2d}"
        )

    print()
    print("=" * 76)
    print("CHANGED RESULTS VS STOP3")
    print("=" * 76)

    base = result_df[
        result_df["Strategy"]
        == "STOP3"
    ][
        [
            "DetectionDate",
            "Code",
            "ReturnPct",
            "ExitType",
        ]
    ].rename(
        columns={
            "ReturnPct":
                "ReturnPct_STOP3",
            "ExitType":
                "ExitType_STOP3",
        }
    )

    changed_rows = []

    for name in order[1:]:

        part = result_df[
            result_df["Strategy"]
            == name
        ].copy()

        merged = part.merge(
            base,
            on=[
                "DetectionDate",
                "Code",
            ],
            how="left",
        )

        current_ret = pd.to_numeric(
            merged["ReturnPct"],
            errors="coerce",
        )

        base_ret = pd.to_numeric(
            merged["ReturnPct_STOP3"],
            errors="coerce",
        )

        mask = (
            (
                current_ret.notna()
                & base_ret.notna()
                & (
                    (current_ret - base_ret)
                    .abs()
                    > 1e-9
                )
            )
            |
            (
                merged["ExitType"]
                != merged[
                    "ExitType_STOP3"
                ]
            )
        )

        changed = merged[
            mask
        ].copy()

        for _, row in changed.iterrows():
            changed_rows.append(
                {
                    "Strategy":
                        name,
                    "DetectionDate":
                        row[
                            "DetectionDate"
                        ],
                    "Code":
                        row["Code"],
                    "Name":
                        row["Name"],
                    "STOP3":
                        row[
                            "ReturnPct_STOP3"
                        ],
                    "NewReturn":
                        row[
                            "ReturnPct"
                        ],
                    "NewExit":
                        row[
                            "ExitType"
                        ],
                    "ExitTime":
                        row[
                            "ExitTime"
                        ],
                    "Diff":
                        (
                            pd.to_numeric(
                                row[
                                    "ReturnPct"
                                ],
                                errors="coerce",
                            )
                            -
                            pd.to_numeric(
                                row[
                                    "ReturnPct_STOP3"
                                ],
                                errors="coerce",
                            )
                        ),
                }
            )

    changed_df = pd.DataFrame(
        changed_rows
    )

    if changed_df.empty:
        print("No changed results.")
    else:
        changed_df["Diff"] = (
            pd.to_numeric(
                changed_df["Diff"],
                errors="coerce",
            )
        )

        changed_df = (
            changed_df
            .sort_values(
                [
                    "Strategy",
                    "Diff",
                ],
                ascending=[
                    True,
                    False,
                ],
            )
        )

        print(
            changed_df.to_string(
                index=False
            )
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
