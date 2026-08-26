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
    / "entry_timing_comparison_summary.csv"
)

OUTPUT_DETAILS_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "entry_timing_comparison_details.csv"
)


# ============================================================
# 共通
# ============================================================

def print_separator(width=150):
    print("=" * width)


def to_numeric(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )
    return df


def calc_return_from_entry(entry_return, future_return):
    """
    検出日終値基準の累積騰落率から、
    エントリー日終値基準の騰落率へ変換する。

    例:
        Day1 = -8%
        Day2 = +6%

    Day1終値で買った場合のDay2騰落率:
        (1.06 / 0.92 - 1) * 100
    """

    entry_factor = 1 + entry_return / 100
    future_factor = 1 + future_return / 100

    result = (
        future_factor
        / entry_factor
        - 1
    ) * 100

    return result


def build_entry_result(
    df,
    entry_name,
    entry_day,
    future_days,
    condition,
):
    """
    指定したエントリー方式について、
    買った後3営業日のリターンを作成する。
    """

    work = df.loc[condition].copy()

    entry_col = f"Day{entry_day}"

    if entry_day == 0:
        # 検出日終値買い
        work["EntryReturn"] = 0.0

        result_cols = []

        for i, day in enumerate(
            future_days,
            start=1,
        ):
            source_col = f"Day{day}"
            result_col = f"After{i}"

            work[result_col] = work[source_col]
            result_cols.append(result_col)

    else:
        work["EntryReturn"] = work[entry_col]

        result_cols = []

        for i, day in enumerate(
            future_days,
            start=1,
        ):
            source_col = f"Day{day}"
            result_col = f"After{i}"

            work[result_col] = calc_return_from_entry(
                work[entry_col],
                work[source_col],
            )

            result_cols.append(result_col)

    # --------------------------------------------------------
    # 3営業日すべて揃ったものだけ評価
    # --------------------------------------------------------

    complete = (
        work[result_cols]
        .notna()
        .all(axis=1)
    )

    work["EntryMethod"] = entry_name
    work["Complete3"] = complete

    work["EntryMax3"] = np.nan
    work["EntryMin3"] = np.nan

    work.loc[
        complete,
        "EntryMax3",
    ] = (
        work.loc[
            complete,
            result_cols,
        ]
        .max(axis=1)
        .round(2)
    )

    work.loc[
        complete,
        "EntryMin3",
    ] = (
        work.loc[
            complete,
            result_cols,
        ]
        .min(axis=1)
        .round(2)
    )

    for col in result_cols:
        work[col] = work[col].round(2)

    return work


def summarize_entry(work):
    confirmed = work[
        work["Complete3"]
    ].copy()

    if confirmed.empty:
        return {
            "方式": work["EntryMethod"].iloc[0]
            if not work.empty
            else "",
            "候補数": len(work),
            "3日評価有効件数": 0,
            "Max3平均": np.nan,
            "Max3中央値": np.nan,
            "Min3平均": np.nan,
            "Min3中央値": np.nan,
            "+3%到達率": np.nan,
            "+5%到達率": np.nan,
            "+10%到達率": np.nan,
            "+20%到達率": np.nan,
            "-3%逆行率": np.nan,
            "-5%逆行率": np.nan,
            "-10%逆行率": np.nan,
        }

    max3 = confirmed["EntryMax3"]
    min3 = confirmed["EntryMin3"]

    return {
        "方式":
            confirmed["EntryMethod"].iloc[0],

        "候補数":
            len(work),

        "3日評価有効件数":
            len(confirmed),

        "Max3平均":
            round(max3.mean(), 2),

        "Max3中央値":
            round(max3.median(), 2),

        "Min3平均":
            round(min3.mean(), 2),

        "Min3中央値":
            round(min3.median(), 2),

        "+3%到達率":
            round(
                (max3 >= 3).mean() * 100,
                2,
            ),

        "+5%到達率":
            round(
                (max3 >= 5).mean() * 100,
                2,
            ),

        "+10%到達率":
            round(
                (max3 >= 10).mean() * 100,
                2,
            ),

        "+20%到達率":
            round(
                (max3 >= 20).mean() * 100,
                2,
            ),

        "-3%逆行率":
            round(
                (min3 <= -3).mean() * 100,
                2,
            ),

        "-5%逆行率":
            round(
                (min3 <= -5).mean() * 100,
                2,
            ),

        "-10%逆行率":
            round(
                (min3 <= -10).mean() * 100,
                2,
            ),
    }


