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
# 現在の検証対象
#   初動スコア 3～4
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
# Day1～Day5完備
# ============================================================

evaluation = p5.dropna(
    subset=[
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
    ]
).copy()


# ============================================================
# Day1 -> Day2 変化幅
# ============================================================

evaluation["Day2_minus_Day1"] = (
    evaluation["Day2"]
    - evaluation["Day1"]
)


# ============================================================
# Day2終値で買った場合の実収益
#
# Day2を基準価格 = 100 として換算
# ============================================================

for day in [
    "Day3",
    "Day4",
    "Day5",
]:

    evaluation[
        f"{day}_from_entry"
    ] = (
        (
            1
            + evaluation[day] / 100
        )
        /
        (
            1
            + evaluation["Day2"] / 100
        )
        - 1
    ) * 100


entry_future_columns = [
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
]


evaluation["entry_future_max"] = (
    evaluation[
        entry_future_columns
    ]
    .max(axis=1)
)


evaluation["entry_future_min"] = (
    evaluation[
        entry_future_columns
    ]
    .min(axis=1)
)


evaluation["day5_positive"] = (
    evaluation[
        "Day5_from_entry"
    ] > 0
)


evaluation["hit_3pct"] = (
    evaluation[
        "entry_future_max"
    ] >= 3
)


evaluation["hit_5pct"] = (
    evaluation[
        "entry_future_max"
    ] >= 5
)


evaluation["hit_10pct"] = (
    evaluation[
        "entry_future_max"
    ] >= 10
)


evaluation["hit_minus_2pct"] = (
    evaluation[
        "entry_future_min"
    ] <= -2
)


evaluation["hit_minus_3pct"] = (
    evaluation[
        "entry_future_min"
    ] <= -3
)


evaluation["hit_minus_5pct"] = (
    evaluation[
        "entry_future_min"
    ] <= -5
)


# ============================================================
# Day1 -> Day2 下落幅分類
# ============================================================

def classify_drop(value):

    if value < -5:
        return "<-5"

    if value < -3:
        return "-5~-3"

    if value < -1:
        return "-3~-1"

    return ">=-1"


evaluation["drop_group"] = (
    evaluation[
        "Day2_minus_Day1"
    ]
    .apply(
        classify_drop
    )
)


# ============================================================
# Day2絶対位置分類
#
# 高値圏維持と完全崩れを分ける
# ============================================================

def classify_day2_position(value):

    if value >= 3:
        return ">=+3"

    if value >= 0:
        return "0~+3"

    if value >= -3:
        return "-3~0"

    if value >= -5:
        return "-5~-3"

    return "<-5"


evaluation["day2_position"] = (
    evaluation[
        "Day2"
    ]
    .apply(
        classify_day2_position
    )
)


# ============================================================
# 集計関数
# ============================================================

def make_summary(
    target,
    label,
):

    if target.empty:
        return None

    return {
        "条件": label,

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

        "変化幅中央値":
            target[
                "Day2_minus_Day1"
            ].median(),

        "5日騰落率中央値":
            target[
                CHANGE5_COL
            ].median(),

        "Day5実収益中央値":
            target[
                "Day5_from_entry"
            ].median(),

        "Day5勝率":
            target[
                "day5_positive"
            ].mean()
            * 100,

        "最大利益中央値":
            target[
                "entry_future_max"
            ].median(),

        "最大下落中央値":
            target[
                "entry_future_min"
            ].median(),

        "+3%到達率":
            target[
                "hit_3pct"
            ].mean()
            * 100,

        "+5%到達率":
            target[
                "hit_5pct"
            ].mean()
            * 100,

        "+10%到達率":
            target[
                "hit_10pct"
            ].mean()
            * 100,

        "-2%到達率":
            target[
                "hit_minus_2pct"
            ].mean()
            * 100,

        "-3%到達率":
            target[
                "hit_minus_3pct"
            ].mean()
            * 100,

        "-5%到達率":
            target[
                "hit_minus_5pct"
            ].mean()
            * 100,
    }


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY2 DROP x POSITION")
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
    len(evaluation),
)


# ============================================================
# Day2位置分布
# ============================================================

print()
print("==============================")
print(" DAY2 POSITION DISTRIBUTION")
print("==============================")
print()


position_order = [
    ">=+3",
    "0~+3",
    "-3~0",
    "-5~-3",
    "<-5",
]


position_counts = (
    evaluation[
        "day2_position"
    ]
    .value_counts()
    .reindex(
        position_order,
        fill_value=0,
    )
)


print(
    position_counts.to_string()
)


# ============================================================
# 下落幅分布
# ============================================================

print()
print("==============================")
print(" DAY2-DAY1 DROP DISTRIBUTION")
print("==============================")
print()


drop_order = [
    "<-5",
    "-5~-3",
    "-3~-1",
    ">=-1",
]


drop_counts = (
    evaluation[
        "drop_group"
    ]
    .value_counts()
    .reindex(
        drop_order,
        fill_value=0,
    )
)


print(
    drop_counts.to_string()
)


# ============================================================
# Day2-Day1 × Day2絶対位置
# ============================================================

print()
print("==============================")
print(" DROP x DAY2 POSITION")
print("==============================")
print()


summary_rows = []


