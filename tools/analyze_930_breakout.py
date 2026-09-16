from pathlib import Path

import pandas as pd
import yfinance as yf


TARGET_DATE = pd.Timestamp("2026-08-28").date()

# 8/28 Excelに記録されていた実際のスクリーナー実行時刻
SIGNAL_TIME = "09:33"

# 候補判明後、次の1分足Openで買えるものとして評価
ENTRY_TIME = "09:34"

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
    # 紫・緑は対象日の前日まで
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

    today = minute[
        minute.index.date == TARGET_DATE
    ].copy()

    if today.empty:
        return None

    # ==========================
    # シグナル確定時点まで
    #
    # 8/28は9:33実行。
    # 9:33足の中身は使わず、
    # 9:32までの確定1分足だけを見る。
    # ==========================
    t0900 = pd.Timestamp("09:00").time()
    signal_time = pd.Timestamp(SIGNAL_TIME).time()
    entry_time = pd.Timestamp(ENTRY_TIME).time()

    snapshot = today[
        (today.index.time >= t0900)
        & (today.index.time < signal_time)
    ]

    if snapshot.empty:
        return None

    entry_rows = today[
        today.index.time >= entry_time
    ]

    if entry_rows.empty:
        return None

    open900 = float(snapshot.iloc[0]["Open"])
    snapshot_high = float(snapshot["High"].max())
    snapshot_low = float(snapshot["Low"].min())
    snapshot_close = float(snapshot.iloc[-1]["Close"])
    snapshot_volume = int(snapshot["Volume"].sum())

    # ==========================
    # 仮想エントリー
    # ==========================
    entry_bar = entry_rows.iloc[0]

    entry_actual_time = entry_bar.name
    entry_price = float(entry_bar["Open"])

    after_entry = today[
        today.index >= entry_actual_time
    ]

    after_high = float(after_entry["High"].max())
    after_low = float(after_entry["Low"].min())

    # ==========================
    # 生の特徴量
    # ==========================
    line_gap_pct = (
        green30 / purple20 - 1
    ) * 100

    morning_move_pct = (
        snapshot_close / open900 - 1
    ) * 100

    purple_distance_pct = (
        entry_price / purple20 - 1
    ) * 100

    green_distance_pct = (
        entry_price / green30 - 1
    ) * 100

    entry_to_close_pct = (
        day_close / entry_price - 1
    ) * 100

    entry_to_high_pct = (
        after_high / entry_price - 1
    ) * 100

    entry_to_low_pct = (
        after_low / entry_price - 1
    ) * 100

    # ==========================
    # 観測フラグ
    #
    # ここでは良し悪しを決めない。
    # 後から成績と比較するための材料。
    # ==========================
    separated = green30 > purple20

    morning_bullish = snapshot_close > open900
    morning_bearish = snapshot_close < open900

    cross_purple = snapshot_high >= purple20
    cross_green = snapshot_high >= green30

    close_above_purple = snapshot_close >= purple20
    close_above_green = snapshot_close >= green30

    entry_above_purple = entry_price >= purple20
    entry_above_green = entry_price >= green30

    below_purple = entry_price < purple20

    # 朝の値幅が紫から緑まで一気にまたいだか
    span_both_lines = (
        separated
        and open900 < purple20
        and snapshot_high >= green30
    )

    # 当初の「本命形」も観測フラグとして残す
    original_main_shape = (
        separated
        and morning_bullish
        and entry_above_purple
        and snapshot_high < green30
    )

    # ==========================
    # 参考分類
    #
    # 分離していない銘柄を①③へ
    # 混ぜないように修正。
    # ==========================
    if not separated:
        group = "対象外_ライン重複"

    elif morning_bearish:
        group = "①陰線"

    elif span_both_lines:
        group = "②紫→緑一気またぎ"

    elif below_purple:
        group = "③紫未突破"

    elif original_main_shape:
        group = "④本命形"

    else:
        group = "⑤その他"

    return {
        "Date": str(TARGET_DATE),
        "Code": code,
        "Name": name,

        "SignalTime": SIGNAL_TIME,
        "EntryTime": str(entry_actual_time),

        "Purple20": purple20,
        "Green30": green30,
        "LineGapPct": line_gap_pct,

        "Open900": open900,
        "SnapshotHigh": snapshot_high,
        "SnapshotLow": snapshot_low,
        "SnapshotClose": snapshot_close,
        "SnapshotVolume": snapshot_volume,
        "MorningMovePct": morning_move_pct,

        "EntryPrice": entry_price,
        "PurpleDistancePct": purple_distance_pct,
        "GreenDistancePct": green_distance_pct,

        "Separated": separated,
        "MorningBullish": morning_bullish,
        "MorningBearish": morning_bearish,

        "CrossPurple": cross_purple,
        "CrossGreen": cross_green,

        "CloseAbovePurple": close_above_purple,
        "CloseAboveGreen": close_above_green,

        "EntryAbovePurple": entry_above_purple,
        "EntryAboveGreen": entry_above_green,

        "BelowPurple": below_purple,
        "SpanBothLines": span_both_lines,
        "OriginalMainShape": original_main_shape,

        "Group": group,

        "DayClose": day_close,
        "EntryToClosePct": entry_to_close_pct,
        "EntryToHighPct": entry_to_high_pct,
        "EntryToLowPct": entry_to_low_pct,
    }


