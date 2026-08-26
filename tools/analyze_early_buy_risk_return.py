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
    / "early_buy_risk_return_summary.csv"
)

OUTPUT_DETAILS_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_risk_return_details.csv"
)


# ============================================================
# 読込
# ============================================================

def load_data():

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        dtype={"コード": str},
        low_memory=False,
    )

    numeric_columns = [
        "初動スコア",
        "前日比",
        "5日騰落率",
        "VolumeRatio20",
        "Day1",
        "Day2",
        "Day3",
        "Max3",
    ]

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df["検出日"] = pd.to_datetime(
        df["検出日"],
        errors="coerce",
    )

    return df


# ============================================================
# 危険回避
#
# H2は除外
# ============================================================

def add_danger_flag(df):

    df = df.copy()

    reason = (
        df["買い回避理由"]
        .fillna("")
        .astype(str)
    )

    df["危険回避4条件"] = (
        reason.str.contains(
            "A_STALL",
            regex=False,
        )
        |
        reason.str.contains(
            "C_SPIKE",
            regex=False,
        )
        |
        reason.str.contains(
            "D_OVERHEAT",
            regex=False,
        )
        |
        reason.str.contains(
            "F_DECEL",
            regex=False,
        )
    )

    return df


# ============================================================
# Min3
#
# 検出日終値を基準とした
# Day1～Day3の終値ベース最大逆行率
# ============================================================

def add_min3(df):

    df = df.copy()

    day_cols = [
        "Day1",
        "Day2",
        "Day3",
    ]

    df["Min3"] = (
        df[day_cols]
        .min(
            axis=1,
            skipna=True,
        )
    )

    # 3日すべて欠損ならMin3も欠損
    all_nan = (
        df[day_cols]
        .isna()
        .all(axis=1)
    )

    df.loc[
        all_nan,
        "Min3"
    ] = np.nan

    return df


# ============================================================
# P5条件
# ============================================================

def make_e_base(df):

    return (
        df["初動スコア"]
        .between(
            3,
            4,
            inclusive="both",
        )
        &
        (
            df["5日騰落率"] > 0
        )
        &
        (
            df["VolumeRatio20"] > 1
        )
        &
        (
            ~df["危険回避4条件"]
        )
    )


# ============================================================
# 条件定義
# ============================================================

def make_conditions(df):

    e = make_e_base(df)

    return {
        "P5基本":
            e,

        "広域_5x5":
            (
                e
                &
                (df["前日比"] >= 5)
                &
                (df["5日騰落率"] >= 5)
            ),

        "強_7x10":
            (
                e
                &
                (df["前日比"] >= 7)
                &
                (df["5日騰落率"] >= 10)
            ),

        "最強_10x10":
            (
                e
                &
                (df["前日比"] >= 10)
                &
                (df["5日騰落率"] >= 10)
            ),
    }


# ============================================================
# 集計
# ============================================================

def summarize(name, target):

    valid = target[
        target["Max3"].notna()
        &
        target["Min3"].notna()
    ].copy()

    n = len(valid)

    if n == 0:
        return None

    max3 = valid["Max3"]
    min3 = valid["Min3"]

    hit5 = int(
        (max3 >= 5).sum()
    )

    hit10 = int(
        (max3 >= 10).sum()
    )

    hit20 = int(
        (max3 >= 20).sum()
    )

    down3 = int(
        (min3 <= -3).sum()
    )

    down5 = int(
        (min3 <= -5).sum()
    )

    down10 = int(
        (min3 <= -10).sum()
    )

    avg_up = max3.mean()

    avg_down_abs = abs(
        min3.mean()
    )

    if avg_down_abs > 0:
        rr = avg_up / avg_down_abs
    else:
        rr = np.nan

    return {
        "条件": name,

        "候補数": len(target),

        "Max3_Min3有効件数": n,

        "Max3平均":
            round(avg_up, 2),

        "Max3中央値":
            round(
                max3.median(),
                2,
            ),

        "Min3平均":
            round(
                min3.mean(),
                2,
            ),

        "Min3中央値":
            round(
                min3.median(),
                2,
            ),

        "+5%件数":
            hit5,

        "+5%到達率":
            round(
                hit5 / n * 100,
                2,
            ),

        "+10%件数":
            hit10,

        "+10%到達率":
            round(
                hit10 / n * 100,
                2,
            ),

        "+20%件数":
            hit20,

        "+20%到達率":
            round(
                hit20 / n * 100,
                2,
            ),

        "-3%逆行件数":
            down3,

        "-3%逆行率":
            round(
                down3 / n * 100,
                2,
            ),

        "-5%逆行件数":
            down5,

        "-5%逆行率":
            round(
                down5 / n * 100,
                2,
            ),

        "-10%逆行件数":
            down10,

        "-10%逆行率":
            round(
                down10 / n * 100,
                2,
            ),

        "平均上昇/平均逆行":
            round(
                rr,
                2,
            )
            if pd.notna(rr)
            else np.nan,
    }