for drop_group in drop_order:

    for position in position_order:

        target = evaluation[
            (
                evaluation[
                    "drop_group"
                ] == drop_group
            )
            & (
                evaluation[
                    "day2_position"
                ] == position
            )
        ].copy()

        result = make_summary(
            target,
            (
                f"{drop_group}"
                f" / "
                f"{position}"
            ),
        )

        if result is not None:

            summary_rows.append(
                result
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
# 重要部分
#
# Day2-Day1 <= -3pt の銘柄だけを調査
# ============================================================

drop_3 = evaluation[
    evaluation[
        "Day2_minus_Day1"
    ] <= -3
].copy()


print()
print("==============================")
print(" DROP <= -3pt BY DAY2 POSITION")
print("==============================")
print()


drop_3_rows = []


for position in position_order:

    target = drop_3[
        drop_3[
            "day2_position"
        ] == position
    ].copy()

    result = make_summary(
        target,
        position,
    )

    if result is not None:

        drop_3_rows.append(
            result
        )


drop_3_summary = pd.DataFrame(
    drop_3_rows
)


if not drop_3_summary.empty:

    print(
        drop_3_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 強い崩れ
#
# Day2-Day1 < -5pt
# ============================================================

drop_5 = evaluation[
    evaluation[
        "Day2_minus_Day1"
    ] < -5
].copy()


print()
print("==============================")
print(" DROP < -5pt BY DAY2 POSITION")
print("==============================")
print()


drop_5_rows = []


for position in position_order:

    target = drop_5[
        drop_5[
            "day2_position"
        ] == position
    ].copy()

    result = make_summary(
        target,
        position,
    )

    if result is not None:

        drop_5_rows.append(
            result
        )


drop_5_summary = pd.DataFrame(
    drop_5_rows
)


if not drop_5_summary.empty:

    print(
        drop_5_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 高値圏を維持している失速
#
# Day2-Day1 <= -3pt
# Day2 >= 0
# ============================================================

high_hold = evaluation[
    (
        evaluation[
            "Day2_minus_Day1"
        ] <= -3
    )
    & (
        evaluation[
            "Day2"
        ] >= 0
    )
].copy()


# ============================================================
# 完全に崩れた失速
#
# Day2-Day1 <= -3pt
# Day2 < 0
# ============================================================

broken = evaluation[
    (
        evaluation[
            "Day2_minus_Day1"
        ] <= -3
    )
    & (
        evaluation[
            "Day2"
        ] < 0
    )
].copy()


print()
print("==============================")
print(" HIGH HOLD vs BROKEN")
print("==============================")
print()


compare_rows = []


for label, target in [
    (
        "失速 / Day2>=0",
        high_hold,
    ),
    (
        "失速 / Day2<0",
        broken,
    ),
]:

    result = make_summary(
        target,
        label,
    )

    if result is not None:

        compare_rows.append(
            result
        )


compare_summary = pd.DataFrame(
    compare_rows
)


if not compare_summary.empty:

    print(
        compare_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 最重要候補
#
# A:
#   Day2-Day1 <= -3
#   Day2 >= 3
#
# B:
#   Day2-Day1 <= -3
#   0 <= Day2 < 3
#
# C:
#   Day2-Day1 <= -3
#   -3 <= Day2 < 0
#
# D:
#   Day2-Day1 <= -3
#   Day2 < -3
# ============================================================

candidate_a = evaluation[
    (
        evaluation[
            "Day2_minus_Day1"
        ] <= -3
    )
    & (
        evaluation[
            "Day2"
        ] >= 3
    )
].copy()


candidate_b = evaluation[
    (
        evaluation[
            "Day2_minus_Day1"
        ] <= -3
    )
    & (
        evaluation[
            "Day2"
        ] >= 0
    )
    & (
        evaluation[
            "Day2"
        ] < 3
    )
].copy()


candidate_c = evaluation[
    (
        evaluation[
            "Day2_minus_Day1"
        ] <= -3
    )
    & (
        evaluation[
            "Day2"
        ] >= -3
    )
    & (
        evaluation[
            "Day2"
        ] < 0
    )
].copy()


candidate_d = evaluation[
    (
        evaluation[
            "Day2_minus_Day1"
        ] <= -3
    )
    & (
        evaluation[
            "Day2"
        ] < -3
    )
].copy()


print()
print("==============================")
print(" FOUR ZONE COMPARISON")
print("==============================")
print()


zone_rows = []


for label, target in [
    (
        "A : Day2>=+3",
        candidate_a,
    ),
    (
        "B : 0<=Day2<+3",
        candidate_b,
    ),
    (
        "C : -3<=Day2<0",
        candidate_c,
    ),
    (
        "D : Day2<-3",
        candidate_d,
    ),
]:

    result = make_summary(
        target,
        label,
    )

    if result is not None:

        zone_rows.append(
            result
        )


zone_summary = pd.DataFrame(
    zone_rows
)


if not zone_summary.empty:

    print(
        zone_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 詳細
#
# Day2-Day1 <= -3pt を全件表示
# ============================================================

print()
print("==============================")
print(" DROP <= -3pt DETAILS")
print("==============================")
print()


display_columns = [
    DATE_COL,
    CODE_COL,
    NAME_COL,
    SCORE_COL,
    CHANGE5_COL,
    "VolumeRatio20",
    "Day1",
    "Day2",
    "Day2_minus_Day1",
    "drop_group",
    "day2_position",
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
    "entry_future_max",
    "entry_future_min",
]


display_columns = [
    column
    for column in display_columns
    if column in drop_3.columns
]


if not drop_3.empty:

    print(
        drop_3[
            display_columns
        ]
        .sort_values(
            [
                "Day2",
                "Day2_minus_Day1",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .round(2)
        .to_string(
            index=False
        )
    )