# ============================================================
# P5条件
# ============================================================

def make_p5_condition(df):
    """
    これまで検証してきたP5条件。

    Score 3～4
    危険回避4条件なし
    5日騰落率 > 0
    VolumeRatio20 > 1

    H2は危険回避から除外。
    """

    score = pd.to_numeric(
        df["初動スコア"],
        errors="coerce",
    )

    change5 = pd.to_numeric(
        df["5日騰落率"],
        errors="coerce",
    )

    vol20 = pd.to_numeric(
        df["VolumeRatio20"],
        errors="coerce",
    )

    danger = (
        df["A_STALL"].fillna(False).astype(bool)
        | df["C_SPIKE"].fillna(False).astype(bool)
        | df["D_OVERHEAT"].fillna(False).astype(bool)
        | df["F_DECEL"].fillna(False).astype(bool)
    )

    return (
        score.between(3, 4)
        & (~danger)
        & (change5 > 0)
        & (vol20 > 1)
    )


def make_strong_7x10_condition(df, p5_condition):
    return (
        p5_condition
        & (df["前日比"] >= 7)
        & (df["5日騰落率"] >= 10)
    )


def make_strongest_10x10_condition(
    df,
    p5_condition,
):
    return (
        p5_condition
        & (df["前日比"] >= 10)
        & (df["5日騰落率"] >= 10)
    )


# ============================================================
# 条件ごとの3方式比較
# ============================================================

def analyze_condition(
    df,
    condition_name,
    base_condition,
):
    results = []

    # --------------------------------------------------------
    # 1. 検出日終値買い
    # --------------------------------------------------------

    detection = build_entry_result(
        df=df,
        entry_name=f"{condition_name}_検出日買い",
        entry_day=0,
        future_days=[1, 2, 3],
        condition=base_condition,
    )

    results.append(detection)

    # --------------------------------------------------------
    # 2. Day1終値買い
    #
    # Day1の方向に関係なく翌日終値で買う
    # --------------------------------------------------------

    day1_wait_condition = (
        base_condition
        & df["Day1"].notna()
    )

    day1_entry = build_entry_result(
        df=df,
        entry_name=f"{condition_name}_Day1待機",
        entry_day=1,
        future_days=[2, 3, 4],
        condition=day1_wait_condition,
    )

    results.append(day1_entry)

    # --------------------------------------------------------
    # 3A. Day2反発確認
    #
    # Day1 < 0
    # Day2 > Day1
    #
    # 検出日終値には戻っていなくても、
    # 下落幅が縮小すれば反発とみなす。
    # --------------------------------------------------------

    rebound_a_condition = (
        base_condition
        & (df["Day1"] < 0)
        & (df["Day2"] > df["Day1"])
    )

    rebound_a = build_entry_result(
        df=df,
        entry_name=(
            f"{condition_name}_"
            "Day2反発A_Day2>Day1"
        ),
        entry_day=2,
        future_days=[3, 4, 5],
        condition=rebound_a_condition,
    )

    results.append(rebound_a)

    # --------------------------------------------------------
    # 3B. Day2強反発確認
    #
    # Day1 < 0
    # Day2 > 0
    #
    # 検出日終値を回復した場合のみ買う。
    # --------------------------------------------------------

    rebound_b_condition = (
        base_condition
        & (df["Day1"] < 0)
        & (df["Day2"] > 0)
    )

    rebound_b = build_entry_result(
        df=df,
        entry_name=(
            f"{condition_name}_"
            "Day2反発B_Day2>0"
        ),
        entry_day=2,
        future_days=[3, 4, 5],
        condition=rebound_b_condition,
    )

    results.append(rebound_b)

    return results


# ============================================================
# メイン
# ============================================================

