from pathlib import Path

import pandas as pd
import yfinance as yf


TARGET_DATE = pd.Timestamp("2026-08-28").date()

TOP20_FILE = Path("results/2026-08-28_top20.csv")
OUTPUT_FILE = Path("data/analysis/930_breakout_2026-08-28.csv")


def flatten_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def find_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def analyze_code(code, name=""):

    ticker = f"{code}.T"

    # ==========================
    # 日足
    # ==========================
    daily = yf.download(
        ticker,
        period="3mo",
        interval="1d",
        auto_adjust=False,
        progress=False,
    )

    if daily.empty:
        return None

    daily = flatten_columns(daily)
    daily.index = pd.to_datetime(daily.index)

    past = daily[daily.index.date < TARGET_DATE].copy()

    if len(past) < 30:
        return None

    today_daily = daily[daily.index.date == TARGET_DATE]

    if today_daily.empty:
        return None

    purple20 = float(past["High"].tail(20).max())
    green30 = float(past["High"].tail(30).max())
    day_close = float(today_daily.iloc[-1]["Close"])

    # ==========================
    # 1分足
    # ==========================
    minute = yf.download(
        ticker,
        period="7d",
        interval="1m",
        auto_adjust=False,
        progress=False,
    )

    if minute.empty:
        return None

    minute = flatten_columns(minute)

    idx = pd.to_datetime(minute.index)

    if idx.tz is None:
        idx = idx.tz_localize("UTC").tz_convert("Asia/Tokyo")
    else:
        idx = idx.tz_convert("Asia/Tokyo")

    minute.index = idx

    today = minute[minute.index.date == TARGET_DATE].copy()

    if today.empty:
        return None

    # ==========================
    # 9:00～9:29
    # ==========================
    t0900 = pd.Timestamp("09:00").time()
    t0930 = pd.Timestamp("09:30").time()

    morning = today[
        (today.index.time >= t0900)
        & (today.index.time < t0930)
    ]

    if morning.empty:
        return None

    after930 = today[today.index.time >= t0930]

    if after930.empty:
        return None

    open900 = float(morning.iloc[0]["Open"])
    high930 = float(morning["High"].max())
    low930 = float(morning["Low"].min())
    close929 = float(morning.iloc[-1]["Close"])
    volume930 = int(morning["Volume"].sum())

    # 9:30足のOpenを仮想買値
    entry930 = float(after930.iloc[0]["Open"])

    after_high = float(after930["High"].max())
    after_low = float(after930["Low"].min())

    # ==========================
    # 数値指標
    # ==========================
    line_gap_pct = (
        green30 / purple20 - 1
    ) * 100

    candle_pct = (
        close929 / open900 - 1
    ) * 100

    entry_vs_20 = (
        entry930 / purple20 - 1
    ) * 100

    entry_vs_30 = (
        entry930 / green30 - 1
    ) * 100

    close_return = (
        day_close / entry930 - 1
    ) * 100

    max_return = (
        after_high / entry930 - 1
    ) * 100

    min_return = (
        after_low / entry930 - 1
    ) * 100

    # ==========================
    # 仮説分類
    # ==========================

    separated = green30 > purple20

    negative_candle = close929 < open900

    both_cross = (
        separated
        and open900 < purple20
        and high930 >= green30
    )

    below_purple = entry930 < purple20

    main_shape = (
        separated
        and close929 > open900
        and entry930 >= purple20
        and high930 < green30
    )

    if negative_candle:
        group = "①陰線"
    elif both_cross:
        group = "②紫→緑一気またぎ"
    elif below_purple:
        group = "③紫未突破"
    elif main_shape:
        group = "④本命形"
    else:
        group = "⑤その他"

    return {
        "Date": str(TARGET_DATE),
        "Code": code,
        "Name": name,

        "Purple20": purple20,
        "Green30": green30,
        "LineGapPct": line_gap_pct,

        "Open900": open900,
        "High930": high930,
        "Low930": low930,
        "Close929": close929,
        "Volume930": volume930,
        "CandlePct930": candle_pct,

        "Entry930": entry930,
        "EntryVs20Pct": entry_vs_20,
        "EntryVs30Pct": entry_vs_30,

        "Separated": separated,
        "NegativeCandle": negative_candle,
        "BothCross": both_cross,
        "BelowPurple": below_purple,
        "MainShape": main_shape,
        "Group": group,

        "DayClose": day_close,
        "ReturnToClose": close_return,
        "MaxReturnAfter930": max_return,
        "MinReturnAfter930": min_return,
    }


def main():

    if not TOP20_FILE.exists():
        raise FileNotFoundError(TOP20_FILE)

    top20 = pd.read_csv(
        TOP20_FILE,
        encoding="utf-8-sig",
        dtype=str,
    )

    code_col = find_column(
        top20,
        ["コード", "Code", "code"],
    )

    name_col = find_column(
        top20,
        ["銘柄名", "Name", "name"],
    )

    if code_col is None:
        raise RuntimeError(
            f"コード列が見つかりません: {list(top20.columns)}"
        )

    results = []

    print("==============================")
    print(" 9:30 びよーん仮説テスト")
    print("==============================")
    print(f"対象日 : {TARGET_DATE}")
    print(f"対象数 : {len(top20)}")
    print()

    for i, row in top20.iterrows():

        code = str(row[code_col]).strip()

        # CSVによって 7203.0 になる場合への対策
        if code.endswith(".0"):
            code = code[:-2]

        name = ""
        if name_col is not None:
            name = str(row[name_col]).strip()

        try:
            result = analyze_code(code, name)

            if result is None:
                print(
                    f"[{i + 1}/{len(top20)}] "
                    f"{code} SKIP"
                )
                continue

            results.append(result)

            print(
                f"[{i + 1}/{len(top20)}] "
                f"{code} "
                f"{result['Group']} "
                f"引け={result['ReturnToClose']:+.2f}%"
            )

        except Exception as e:
            print(
                f"[{i + 1}/{len(top20)}] "
                f"{code} ERROR : {e}"
            )

    if not results:
        print("有効データなし")
        return

    df = pd.DataFrame(results)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("==============================")
    print(" グループ別結果")
    print("==============================")

    summary = (
        df.groupby("Group")["ReturnToClose"]
        .agg(["count", "mean", "median"])
        .round(2)
    )

    print(summary.to_string())

    print()
    print("=== 引け勝率 ===")

    win_rate = (
        df.groupby("Group")["ReturnToClose"]
        .apply(
            lambda s: round(
                (s > 0).mean() * 100,
                1,
            )
        )
    )

    print(win_rate.to_string())

    print()
    print("=== 9:30以降 最大上昇率 ===")

    max_summary = (
        df.groupby("Group")["MaxReturnAfter930"]
        .agg(["count", "mean", "median"])
        .round(2)
    )

    print(max_summary.to_string())

    print()
    print(f"保存 : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
