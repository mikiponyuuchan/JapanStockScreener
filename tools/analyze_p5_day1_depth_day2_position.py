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
# 基本条件
#   初動スコア >= 3
#   5日騰落率 > 0
#   VolumeRatio20 > 1
#
# 回避条件
#   A_STALL
#   C_SPIKE
#   D_OVERHEAT
#   F_DECEL
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
# Day2時点で判定可能
# ============================================================

day2_ready = p5.dropna(
    subset=[
        "Day1",
        "Day2",
    ]
).copy()


# ============================================================
# Day1で押した銘柄
#
# 未来のDay3～Day5はここでは使用しない
# ============================================================

pullback = day2_ready[
    day2_ready["Day1"] < 0
].copy()


# ============================================================
# Day1 -> Day2 反発幅
# ============================================================

pullback["rebound_size"] = (
    pullback["Day2"]
    - pullback["Day1"]
)


# ============================================================
# Day3～Day5まで評価可能なもの
#
# Day3～Day5は結果評価だけに使用
# ============================================================

evaluation = pullback.dropna(
    subset=[
        "Day3",
        "Day4",
        "Day5",
    ]
).copy()


# ============================================================
# 将来成績
# ============================================================

future_columns = [
    "Day3",
    "Day4",
    "Day5",
]


evaluation["future_max"] = (
    evaluation[
        future_columns
    ]
    .max(axis=1)
)


evaluation["future_min"] = (
    evaluation[
        future_columns
    ]
    .min(axis=1)
)


evaluation["day5_positive"] = (
    evaluation["Day5"] > 0
)


evaluation["future_hit_5pct"] = (
    evaluation["future_max"] >= 5
)


evaluation["future_hit_10pct"] = (
    evaluation["future_max"] >= 10
)


# ============================================================
# Day1押し目深度
#
# shallow :  0 ～ -2%
# normal  : -2 ～ -4%
# deep    : -4 ～ -6%
# very_deep : -6%以下
# ============================================================

def classify_day1_depth(value):

    if value >= -2:
        return "0~-2"

    if value >= -4:
        return "-2~-4"

    if value >= -6:
        return "-4~-6"

    return "<-6"


evaluation["Day1深度"] = (
    evaluation["Day1"]
    .apply(
        classify_day1_depth
    )
)


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY1 DEPTH x DAY2 POSITION")
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
    "Day1-Day2あり :",
    len(day2_ready),
)

print(
    "Day1マイナス :",
    len(pullback),
)

print(
    "Day3-Day5評価可能 :",
    len(evaluation),
)


# ============================================================
# Day1深度分布
# ============================================================

print()
print("==============================")
print(" DAY1 DEPTH DISTRIBUTION")
print("==============================")
print()

depth_order = [
    "0~-2",
    "-2~-4",
    "-4~-6",
    "<-6",
]


depth_counts = (
    evaluation[
        "Day1深度"
    ]
    .value_counts()
    .reindex(
        depth_order,
        fill_value=0,
    )
)


print(
    depth_counts.to_string()
)


# ============================================================
# Day1深度 × Day2位置
# ============================================================

print()
print("==============================")
print(" DAY1 DEPTH x DAY2 POSITION")
print("==============================")
print()


day2_thresholds = [
    0,
    2,
    3,
    5,
]


summary_rows = []


for depth in depth_order:

    depth_df = evaluation[
        evaluation[
            "Day1深度"
        ] == depth
    ].copy()

    for threshold in day2_thresholds:

        target = depth_df[
            depth_df["Day2"] >= threshold
        ].copy()

        if target.empty:
            continue

        summary_rows.append(
            {
                "Day1深度":
                    depth,

                "Day2条件":
                    f">={threshold}%",

                "件数":
                    len(target),

                "Day1中央値":
                    target[
                        "Day1"
                    ].median(),

                "Day2中央値":
                    target[
                        "Day2"
                    ].median(),

                "反発幅中央値":
                    target[
                        "rebound_size"
                    ].median(),

                "Day5中央値":
                    target[
                        "Day5"
                    ].median(),

                "Day5プラス率":
                    (
                        target[
                            "day5_positive"
                        ].mean()
                        * 100
                    ),

                "Day3-5で+5%以上率":
                    (
                        target[
                            "future_hit_5pct"
                        ].mean()
                        * 100
                    ),

                "Day3-5で+10%以上率":
                    (
                        target[
                            "future_hit_10pct"
                        ].mean()
                        * 100
                    ),

                "将来最大中央値":
                    target[
                        "future_max"
                    ].median(),

                "将来最小中央値":
                    target[
                        "future_min"
                    ].median(),
            }
        )


