from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# パス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "buy_decision_backtest_panel.csv"
)

OUTPUT_SUMMARY_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_day1_entry_summary.csv"
)

OUTPUT_DETAILS_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_day1_entry_details.csv"
)


# ============================================================
# 設定
# ============================================================

DANGER_COLUMNS = [
    "A_STALL",
    "C_SPIKE",
    "D_OVERHEAT",
    "F_DECEL",
]


# ============================================================
# 共通
# ============================================================

def print_separator(width=150):
    print("=" * width)


def to_bool_series(series):
    if series.dtype == bool:
        return series.fillna(False)

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )


def safe_numeric(df, column):
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index)

    return pd.to_numeric(
        df[column],
        errors="coerce",
    )


# ============================================================
# 危険回避なし判定
# ============================================================

def make_no_danger_mask(df):
    danger = pd.Series(
        False,
        index=df.index,
    )

    for column in DANGER_COLUMNS:
        if column in df.columns:
            danger = danger | to_bool_series(df[column])

    return ~danger


# ============================================================
# 条件マスク
# ============================================================

def make_condition_masks(df):
    score = safe_numeric(df, "初動スコア")
    change1 = safe_numeric(df, "前日比")
    change5 = safe_numeric(df, "5日騰落率")
    volume20 = safe_numeric(df, "VolumeRatio20")

    no_danger = make_no_danger_mask(df)

    # P5基本
    p5_basic = (
        score.between(3, 4, inclusive="both")
        & no_danger
        & (change5 > 0)
        & (volume20 > 1)
    )

    # 広域 5x5
    wide_5x5 = (
        p5_basic
        & (change1 >= 5)
        & (change5 >= 5)
    )

    # 強 7x10
    strong_7x10 = (
        p5_basic
        & (change1 >= 7)
        & (change5 >= 10)
    )

    # 最強 10x10
    strongest_10x10 = (
        p5_basic
        & (change1 >= 10)
        & (change5 >= 10)
    )

    return {
        "P5基本": p5_basic,
        "広域_5x5": wide_5x5,
        "強_7x10": strong_7x10,
        "最強_10x10": strongest_10x10,
    }


# ============================================================
# Day1分類
# ============================================================

def classify_day1(value):
    if pd.isna(value):
        return "Day1なし"

    if value > 0:
        return "上昇継続"

    if value >= -3:
        return "軽い押し_0～-3"

    if value >= -5:
        return "深い押し_-3～-5"

    return "急失速_-5以下"


# ============================================================
# Day1終値から見た Day2 / Day3 の騰落率
# ============================================================

def calc_after_day1_returns(df):
    """
    Day1, Day2, Day3 はすべて「候補検出日の終値」を基準にした
    累積騰落率として保存されている。

    Day1終値で買ったと仮定した場合、

        Day1 -> Day2
        Day1 -> Day3

    のリターンへ変換する。
    """

    day1 = safe_numeric(df, "Day1")
    day2 = safe_numeric(df, "Day2")
    day3 = safe_numeric(df, "Day3")

    base1 = 1.0 + day1 / 100.0

    after_day1_day2 = (
        (1.0 + day2 / 100.0)
        / base1
        - 1.0
    ) * 100.0

    after_day1_day3 = (
        (1.0 + day3 / 100.0)
        / base1
        - 1.0
    ) * 100.0

    after_day1_day2 = after_day1_day2.where(
        day1.notna() & day2.notna()
    )

    after_day1_day3 = after_day1_day3.where(
        day1.notna() & day3.notna()
    )

    return (
        after_day1_day2,
        after_day1_day3,
    )


# ============================================================
# Day1買い後 Max / Min
# ============================================================