def main():

    print()
    print_separator()
    print("早期買い候補 エントリータイミング比較")
    print_separator()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"入力ファイルがありません: {INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        low_memory=False,
    )

    print()
    print("読込 :", INPUT_FILE)
    print("行数 :", len(df))

    numeric_columns = [
        "初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
        "Max3",
    ]

    df = to_numeric(
        df,
        numeric_columns,
    )

    required_columns = [
        "初動スコア",
        "前日比",
        "5日騰落率",
        "VolumeRatio20",
        "A_STALL",
        "C_SPIKE",
        "D_OVERHEAT",
        "F_DECEL",
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise KeyError(
            f"必要列がありません: {missing}"
        )

    # --------------------------------------------------------
    # 基本条件
    # --------------------------------------------------------

    p5_condition = make_p5_condition(df)

    strong_condition = (
        make_strong_7x10_condition(
            df,
            p5_condition,
        )
    )

    strongest_condition = (
        make_strongest_10x10_condition(
            df,
            p5_condition,
        )
    )

    condition_sets = [
        (
            "P5基本",
            p5_condition,
        ),
        (
            "強_7x10",
            strong_condition,
        ),
        (
            "最強_10x10",
            strongest_condition,
        ),
    ]

    all_results = []

    for condition_name, condition in condition_sets:

        parts = analyze_condition(
            df=df,
            condition_name=condition_name,
            base_condition=condition,
        )

        all_results.extend(parts)

    # --------------------------------------------------------
    # 集計
    # --------------------------------------------------------

    summary_rows = []

    for work in all_results:
        summary_rows.append(
            summarize_entry(work)
        )

    summary = pd.DataFrame(
        summary_rows
    )

    print()
    print_separator(180)
    print("条件別 エントリー方式比較")
    print_separator(180)

    print(
        summary.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # 詳細統合
    # --------------------------------------------------------

    detail_columns = [
        "EntryMethod",
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
        "EntryReturn",
        "After1",
        "After2",
        "After3",
        "EntryMax3",
        "EntryMin3",
        "Complete3",
    ]

    detail_parts = []

    for work in all_results:

        available = [
            col
            for col in detail_columns
            if col in work.columns
        ]

        detail_parts.append(
            work[available].copy()
        )

    details = pd.concat(
        detail_parts,
        ignore_index=True,
    )

    # --------------------------------------------------------
    # Day2反発成功例
    # --------------------------------------------------------

    rebound_success = details[
        details["EntryMethod"]
        .str.contains(
            "Day2反発",
            na=False,
        )
        & details["Complete3"]
        & (
            details["EntryMax3"]
            >= 5
        )
    ].copy()

    print()
    print_separator()
    print(
        "Day2反発確認後に買い、"
        "その後3営業日で+5%以上となった候補"
    )
    print_separator()

    show_columns = [
        "EntryMethod",
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
        "Day4",
        "Day5",
        "EntryMax3",
        "EntryMin3",
    ]

    if rebound_success.empty:
        print("該当なし")
    else:
        print(
            rebound_success[
                show_columns
            ]
            .sort_values(
                "EntryMax3",
                ascending=False,
            )
            .to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # Day2反発後の失敗例
    # --------------------------------------------------------

    rebound_failure = details[
        details["EntryMethod"]
        .str.contains(
            "Day2反発",
            na=False,
        )
        & details["Complete3"]
        & (
            details["EntryMin3"]
            <= -5
        )
    ].copy()

    print()
    print_separator()
    print(
        "Day2反発確認後に買ったが、"
        "その後-5%以上逆行した候補"
    )
    print_separator()

    if rebound_failure.empty:
        print("該当なし")
    else:
        print(
            rebound_failure[
                show_columns
            ]
            .sort_values(
                "EntryMin3",
                ascending=True,
            )
            .to_string(
                index=False
            )
        )

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
        "集計保存 :",
        OUTPUT_SUMMARY_FILE,
    )
    print(
        "詳細保存 :",
        OUTPUT_DETAILS_FILE,
    )
    print_separator()


if __name__ == "__main__":
    main()