summary = pd.DataFrame(
    summary_rows
)


if not summary.empty:

    print(
        summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day1深度だけの成績
# ============================================================

print()
print("==============================")
print(" DAY1 DEPTH ONLY")
print("==============================")
print()


for depth in depth_order:

    target = evaluation[
        evaluation[
            "Day1深度"
        ] == depth
    ].copy()

    if target.empty:
        continue

    print(
        f"Day1 {depth}%"
    )

    print(
        " 件数 :",
        len(target),
    )

    print(
        " Day1中央値 :",
        round(
            target[
                "Day1"
            ].median(),
            2,
        ),
    )

    print(
        " Day2中央値 :",
        round(
            target[
                "Day2"
            ].median(),
            2,
        ),
    )

    print(
        " Day5中央値 :",
        round(
            target[
                "Day5"
            ].median(),
            2,
        ),
    )

    print(
        " Day5プラス率 :",
        round(
            target[
                "day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        " Day3-5 +5%以上率 :",
        round(
            target[
                "future_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        " Day3-5 +10%以上率 :",
        round(
            target[
                "future_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print()


# ============================================================
# 有力ゾーン1
#
# Day1 -4%以内
# Day2 +2%以上
#
# 「浅い～普通の押し目からP5価格を明確に奪回」
# ============================================================

candidate_1 = evaluation[
    (evaluation["Day1"] >= -4)
    & (evaluation["Day2"] >= 2)
].copy()


# ============================================================
# 有力ゾーン2
#
# Day1 -6%以内
# Day2 +3%以上
# ============================================================

candidate_2 = evaluation[
    (evaluation["Day1"] >= -6)
    & (evaluation["Day2"] >= 3)
].copy()


# ============================================================
# 有力ゾーン3
#
# Day1の深さを問わず
# Day2 +5%以上
#
# 強い回復そのものを評価
# ============================================================

candidate_3 = evaluation[
    evaluation["Day2"] >= 5
].copy()


# ============================================================
# 候補成績表示
# ============================================================

def print_candidate_result(
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

    print(
        "Day1中央値 :",
        round(
            target[
                "Day1"
            ].median(),
            2,
        ),
    )

    print(
        "Day2中央値 :",
        round(
            target[
                "Day2"
            ].median(),
            2,
        ),
    )

    print(
        "反発幅中央値 :",
        round(
            target[
                "rebound_size"
            ].median(),
            2,
        ),
    )

    print(
        "Day5中央値 :",
        round(
            target[
                "Day5"
            ].median(),
            2,
        ),
    )

    print(
        "Day5プラス率 :",
        round(
            target[
                "day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "Day3-5 +5%以上率 :",
        round(
            target[
                "future_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "Day3-5 +10%以上率 :",
        round(
            target[
                "future_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )


print_candidate_result(
    " CANDIDATE 1 : Day1 >= -4 / Day2 >= 2",
    candidate_1,
)


print_candidate_result(
    " CANDIDATE 2 : Day1 >= -6 / Day2 >= 3",
    candidate_2,
)


print_candidate_result(
    " CANDIDATE 3 : Day2 >= 5",
    candidate_3,
)


# ============================================================
# Candidate 1 詳細
# ============================================================

print()
print("==============================")
print(" CANDIDATE 1 DETAILS")
print("==============================")
print()


if not candidate_1.empty:

    display_columns = [
        DATE_COL,
        CODE_COL,
        NAME_COL,
        SCORE_COL,
        CHANGE5_COL,
        "VolumeRatio20",
        "Day1",
        "Day2",
        "rebound_size",
        "Day3",
        "Day4",
        "Day5",
        "future_max",
        "future_min",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in candidate_1.columns
    ]

    print(
        candidate_1[
            display_columns
        ]
        .sort_values(
            [
                "Day2",
                "rebound_size",
            ],
            ascending=[
                False,
                False,
            ],
        )
        .round(2)
        .to_string(
            index=False
        )
    )