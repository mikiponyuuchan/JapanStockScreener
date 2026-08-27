from pathlib import Path

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


# ============================================================
# 列名
# ============================================================

CODE_COL = "コード"
NAME_COL = "銘柄名"
DATE_COL = "検出日"

SCORE_COL = "初動スコア"
CHANGE5_COL = "5日騰落率"

AVOID_COLUMNS = [
    "A_STALL",
    "C_SPIKE",
    "D_OVERHEAT",
    "F_DECEL",
]


# ============================================================
# 読み込み
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
    low_memory=False,
)


# ============================================================
# 数値化
# ============================================================

numeric_columns = [
    SCORE_COL,
    CHANGE5_COL,
    "VolumeRatio20",
    "Day1",
    "Day2",
    "Day3",
    "Day4",
    "Day5",
]

for column in numeric_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )


# ============================================================
# 正式P5
#
# 初動スコア 3～4
# 5日騰落率 > 0
# VolumeRatio20 > 1
#
# 回避条件
# A_STALL
# C_SPIKE
# D_OVERHEAT
# F_DECEL
# ============================================================

base_p5 = (
    (df[SCORE_COL] >= 3)
    & (df[SCORE_COL] <= 4)
    & (df[CHANGE5_COL] > 0)
    & (df["VolumeRatio20"] > 1)
)


avoid = pd.Series(
    False,
    index=df.index,
)


for column in AVOID_COLUMNS:

    if column in df.columns:

        avoid |= (
            df[column]
            .fillna(False)
            .astype(bool)
        )


p5 = df[
    base_p5
    & ~avoid
].copy()


# ============================================================
# Day1～Day5完備
# ============================================================

complete = p5.dropna(
    subset=[
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
    ]
).copy()


# ============================================================
# 累積騰落率から実際の買値基準収益へ変換
#
# Day1 = 検出日終値からDay1終値までの累積騰落率
# Day2 = 検出日終値からDay2終値までの累積騰落率
#
# Day1終値買いの場合
#
#   Day2収益 =
#       (1 + Day2 / 100)
#       /
#       (1 + Day1 / 100)
#       - 1
#
# Day2終値買いも同様
# ============================================================

def return_from_entry(
    entry_return,
    future_return,
):

    return (
        (
            (1 + future_return / 100)
            /
            (1 + entry_return / 100)
        )
        - 1
    ) * 100


# ============================================================
# Day1買い収益
# ============================================================

complete["D1_Day2"] = return_from_entry(
    complete["Day1"],
    complete["Day2"],
)

complete["D1_Day3"] = return_from_entry(
    complete["Day1"],
    complete["Day3"],
)

complete["D1_Day4"] = return_from_entry(
    complete["Day1"],
    complete["Day4"],
)

complete["D1_Day5"] = return_from_entry(
    complete["Day1"],
    complete["Day5"],
)


# ============================================================
# Day2買い収益
# ============================================================

complete["D2_Day3"] = return_from_entry(
    complete["Day2"],
    complete["Day3"],
)

complete["D2_Day4"] = return_from_entry(
    complete["Day2"],
    complete["Day4"],
)

complete["D2_Day5"] = return_from_entry(
    complete["Day2"],
    complete["Day5"],
)


# ============================================================
# 比較対象
#
# ここでは「Day2時点で条件成立した銘柄」を固定して、
# 同じ銘柄をDay1で買った場合とDay2で買った場合を比較する。
#
# これによりDay2確認に払うコストを測定できる。
# ============================================================

candidate_main = complete[
    (complete["Day1"] >= 3)
    & (complete["Day2"] >= 3)
].copy()


candidate_strong = complete[
    (complete["Day1"] >= 4)
    & (complete["Day2"] >= 4)
].copy()


# ============================================================
# 成績計算
# ============================================================

def calculate_entry_stats(
    target,
    entry_type,
):

    if target.empty:
        return None

    if entry_type == "Day1":

        future_columns = [
            "D1_Day2",
            "D1_Day3",
            "D1_Day4",
            "D1_Day5",
        ]

        final_column = "D1_Day5"

    else:

        future_columns = [
            "D2_Day3",
            "D2_Day4",
            "D2_Day5",
        ]

        final_column = "D2_Day5"

    work = target.copy()

    work["entry_max"] = (
        work[future_columns]
        .max(axis=1)
    )

    work["entry_min"] = (
        work[future_columns]
        .min(axis=1)
    )

    result = {
        "買い": entry_type,

        "件数":
            len(work),

        "Day5収益平均":
            work[
                final_column
            ].mean(),

        "Day5収益中央値":
            work[
                final_column
            ].median(),

        "Day5勝率":
            (
                work[
                    final_column
                ] > 0
            ).mean()
            * 100,

        "最大利益中央値":
            work[
                "entry_max"
            ].median(),

        "最大下落中央値":
            work[
                "entry_min"
            ].median(),

        "+3%到達率":
            (
                work[
                    "entry_max"
                ] >= 3
            ).mean()
            * 100,

        "+5%到達率":
            (
                work[
                    "entry_max"
                ] >= 5
            ).mean()
            * 100,

        "+10%到達率":
            (
                work[
                    "entry_max"
                ] >= 10
            ).mean()
            * 100,

        "-2%到達率":
            (
                work[
                    "entry_min"
                ] <= -2
            ).mean()
            * 100,

        "-3%到達率":
            (
                work[
                    "entry_min"
                ] <= -3
            ).mean()
            * 100,

        "-5%到達率":
            (
                work[
                    "entry_min"
                ] <= -5
            ).mean()
            * 100,
    }

    return result


