from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


INPUT_PATH = Path(
    "data/analysis/intraday_strategy_h1_0931_candle.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/intraday_strategy_h1_breakeven.csv"
)

LOWER_LIMIT = -3.0
UPPER_LIMIT = 1.0

TAKE_PCT = 10.0
STOP_PCT = -3.0

METHODS = {
    "CURRENT": None,
    "BE+1.0": 1.0,
    "BE+1.5": 1.5,
    "BE+2.0": 2.0,
    "BE+2.5": 2.5,
    "BE+3.0": 3.0,
}


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

    for col in needed:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=needed
    )

    return df


def time_text(ts):
    if ts is None:
        return ""

    return pd.Timestamp(ts).strftime(
        "%H:%M"
    )


def prepare_work(bars, date_text):
    start = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    ).replace(
        hour=9,
        minute=32,
        second=0,
    )

    end = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    ).replace(
        hour=15,
        minute=30,
        second=0,
    )

    work = bars[
        (bars.index >= start)
        & (bars.index <= end)
    ].copy()

    if work.empty:
        return None

    return work


def simulate_current(work):
    entry_price = float(
        work.iloc[0]["Open"]
    )

    take_price = (
        entry_price
        * (1.0 + TAKE_PCT / 100.0)
    )

    stop_price = (
        entry_price
        * (1.0 + STOP_PCT / 100.0)
    )

    for ts, bar in work.iterrows():
        high = float(bar["High"])
        low = float(bar["Low"])

        take_hit = high >= take_price
        stop_hit = low <= stop_price

        if take_hit and stop_hit:
            return {
                "ExitType": "SAME_BAR",
                "ReturnPct": pd.NA,
                "ExitTime": time_text(ts),
                "BETriggerTime": "",
            }

        if take_hit:
            return {
                "ExitType": "TAKE",
                "ReturnPct": TAKE_PCT,
                "ExitTime": time_text(ts),
                "BETriggerTime": "",
            }

        if stop_hit:
            return {
                "ExitType": "STOP",
                "ReturnPct": STOP_PCT,
                "ExitTime": time_text(ts),
                "BETriggerTime": "",
            }

    last_close = float(
        work.iloc[-1]["Close"]
    )

    return_pct = (
        last_close / entry_price - 1.0
    ) * 100.0

    return {
        "ExitType": "CLOSE",
        "ReturnPct": return_pct,
        "ExitTime": time_text(
            work.index[-1]
        ),
        "BETriggerTime": "",
    }


def simulate_breakeven(
    work,
    trigger_pct,
):
    entry_price = float(
        work.iloc[0]["Open"]
    )

    take_price = (
        entry_price
        * (1.0 + TAKE_PCT / 100.0)
    )

    stop_price = (
        entry_price
        * (1.0 + STOP_PCT / 100.0)
    )

    trigger_price = (
        entry_price
        * (1.0 + trigger_pct / 100.0)
    )

    be_active = False
    trigger_time = None

    for ts, bar in work.iterrows():
        high = float(bar["High"])
        low = float(bar["Low"])

        # --------------------------------
        # 建値STOPがすでに有効な場合
        # --------------------------------
        if be_active:
            take_hit = high >= take_price
            be_hit = low <= entry_price

            if take_hit and be_hit:
                return {
                    "ExitType": "SAME_BAR",
                    "ReturnPct": pd.NA,
                    "ExitTime": time_text(ts),
                    "BETriggerTime":
                        time_text(trigger_time),
                }

            if take_hit:
                return {
                    "ExitType": "TAKE",
                    "ReturnPct": TAKE_PCT,
                    "ExitTime": time_text(ts),
                    "BETriggerTime":
                        time_text(trigger_time),
                }

            if be_hit:
                return {
                    "ExitType": "BREAKEVEN",
                    "ReturnPct": 0.0,
                    "ExitTime": time_text(ts),
                    "BETriggerTime":
                        time_text(trigger_time),
                }

            continue

        # --------------------------------
        # 建値STOP発動前
        # --------------------------------
        take_hit = high >= take_price
        stop_hit = low <= stop_price
        trigger_hit = high >= trigger_price

        # +10%と-3%が同一足
        if take_hit and stop_hit:
            return {
                "ExitType": "SAME_BAR",
                "ReturnPct": pd.NA,
                "ExitTime": time_text(ts),
                "BETriggerTime": "",
            }

        # +10%に先に到達
        if take_hit:
            return {
                "ExitType": "TAKE",
                "ReturnPct": TAKE_PCT,
                "ExitTime": time_text(ts),
                "BETriggerTime": "",
            }

        # -3%に先に到達
        if stop_hit:
            return {
                "ExitType": "STOP",
                "ReturnPct": STOP_PCT,
                "ExitTime": time_text(ts),
                "BETriggerTime": "",
            }

        if trigger_hit:
            # 同じ1分足の中で、
            # trigger到達と建値割れの両方が存在。
            #
            # OHLCだけでは
            # 「上昇してtrigger → 下落して建値」
            # なのか
            # 「先に建値割れ → 後からtrigger」
            # なのか判定できない。
            if low <= entry_price:
                return {
                    "ExitType":
                        "BE_TRIGGER_SAME_BAR",
                    "ReturnPct": pd.NA,
                    "ExitTime": time_text(ts),
                    "BETriggerTime":
                        time_text(ts),
                }

            be_active = True
            trigger_time = ts

    last_close = float(
        work.iloc[-1]["Close"]
    )

    return_pct = (
        last_close / entry_price - 1.0
    ) * 100.0

    return {
        "ExitType": "CLOSE",
        "ReturnPct": return_pct,
        "ExitTime": time_text(
            work.index[-1]
        ),
        "BETriggerTime":
            time_text(trigger_time),
    }


