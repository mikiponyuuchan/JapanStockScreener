from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# H1 MID_CXV
# True Pullback Entry Analysis
#
# 09:30基準価格から一定率下に指値を置いたと仮定し、
# 1分足 Low が指値に到達した最初の時刻で約定判定する。
#
# 約定後：
#   TAKE +10%
#   STOP  -3%
#   どちらにも到達しなければ当日終値で決済
#
# 注意：
# Yahoo Finance の1分足には取得可能期間の制限がある。
# 取得できない過去日は SKIP_DATA として扱う。
# ============================================================


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_delayed_entry_detail.csv"
)

OUTPUT_DETAIL = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_true_pullback_entry_detail.csv"
)

OUTPUT_SUMMARY = (
    BASE_DIR
    / "data"
    / "analysis"
    / "h1_true_pullback_entry_summary.csv"
)


# ------------------------------------------------------------
# 検証条件
# ------------------------------------------------------------

TAKE_PCT = 10.0
STOP_PCT = -3.0

# -0.50% ～ -3.00% を 0.25%刻み
PULLBACK_LEVELS = [
    -0.50,
    -0.75,
    -1.00,
    -1.25,
    -1.50,
    -1.75,
    -2.00,
    -2.25,
    -2.50,
    -2.75,
    -3.00,
]

ENTRY_START = "09:31"
ENTRY_END = "09:35"


# ============================================================
# Utility
# ============================================================

def normalize_code(value):
    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    return code


def get_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col

    return None


def safe_float(value):
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def get_standard_tick_size(price):
    """
    Standard TSE tick size.

    This function currently handles the standard tick table.
    TOPIX100 finer tick sizes are intentionally not applied here.
    """
    price = safe_float(price)

    if np.isnan(price) or price <= 0:
        return np.nan

    if price <= 3000:
        return 1.0
    if price <= 5000:
        return 5.0
    if price <= 30000:
        return 10.0
    if price <= 50000:
        return 50.0
    if price <= 300000:
        return 100.0
    if price <= 500000:
        return 500.0
    if price <= 3000000:
        return 1000.0
    if price <= 5000000:
        return 5000.0
    if price <= 30000000:
        return 10000.0
    if price <= 50000000:
        return 50000.0

    return 100000.0


def floor_to_tick(price):
    """
    Round a BUY limit downward to a valid standard tick.

    Downward rounding keeps the requested pullback at least as deep
    as the theoretical pullback level.
    """
    price = safe_float(price)
    tick = get_standard_tick_size(price)

    if np.isnan(price) or np.isnan(tick):
        return np.nan

    units = np.floor((price + 1e-12) / tick)

    return float(units * tick)


# ============================================================
# Yahoo 1-minute data
# ============================================================

def download_intraday(code, detection_date):
    ticker = f"{code}.T"

    day = pd.Timestamp(detection_date)

    start_date = day.strftime("%Y-%m-%d")
    end_date = (day + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        df = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            interval="1m",
            progress=False,
            auto_adjust=False,
            prepost=False,
            threads=False,
        )
    except Exception as e:
        print(
            f"Yahoo error : {detection_date} "
            f"{code} {type(e).__name__}: {e}"
        )
        return None

    if df is None or df.empty:
        return None

    # MultiIndex対策
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df.columns = df.columns.get_level_values(0)
        except Exception:
            pass

    required = ["Open", "High", "Low", "Close"]

    for col in required:
        if col not in df.columns:
            return None

    df = df.copy()

    # timezoneを日本時間へ
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is not None:
            try:
                df.index = df.index.tz_convert("Asia/Tokyo")
            except Exception:
                pass

    df = df.sort_index()

    return df


# ============================================================
# Entry simulation
# ============================================================