def print_summary(df):

    print()
    print("==============================")
    print(" 全銘柄 グループ別")
    print("==============================")

    summary = (
        df.groupby("Group")["EntryToClosePct"]
        .agg(["count", "mean", "median"])
        .round(2)
    )

    print(summary.to_string())

    print()
    print("=== 引け勝率 ===")

    win_rate = (
        df.groupby("Group")["EntryToClosePct"]
        .apply(
            lambda s: round(
                (s > 0).mean() * 100,
                1,
            )
        )
    )

    print(win_rate.to_string())

    # ==========================
    # 本来の観察対象
    # 緑 > 紫 の銘柄だけ
    # ==========================
    separated_df = df[
        df["Separated"] == True
    ].copy()

    print()
    print("==============================")
    print(" 緑 > 紫 の分離銘柄だけ")
    print("==============================")
    print(
        f"分離銘柄数 : "
        f"{len(separated_df)} / {len(df)}"
    )

    if separated_df.empty:
        print("分離銘柄なし")
        return

    sep_summary = (
        separated_df
        .groupby("Group")["EntryToClosePct"]
        .agg(["count", "mean", "median"])
        .round(2)
    )

    print()
    print(sep_summary.to_string())

    print()
    print("=== 分離銘柄 引け勝率 ===")

    sep_win = (
        separated_df
        .groupby("Group")["EntryToClosePct"]
        .apply(
            lambda s: round(
                (s > 0).mean() * 100,
                1,
            )
        )
    )

    print(sep_win.to_string())

    print()
    print("=== 分離銘柄 エントリー後最大上昇 ===")

    sep_high = (
        separated_df
        .groupby("Group")["EntryToHighPct"]
        .agg(["count", "mean", "median"])
        .round(2)
    )

    print(sep_high.to_string())

    print()
    print("=== 分離銘柄 エントリー後最大下落 ===")

    sep_low = (
        separated_df
        .groupby("Group")["EntryToLowPct"]
        .agg(["count", "mean", "median"])
        .round(2)
    )

    print(sep_low.to_string())


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
            f"コード列が見つかりません: "
            f"{list(top20.columns)}"
        )

    results = []

    print("==============================")
    print(" 9:33 びよーん仮説テスト")
    print("==============================")
    print(f"対象日       : {TARGET_DATE}")
    print(f"シグナル時刻 : {SIGNAL_TIME}")
    print(f"仮想買付時刻 : {ENTRY_TIME}")
    print(f"対象数       : {len(top20)}")
    print()

    for i, row in top20.iterrows():

        code = str(row[code_col]).strip()

        if code.endswith(".0"):
            code = code[:-2]

        name = ""

        if name_col is not None:
            name = str(row[name_col]).strip()

        try:
            result = analyze_code(
                code,
                name,
            )

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
                f"引け="
                f"{result['EntryToClosePct']:+.2f}%"
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

    print_summary(df)

    print()
    print("==============================")
    print(f"保存 : {OUTPUT_FILE}")
    print("==============================")


if __name__ == "__main__":
    main()