def summarize(result):
    print()
    print("=" * 78)
    print("H1 BREAKEVEN STOP COMPARISON")
    print("=" * 78)

    rows = []

    for method in METHODS:
        x = result[
            result["Method"] == method
        ].copy()

        returns = pd.to_numeric(
            x["ReturnPct"],
            errors="coerce",
        )

        valid = returns.dropna()

        exit_counts = (
            x["ExitType"]
            .value_counts()
            .to_dict()
        )

        rows.append({
            "Method": method,
            "Trades": len(x),
            "Valid": len(valid),
            "MeanReturn":
                valid.mean(),
            "Median":
                valid.median(),
            "WinRate":
                (
                    (valid > 0).mean() * 100
                    if len(valid)
                    else pd.NA
                ),
            "TotalReturn":
                valid.sum(),
            "TAKE":
                exit_counts.get(
                    "TAKE",
                    0,
                ),
            "STOP":
                exit_counts.get(
                    "STOP",
                    0,
                ),
            "BE":
                exit_counts.get(
                    "BREAKEVEN",
                    0,
                ),
            "CLOSE":
                exit_counts.get(
                    "CLOSE",
                    0,
                ),
            "AMBIG":
                (
                    exit_counts.get(
                        "SAME_BAR",
                        0,
                    )
                    + exit_counts.get(
                        "BE_TRIGGER_SAME_BAR",
                        0,
                    )
                ),
        })

    summary = pd.DataFrame(rows)

    display = summary.copy()

    for col in [
        "MeanReturn",
        "Median",
        "WinRate",
        "TotalReturn",
    ]:
        display[col] = display[col].map(
            lambda x:
                ""
                if pd.isna(x)
                else f"{x:.2f}%"
        )

    print(
        display.to_string(
            index=False
        )
    )

    print()
    print("=" * 78)
    print("STOCK DETAIL")
    print("=" * 78)

    pivot = result.pivot_table(
        index=[
            "DetectionDate",
            "Code",
            "Name",
            "Rank",
            "Close0931Pct",
            "CxV",
        ],
        columns="Method",
        values="ReturnPct",
        aggfunc="first",
    ).reset_index()

    print(
        pivot.to_string(
            index=False
        )
    )

    print()
    print("=" * 78)
    print("AMBIGUOUS 1-MINUTE BARS")
    print("=" * 78)

    ambiguous = result[
        result["ExitType"].isin([
            "SAME_BAR",
            "BE_TRIGGER_SAME_BAR",
        ])
    ].copy()

    if ambiguous.empty:
        print("None")
    else:
        cols = [
            "DetectionDate",
            "Code",
            "Name",
            "Method",
            "EntryPrice",
            "ExitType",
            "ExitTime",
            "BETriggerTime",
        ]

        print(
            ambiguous[cols]
            .to_string(index=False)
        )

    return summary


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

    print("=" * 78)
    print("H1 BREAKEVEN STOP ANALYSIS")
    print("=" * 78)
    print(
        f"Target rows : {len(target)}"
    )
    print(
        f"Entry       : 09:32 OPEN"
    )
    print(
        f"Band        : "
        f"{LOWER_LIMIT:+.1f}% "
        f"<= Close0931Pct "
        f"< {UPPER_LIMIT:+.1f}%"
    )
    print(
        f"Take profit : +{TAKE_PCT:.1f}%"
    )
    print(
        f"Initial stop: {STOP_PCT:.1f}%"
    )

    results = []

    for _, row in target.iterrows():
        date_text = str(
            row["DetectionDate"]
        )
        code = str(row["Code"])

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

        work = prepare_work(
            bars,
            date_text,
        )

        if work is None:
            print(
                f"NO WORK : "
                f"{date_text} {code}"
            )
            continue

        entry_price = float(
            work.iloc[0]["Open"]
        )

        for method, trigger in METHODS.items():
            if trigger is None:
                sim = simulate_current(
                    work
                )
            else:
                sim = simulate_breakeven(
                    work,
                    trigger,
                )

            results.append({
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
                "EntryPrice":
                    entry_price,
                "Method":
                    method,
                "TriggerPct":
                    (
                        trigger
                        if trigger is not None
                        else pd.NA
                    ),
                **sim,
            })

    result = pd.DataFrame(
        results
    )

    if result.empty:
        print("No results.")
        return

    summary = summarize(
        result
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    summary_path = OUTPUT_PATH.with_name(
        "intraday_strategy_h1_breakeven_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"Saved : {OUTPUT_PATH}"
    )
    print(
        f"Saved : {summary_path}"
    )


if __name__ == "__main__":
    main()