def find_pullback_entry(
    intraday,
    base_price,
    pullback_level,
):
    """
    09:30～09:35の1分足Lowで指値到達を判定。

    指値価格：
        base_price * (1 + pullback_level / 100)

    Low <= 指値価格
    となった最初の1分足で約定とする。

    約定価格は指値価格を使用。
    """

    if intraday is None or intraday.empty:
        return None

    raw_limit_price = (
        base_price
        * (1.0 + pullback_level / 100.0)
    )

    limit_price = floor_to_tick(
        raw_limit_price
    )

    if np.isnan(limit_price):
        return None

    entry_window = intraday.between_time(
        ENTRY_START,
        ENTRY_END,
        inclusive="both",
    )

    if entry_window.empty:
        return None

    for ts, row in entry_window.iterrows():

        low = safe_float(row["Low"])

        if np.isnan(low):
            continue

        if low <= limit_price:

            return {
                "EntryTime": ts,
                "EntryPrice": limit_price,
                "RawLimitPrice": raw_limit_price,
                "TickSize": get_standard_tick_size(
                    raw_limit_price
                ),
                "EntryBarOpen": safe_float(row["Open"]),
                "EntryBarHigh": safe_float(row["High"]),
                "EntryBarLow": low,
                "EntryBarClose": safe_float(row["Close"]),
            }

    return None


# ============================================================
# Exit simulation
# ============================================================

def simulate_exit(
    intraday,
    entry_time,
    entry_price,
):
    """
    約定時刻以降の1分足で
    +10% TAKE / -3% STOP を判定。

    同じ1分足で TAKE と STOP の両方に触れた場合は、
    1分足だけでは順序が不明なので STOP 優先とする。
    """

    take_price = (
        entry_price
        * (1.0 + TAKE_PCT / 100.0)
    )

    stop_price = (
        entry_price
        * (1.0 + STOP_PCT / 100.0)
    )

    after = intraday.loc[intraday.index >= entry_time]

    if after.empty:
        return None

    hit_take_time = None
    hit_stop_time = None

    for ts, row in after.iterrows():

        high = safe_float(row["High"])
        low = safe_float(row["Low"])

        if np.isnan(high) or np.isnan(low):
            continue

        take_hit = high >= take_price
        stop_hit = low <= stop_price

        # 同一1分足で両方到達
        # 順序不明のため保守的にSTOP
        if take_hit and stop_hit:
            return {
                "ExitType": "STOP",
                "ReturnPct": STOP_PCT,
                "ExitTime": ts,
                "TakePrice": take_price,
                "StopPrice": stop_price,
                "HitTakeTime": ts,
                "HitStopTime": ts,
                "SameBarBothHit": True,
            }

        if stop_hit:
            hit_stop_time = ts

            return {
                "ExitType": "STOP",
                "ReturnPct": STOP_PCT,
                "ExitTime": ts,
                "TakePrice": take_price,
                "StopPrice": stop_price,
                "HitTakeTime": hit_take_time,
                "HitStopTime": hit_stop_time,
                "SameBarBothHit": False,
            }

        if take_hit:
            hit_take_time = ts

            return {
                "ExitType": "TAKE",
                "ReturnPct": TAKE_PCT,
                "ExitTime": ts,
                "TakePrice": take_price,
                "StopPrice": stop_price,
                "HitTakeTime": hit_take_time,
                "HitStopTime": hit_stop_time,
                "SameBarBothHit": False,
            }

    # TAKE / STOPなし → 当日最終Close
    last_close = safe_float(after.iloc[-1]["Close"])

    if np.isnan(last_close):
        return None

    return_pct = (
        (last_close / entry_price) - 1.0
    ) * 100.0

    return {
        "ExitType": "CLOSE",
        "ReturnPct": return_pct,
        "ExitTime": after.index[-1],
        "TakePrice": take_price,
        "StopPrice": stop_price,
        "HitTakeTime": hit_take_time,
        "HitStopTime": hit_stop_time,
        "SameBarBothHit": False,
    }


# ============================================================
# Summary
# ============================================================