# ============================================================
# 比較表
# ============================================================

def compare_entries(
    title,
    target,
):

    print()
    print("==============================")
    print(title)
    print("==============================")
    print()

    print(
        "件数 :",
        len(target),
    )

    if target.empty:
        return

    rows = []

    day1_result = calculate_entry_stats(
        target,
        "Day1",
    )

    day2_result = calculate_entry_stats(
        target,
        "Day2",
    )

    if day1_result is not None:
        rows.append(day1_result)

    if day2_result is not None:
        rows.append(day2_result)

    result_df = pd.DataFrame(
        rows
    )

    print()
    print(
        result_df
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY1 vs DAY2 ENTRY")
print("==============================")
print()

print(
    "全件数 :",
    len(df),
)

print(
    "正式P5 :",
    len(p5),
)

print(
    "Day1-Day5完備 :",
    len(complete),
)

print(
    "基本候補 Day1>=3 / Day2>=3 :",
    len(candidate_main),
)

print(
    "強い候補 Day1>=4 / Day2>=4 :",
    len(candidate_strong),
)


# ============================================================
# 基本候補比較
# ============================================================

compare_entries(
    " MAIN CANDIDATE : Day1>=3 / Day2>=3",
    candidate_main,
)


# ============================================================
# 強い候補比較
# ============================================================

compare_entries(
    " STRONG CANDIDATE : Day1>=4 / Day2>=4",
    candidate_strong,
)


# ============================================================
# 個別比較
# ============================================================

print()
print("==============================")
print(" INDIVIDUAL COMPARISON")
print(" Day1>=3 / Day2>=3")
print("==============================")
print()


if not candidate_main.empty:

    detail = candidate_main.copy()

    detail["Day1買い_Day5"] = (
        detail["D1_Day5"]
    )

    detail["Day2買い_Day5"] = (
        detail["D2_Day5"]
    )

    detail["Day2待機コスト"] = (
        detail["Day2買い_Day5"]
        - detail["Day1買い_Day5"]
    )

    detail["Day1買い最大"] = (
        detail[
            [
                "D1_Day2",
                "D1_Day3",
                "D1_Day4",
                "D1_Day5",
            ]
        ]
        .max(axis=1)
    )

    detail["Day1買い最小"] = (
        detail[
            [
                "D1_Day2",
                "D1_Day3",
                "D1_Day4",
                "D1_Day5",
            ]
        ]
        .min(axis=1)
    )

    detail["Day2買い最大"] = (
        detail[
            [
                "D2_Day3",
                "D2_Day4",
                "D2_Day5",
            ]
        ]
        .max(axis=1)
    )

    detail["Day2買い最小"] = (
        detail[
            [
                "D2_Day3",
                "D2_Day4",
                "D2_Day5",
            ]
        ]
        .min(axis=1)
    )

    display_columns = [
        DATE_COL,
        CODE_COL,
        NAME_COL,
        SCORE_COL,
        CHANGE5_COL,
        "VolumeRatio20",
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
        "Day1買い_Day5",
        "Day2買い_Day5",
        "Day2待機コスト",
        "Day1買い最大",
        "Day1買い最小",
        "Day2買い最大",
        "Day2買い最小",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in detail.columns
    ]

    print(
        detail[
            display_columns
        ]
        .sort_values(
            "Day2買い_Day5",
            ascending=False,
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day2待機コスト
# ============================================================

print()
print("==============================")
print(" DAY2 WAITING COST")
print("==============================")
print()


if not candidate_main.empty:

    waiting = candidate_main.copy()

    waiting["Day1_to_Day2"] = (
        waiting["D1_Day2"]
    )

    print(
        "Day1からDay2までの値動き中央値 :",
        round(
            waiting[
                "Day1_to_Day2"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day1からDay2までの値動き平均 :",
        round(
            waiting[
                "Day1_to_Day2"
            ].mean(),
            2,
        ),
        "%",
    )

    print(
        "Day2の方がDay1より高値だった率 :",
        round(
            (
                waiting[
                    "Day1_to_Day2"
                ] > 0
            ).mean()
            * 100,
            2,
        ),
        "%",
    )


# ============================================================
# Day1買いとDay2買いの差
# ============================================================

print()
print("==============================")
print(" ENTRY ADVANTAGE")
print("==============================")
print()


if not candidate_main.empty:

    comparison = candidate_main.copy()

    comparison["Day1_final"] = (
        comparison["D1_Day5"]
    )

    comparison["Day2_final"] = (
        comparison["D2_Day5"]
    )

    comparison["Day1_minus_Day2"] = (
        comparison["Day1_final"]
        - comparison["Day2_final"]
    )

    print(
        "Day1買いがDay2買いを上回った率 :",
        round(
            (
                comparison[
                    "Day1_minus_Day2"
                ] > 0
            ).mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "Day1買い優位幅中央値 :",
        round(
            comparison[
                "Day1_minus_Day2"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day1買い優位幅平均 :",
        round(
            comparison[
                "Day1_minus_Day2"
            ].mean(),
            2,
        ),
        "%",
    )