def add_day1_entry_metrics(df):
    result = df.copy()

    (
        result["Day1買い_Day2"],
        result["Day1買い_Day3"],
    ) = calc_after_day1_returns(result)

    after_cols = [
        "Day1買い_Day2",
        "Day1買い_Day3",
    ]

    result["Day1買い_Max2"] = (
        result[after_cols]
        .max(axis=1, skipna=True)
    )

    result["Day1買い_Min2"] = (
        result[after_cols]
        .min(axis=1, skipna=True)
    )

    no_future = result[after_cols].isna().all(axis=1)

    result.loc[
        no_future,
        "Day1買い_Max2"
    ] = np.nan

    result.loc[
        no_future,
        "Day1買い_Min2"
    ] = np.nan

    result["Day1分類"] = (
        safe_numeric(result, "Day1")
        .apply(classify_day1)
    )

    return result


# ============================================================
# 集計
# ============================================================

def summarize_group(
    part,
    condition_name,
    day1_class,
):
    valid = part[
        part["Day1買い_Max2"].notna()
        & part["Day1買い_Min2"].notna()
    ].copy()

    count_all = len(part)
    count_valid = len(valid)

    if count_valid == 0:
        return {
            "条件": condition_name,
            "Day1分類": day1_class,
            "候補数": count_all,
            "Day1買い有効件数": 0,
            "Day1平均": np.nan,
            "Day1中央値": np.nan,
            "買い後Max2平均": np.nan,
            "買い後Max2中央値": np.nan,
            "買い後Min2平均": np.nan,
            "買い後Min2中央値": np.nan,
            "+3%到達率": np.nan,
            "+5%到達率": np.nan,
            "+10%到達率": np.nan,
            "-3%逆行率": np.nan,
            "-5%逆行率": np.nan,
        }

    day1 = safe_numeric(valid, "Day1")
    max2 = safe_numeric(valid, "Day1買い_Max2")
    min2 = safe_numeric(valid, "Day1買い_Min2")

    return {
        "条件": condition_name,
        "Day1分類": day1_class,
        "候補数": count_all,
        "Day1買い有効件数": count_valid,

        "Day1平均": round(
            day1.mean(),
            2,
        ),
        "Day1中央値": round(
            day1.median(),
            2,
        ),

        "買い後Max2平均": round(
            max2.mean(),
            2,
        ),
        "買い後Max2中央値": round(
            max2.median(),
            2,
        ),

        "買い後Min2平均": round(
            min2.mean(),
            2,
        ),
        "買い後Min2中央値": round(
            min2.median(),
            2,
        ),

        "+3%到達率": round(
            (max2 >= 3).mean() * 100,
            2,
        ),

        "+5%到達率": round(
            (max2 >= 5).mean() * 100,
            2,
        ),

        "+10%到達率": round(
            (max2 >= 10).mean() * 100,
            2,
        ),

        "-3%逆行率": round(
            (min2 <= -3).mean() * 100,
            2,
        ),

        "-5%逆行率": round(
            (min2 <= -5).mean() * 100,
            2,
        ),
    }


# ============================================================
# 詳細作成
# ============================================================

def make_details(df):
    condition_masks = make_condition_masks(df)

    details = []

    for condition_name, mask in condition_masks.items():
        part = df.loc[mask].copy()

        if part.empty:
            continue

        part["条件名"] = condition_name

        details.append(part)

    if not details:
        return pd.DataFrame()

    return pd.concat(
        details,
        ignore_index=True,
    )


# ============================================================
# 集計作成
# ============================================================

def make_summary(details):
    if details.empty:
        return pd.DataFrame()

    rows = []

    day1_order = [
        "上昇継続",
        "軽い押し_0～-3",
        "深い押し_-3～-5",
        "急失速_-5以下",
        "Day1なし",
    ]

    condition_order = [
        "P5基本",
        "広域_5x5",
        "強_7x10",
        "最強_10x10",
    ]

    for condition_name in condition_order:
        condition_part = details[
            details["条件名"] == condition_name
        ].copy()

        if condition_part.empty:
            continue

        # 条件全体
        rows.append(
            summarize_group(
                condition_part,
                condition_name,
                "全体",
            )
        )

        # Day1分類別
        for day1_class in day1_order:
            part = condition_part[
                condition_part["Day1分類"]
                == day1_class
            ].copy()

            if part.empty:
                continue

            rows.append(
                summarize_group(
                    part,
                    condition_name,
                    day1_class,
                )
            )

    return pd.DataFrame(rows)