def create_summary(detail):
    rows = []

    for level in PULLBACK_LEVELS:

        g = detail[
            detail["PullbackLevel"] == level
        ].copy()

        total = len(g)

        executed = g[
            g["Status"] == "EXECUTED"
        ].copy()

        data_missing = int(
            (g["Status"] == "SKIP_DATA").sum()
        )

        no_fill = int(
            (g["Status"] == "NO_FILL").sum()
        )

        n = len(executed)

        take = int(
            (executed["ExitType"] == "TAKE").sum()
        )

        stop = int(
            (executed["ExitType"] == "STOP").sum()
        )

        close = int(
            (executed["ExitType"] == "CLOSE").sum()
        )

        if n > 0:
            mean_return = executed[
                "ReturnPct"
            ].mean()

            median_return = executed[
                "ReturnPct"
            ].median()

            total_return = executed[
                "ReturnPct"
            ].sum()

            positive_pct = (
                (executed["ReturnPct"] > 0).mean()
                * 100.0
            )

            take_pct = take / n * 100.0
            stop_pct = stop / n * 100.0

        else:
            mean_return = np.nan
            median_return = np.nan
            total_return = np.nan
            positive_pct = np.nan
            take_pct = np.nan
            stop_pct = np.nan

        valid_opportunities = (
            total - data_missing
        )

        if valid_opportunities > 0:
            execution_pct = (
                n / valid_opportunities * 100.0
            )
        else:
            execution_pct = np.nan

        rows.append(
            {
                "PullbackLevel": level,
                "TotalTrades": total,
                "DataMissing": data_missing,
                "ValidTrades": valid_opportunities,
                "Executed": n,
                "NoFill": no_fill,
                "ExecutionPct": execution_pct,
                "Take": take,
                "Stop": stop,
                "Close": close,
                "TakePct": take_pct,
                "StopPct": stop_pct,
                "MeanReturnPct": mean_return,
                "MedianReturnPct": median_return,
                "TotalReturnPct": total_return,
                "PositivePct": positive_pct,
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 80)
    print("H1 MID_CXV TRUE PULLBACK ENTRY ANALYSIS")
    print("=" * 80)
    print()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    src = pd.read_csv(
        INPUT_FILE,
        dtype={"Code": str},
    )

    date_col = get_column(
        src,
        ["DetectionDate"],
    )

    code_col = get_column(
        src,
        ["Code"],
    )

    name_col = get_column(
        src,
        ["Name"],
    )

    entry_time_col = get_column(
        src,
        ["EntryTime"],
    )

    entry_price_col = get_column(
        src,
        [
            "DelayedEntryPrice",
            "EntryPriceDelayed",
            "EntryPrice",
        ],
    )

    original_exit_col = get_column(
        src,
        [
            "OriginalExitType",
            "ExitType",
        ],
    )

    original_return_col = get_column(
        src,
        [
            "OriginalReturnPct",
            "ReturnPct",
        ],
    )

    required = {
        "DetectionDate": date_col,
        "Code": code_col,
        "EntryTime": entry_time_col,
        "EntryPrice": entry_price_col,
    }

    missing = [
        key
        for key, value in required.items()
        if value is None
    ]

    if missing:
        print("Available columns:")
        for col in src.columns:
            print(f"  {col}")

        raise KeyError(
            "Missing columns: "
            + ", ".join(missing)
        )

    src[code_col] = (
        src[code_col]
        .map(normalize_code)
    )

    # --------------------------------------------------------
    # 09:30行を基準価格として使用
    # --------------------------------------------------------

    base = src[
        src[entry_time_col].astype(str) == "09:30"
    ].copy()

    base = (
        base
        .sort_values(
            [date_col, code_col]
        )
        .drop_duplicates(
            [date_col, code_col],
            keep="first",
        )
    )

    print(
        f"09:30 base trades : {len(base)}"
    )
    print()

    print(
        "Pullback levels : "
        + ", ".join(
            f"{x:.2f}%"
            for x in PULLBACK_LEVELS
        )
    )

    print()
    print(
        f"Entry window : "
        f"{ENTRY_START} - {ENTRY_END}"
    )

    print()

    results = []

    intraday_cache = {}

    total_trades = len(base)

    for trade_no, (_, row) in enumerate(
        base.iterrows(),
        start=1,
    ):

        detection_date = str(
            row[date_col]
        )[:10]

        code = normalize_code(
            row[code_col]
        )

        if name_col is not None:
            name = str(
                row[name_col]
            )
        else:
            name = ""

        base_price = safe_float(
            row[entry_price_col]
        )

        if np.isnan(base_price):
            continue

        key = (
            detection_date,
            code,
        )

        print(
            f"[{trade_no}/{total_trades}] "
            f"{detection_date} "
            f"{code} "
            f"{name}"
        )

        if key not in intraday_cache:

            intraday_cache[key] = (
                download_intraday(
                    code,
                    detection_date,
                )
            )

        intraday = intraday_cache[key]

        for level in PULLBACK_LEVELS:

            common = {
                "DetectionDate":
                    detection_date,
                "Code":
                    code,
                "Name":
                    name,
                "Price0930":
                    base_price,
                "PullbackLevel":
                    level,
                "LimitPrice":
                    (
                        base_price
                        * (
                            1.0
                            + level / 100.0
                        )
                    ),
            }

            if original_exit_col is not None:
                common[
                    "OriginalExitType"
                ] = row[
                    original_exit_col
                ]

            if original_return_col is not None:
                common[
                    "OriginalReturnPct"
                ] = safe_float(
                    row[
                        original_return_col
                    ]
                )

            # -----------------------------------------------
            # データなし
            # -----------------------------------------------

            if (
                intraday is None
                or intraday.empty
            ):

                results.append(
                    {
                        **common,
                        "Status":
                            "SKIP_DATA",
                        "EntryTime":
                            pd.NaT,
                        "EntryPrice":
                            np.nan,
                        "ActualPullbackPct":
                            np.nan,
                        "ExitType":
                            np.nan,
                        "ReturnPct":
                            np.nan,
                    }
                )

                continue

            # -----------------------------------------------
            # 指値判定
            # -----------------------------------------------

            entry = find_pullback_entry(
                intraday,
                base_price,
                level,
            )

            if entry is None:

                results.append(
                    {
                        **common,
                        "Status":
                            "NO_FILL",
                        "EntryTime":
                            pd.NaT,
                        "EntryPrice":
                            np.nan,
                        "ActualPullbackPct":
                            np.nan,
                        "ExitType":
                            "SKIP",
                        "ReturnPct":
                            np.nan,
                    }
                )

                continue

            entry_price = safe_float(
                entry["EntryPrice"]
            )

            actual_pullback = (
                (
                    entry_price
                    / base_price
                )
                - 1.0
            ) * 100.0

            # -----------------------------------------------
            # Exit判定
            # -----------------------------------------------

            exit_result = simulate_exit(
                intraday,
                entry["EntryTime"],
                entry_price,
            )

            if exit_result is None:

                results.append(
                    {
                        **common,
                        "Status":
                            "SKIP_DATA",
                        "EntryTime":
                            entry["EntryTime"],
                        "EntryPrice":
                            entry_price,
                        "ActualPullbackPct":
                            actual_pullback,
                        "ExitType":
                            np.nan,
                        "ReturnPct":
                            np.nan,
                    }
                )

                continue

            results.append(
                {
                    **common,

                    "Status":
                        "EXECUTED",

                    "EntryTime":
                        entry["EntryTime"],

                    "EntryPrice":
                        entry_price,

                    "ActualPullbackPct":
                        actual_pullback,

                    "EntryBarOpen":
                        entry["EntryBarOpen"],

                    "EntryBarHigh":
                        entry["EntryBarHigh"],

                    "EntryBarLow":
                        entry["EntryBarLow"],

                    "EntryBarClose":
                        entry["EntryBarClose"],

                    "TakePrice":
                        exit_result[
                            "TakePrice"
                        ],

                    "StopPrice":
                        exit_result[
                            "StopPrice"
                        ],

                    "ExitType":
                        exit_result[
                            "ExitType"
                        ],

                    "ReturnPct":
                        exit_result[
                            "ReturnPct"
                        ],

                    "ExitTime":
                        exit_result[
                            "ExitTime"
                        ],

                    "HitTakeTime":
                        exit_result[
                            "HitTakeTime"
                        ],

                    "HitStopTime":
                        exit_result[
                            "HitStopTime"
                        ],

                    "SameBarBothHit":
                        exit_result[
                            "SameBarBothHit"
                        ],
                }
            )

    # ========================================================
    # Result
    # ========================================================

    detail = pd.DataFrame(
        results
    )

    summary = create_summary(
        detail
    )

    OUTPUT_DETAIL.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    detail.to_csv(
        OUTPUT_DETAIL,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 80)
    print("TRUE PULLBACK SUMMARY")
    print("=" * 80)
    print()

    if summary.empty:
        print("No result.")
    else:

        display_cols = [
            "PullbackLevel",
            "TotalTrades",
            "DataMissing",
            "ValidTrades",
            "Executed",
            "NoFill",
            "ExecutionPct",
            "Take",
            "Stop",
            "Close",
            "TakePct",
            "StopPct",
            "MeanReturnPct",
            "MedianReturnPct",
            "TotalReturnPct",
            "PositivePct",
        ]

        print(
            summary[
                display_cols
            ].to_string(
                index=False,
                float_format=lambda x:
                    f"{x:.2f}"
            )
        )

    # ========================================================
    # TAKE取り逃し確認
    # ========================================================

    if (
        original_exit_col is not None
        and not detail.empty
    ):

        print()
        print("=" * 80)
        print("ORIGINAL TAKE -> PULLBACK RESULT")
        print("=" * 80)
        print()

        take_rows = detail[
            detail[
                "OriginalExitType"
            ].astype(str) == "TAKE"
        ].copy()

        if take_rows.empty:
            print("None")
        else:

            cols = [
                "DetectionDate",
                "Code",
                "Name",
                "PullbackLevel",
                "Status",
                "EntryTime",
                "EntryPrice",
                "ExitType",
                "ReturnPct",
            ]

            existing = [
                c
                for c in cols
                if c in take_rows.columns
            ]

            print(
                take_rows[
                    existing
                ].to_string(
                    index=False
                )
            )

    # ========================================================
    # STOP改善確認
    # ========================================================

    if (
        original_exit_col is not None
        and not detail.empty
    ):

        print()
        print("=" * 80)
        print("ORIGINAL STOP -> PULLBACK RESULT")
        print("=" * 80)
        print()

        stop_rows = detail[
            detail[
                "OriginalExitType"
            ].astype(str) == "STOP"
        ].copy()

        if stop_rows.empty:
            print("None")
        else:

            cols = [
                "DetectionDate",
                "Code",
                "Name",
                "PullbackLevel",
                "Status",
                "EntryTime",
                "EntryPrice",
                "ExitType",
                "ReturnPct",
            ]

            existing = [
                c
                for c in cols
                if c in stop_rows.columns
            ]

            print(
                stop_rows[
                    existing
                ].to_string(
                    index=False
                )
            )

    print()
    print(
        f"Detail saved  : "
        f"{OUTPUT_DETAIL.relative_to(BASE_DIR)}"
    )

    print(
        f"Summary saved : "
        f"{OUTPUT_SUMMARY.relative_to(BASE_DIR)}"
    )


if __name__ == "__main__":
    main()