# ============================================================
# 成功したのに大きく逆行した例
# ============================================================

def print_success_with_drawdown(details):

    work = details[
        (details["Max3"] >= 10)
        &
        (details["Min3"] <= -3)
    ].copy()

    print()
    print("=" * 150)
    print("10%以上成功したが途中で-3%以上逆行した候補")
    print("=" * 150)

    if work.empty:

        print("該当なし")
        return

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
        "Day2",
        "Day3",
        "Max3",
        "Min3",
    ]

    print(
        work[
            columns
        ]
        .sort_values(
            [
                "Min3",
                "Max3",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .to_string(
            index=False
        )
    )


# ============================================================
# 失敗・大幅逆行例
# ============================================================

def print_large_drawdowns(details):

    work = details[
        details["Min3"] <= -10
    ].copy()

    print()
    print("=" * 150)
    print("-10%以上逆行した候補")
    print("=" * 150)

    if work.empty:

        print("該当なし")
        return

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
        "Day2",
        "Day3",
        "Max3",
        "Min3",
    ]

    print(
        work[
            columns
        ]
        .sort_values(
            "Min3"
        )
        .to_string(
            index=False
        )
    )


# ============================================================
# main
# ============================================================

def main():

    print()
    print("=" * 150)
    print("早期買い候補 リスク・リターン検証")
    print("=" * 150)

    df = load_data()

    df = add_danger_flag(
        df
    )

    df = add_min3(
        df
    )

    conditions = make_conditions(
        df
    )

    summary_rows = []
    detail_frames = []

    for name, mask in conditions.items():

        target = df[
            mask
        ].copy()

        result = summarize(
            name,
            target,
        )

        if result is not None:
            summary_rows.append(
                result
            )

        target["条件名"] = name

        detail_frames.append(
            target
        )

    summary = pd.DataFrame(
        summary_rows
    )

    details = pd.concat(
        detail_frames,
        ignore_index=True,
    )

    print()
    print("=" * 170)
    print("条件別 リスク・リターン")
    print("=" * 170)

    display_columns = [
        "条件",
        "候補数",
        "Max3_Min3有効件数",
        "Max3平均",
        "Max3中央値",
        "Min3平均",
        "Min3中央値",
        "+5%到達率",
        "+10%到達率",
        "+20%到達率",
        "-3%逆行率",
        "-5%逆行率",
        "-10%逆行率",
        "平均上昇/平均逆行",
    ]

    print(
        summary[
            display_columns
        ]
        .to_string(
            index=False
        )
    )

    print_success_with_drawdown(
        details
    )

    print_large_drawdowns(
        details
    )

    OUTPUT_SUMMARY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
    print("=" * 150)
    print(
        "集計保存 :",
        OUTPUT_SUMMARY_FILE
    )
    print(
        "詳細保存 :",
        OUTPUT_DETAILS_FILE
    )
    print("=" * 150)


if __name__ == "__main__":
    main()