# ============================================================
# 注目例表示
# ============================================================

def print_examples(details):
    columns = [
        "条件名",
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "前日比",
        "5日騰落率",
        "VolumeRatio20",
        "Day1",
        "Day1分類",
        "Day2",
        "Day3",
        "Day1買い_Day2",
        "Day1買い_Day3",
        "Day1買い_Max2",
        "Day1買い_Min2",
    ]

    columns = [
        c for c in columns
        if c in details.columns
    ]

    # --------------------------------------------------------
    # Day1で下げた後に回復した例
    # --------------------------------------------------------

    print()
    print_separator()
    print("Day1で-3%以上下落したが、その後+5%以上上昇した候補")
    print_separator()

    part = details[
        (safe_numeric(details, "Day1") <= -3)
        & (
            safe_numeric(
                details,
                "Day1買い_Max2",
            )
            >= 5
        )
    ].copy()

    if part.empty:
        print("該当なし")
    else:
        part = part.sort_values(
            "Day1買い_Max2",
            ascending=False,
        )

        print(
            part[columns]
            .head(50)
            .to_string(index=False)
        )

    # --------------------------------------------------------
    # Day1上昇継続だが、その後失速した例
    # --------------------------------------------------------

    print()
    print_separator()
    print("Day1は上昇したが、その後-5%以上逆行した候補")
    print_separator()

    part = details[
        (safe_numeric(details, "Day1") > 0)
        & (
            safe_numeric(
                details,
                "Day1買い_Min2",
            )
            <= -5
        )
    ].copy()

    if part.empty:
        print("該当なし")
    else:
        part = part.sort_values(
            "Day1買い_Min2",
            ascending=True,
        )

        print(
            part[columns]
            .head(50)
            .to_string(index=False)
        )


# ============================================================
# main
# ============================================================

def main():
    print()
    print_separator()
    print("早期買い候補 Day1待機エントリー検証")
    print_separator()

    if not INPUT_FILE.exists():
        print()
        print(
            f"入力ファイルがありません : {INPUT_FILE}"
        )
        return

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        low_memory=False,
    )

    print()
    print(f"読込 : {INPUT_FILE}")
    print(f"行数 : {len(df)}")

    required_columns = [
        "初動スコア",
        "前日比",
        "5日騰落率",
        "VolumeRatio20",
        "Day1",
        "Day2",
        "Day3",
    ]

    missing = [
        c for c in required_columns
        if c not in df.columns
    ]

    if missing:
        print()
        print(
            "必要列がありません : "
            + ", ".join(missing)
        )
        return

    # --------------------------------------------------------
    # Day1買い指標
    # --------------------------------------------------------

    df = add_day1_entry_metrics(df)

    # --------------------------------------------------------
    # 詳細
    # --------------------------------------------------------

    details = make_details(df)

    if details.empty:
        print()
        print("対象候補がありません。")
        return

    # --------------------------------------------------------
    # 集計
    # --------------------------------------------------------

    summary = make_summary(details)

    print()
    print_separator(180)
    print("条件別 × Day1値動き別 エントリー成績")
    print_separator(180)

    if summary.empty:
        print("集計結果なし")
    else:
        print(
            summary.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # 注目例
    # --------------------------------------------------------

    print_examples(details)

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    summary.to_csv(
        OUTPUT_SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    details.to_csv(
        OUTPUT_DETAILS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print_separator()
    print(
        f"集計保存 : {OUTPUT_SUMMARY_FILE}"
    )
    print(
        f"詳細保存 : {OUTPUT_DETAILS_FILE}"
    )
    print_separator()


if __name__ == "__main__":
    main()
