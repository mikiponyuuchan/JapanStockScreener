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
#
#   初動スコア 3～4
#   5日騰落率 > 0
#   VolumeRatio20 > 1
#
# 回避条件
#
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
# Day1～Day5 完備
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
# Day1 -> Day2 の変化
# ============================================================

evaluation["Day2_minus_Day1"] = (
    evaluation["Day2"]
    - evaluation["Day1"]
)


# ============================================================
# Day2終値で買った場合の実収益
#
# Day値は検出日終値基準の騰落率なので、
# Day2を買値=0%へ変換する
# ============================================================

for day in [
    "Day3",
    "Day4",
    "Day5",
]:

    new_column = (
        f"{day}_from_entry"
    )

    evaluation[new_column] = (
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


# ============================================================
# Day2買い後の将来成績
# ============================================================

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


evaluation["day5_win"] = (
    evaluation[
        "Day5_from_entry"
    ] > 0
)


for threshold in [
    3,
    5,
    10,
]:

    evaluation[
        f"hit_plus_{threshold}"
    ] = (
        evaluation[
            "entry_future_max"
        ] >= threshold
    )


for threshold in [
    2,
    3,
    5,
]:

    evaluation[
        f"hit_minus_{threshold}"
    ] = (
        evaluation[
            "entry_future_min"
        ] <= -threshold
    )


# ============================================================
# 5日騰落率グループ
# ============================================================

def classify_change5(value):

    if value < 5:
        return "0~5"

    if value < 10:
        return "5~10"

    if value < 15:
        return "10~15"

    if value < 20:
        return "15~20"

    return ">=20"


evaluation["change5_group"] = (
    evaluation[
        CHANGE5_COL
    ]
    .apply(
        classify_change5
    )
)


change5_order = [
    "0~5",
    "5~10",
    "10~15",
    "15~20",
    ">=20",
]


# ============================================================
# Day2-Day1 グループ
# ============================================================

def classify_day2_shape(value):

    if value < -5:
        return "<-5"

    if value < -3:
        return "-5~-3"

    if value < -1:
        return "-3~-1"

    if value < 1:
        return "-1~+1"

    if value < 3:
        return "+1~+3"

    return ">=+3"


evaluation["shape_group"] = (
    evaluation[
        "Day2_minus_Day1"
    ]
    .apply(
        classify_day2_shape
    )
)


shape_order = [
    "<-5",
    "-5~-3",
    "-3~-1",
    "-1~+1",
    "+1~+3",
    ">=+3",
]


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 CHANGE5 x DAY2 SHAPE")
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
# 分布
# ============================================================

print()
print("==============================")
print(" 5DAY CHANGE DISTRIBUTION")
print("==============================")
print()

change_counts = (
    evaluation[
        "change5_group"
    ]
    .value_counts()
    .reindex(
        change5_order,
        fill_value=0,
    )
)

print(
    change_counts.to_string()
)


print()
print("==============================")
print(" DAY2-DAY1 DISTRIBUTION")
print("==============================")
print()

shape_counts = (
    evaluation[
        "shape_group"
    ]
    .value_counts()
    .reindex(
        shape_order,
        fill_value=0,
    )
)

print(
    shape_counts.to_string()
)


# ============================================================
# 集計関数
# ============================================================

def make_result_row(
    change_group,
    shape_group,
    target,
):

    return {
        "5日騰落率":
            change_group,

        "Day2-Day1":
            shape_group,

        "件数":
            len(target),

        "5日騰落率中央値":
            target[
                CHANGE5_COL
            ].median(),

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

        "Day5実収益中央値":
            target[
                "Day5_from_entry"
            ].median(),

        "Day5勝率":
            (
                target[
                    "day5_win"
                ].mean()
                * 100
            ),

        "最大利益中央値":
            target[
                "entry_future_max"
            ].median(),

        "最大下落中央値":
            target[
                "entry_future_min"
            ].median(),

        "+3%到達率":
            (
                target[
                    "hit_plus_3"
                ].mean()
                * 100
            ),

        "+5%到達率":
            (
                target[
                    "hit_plus_5"
                ].mean()
                * 100
            ),

        "+10%到達率":
            (
                target[
                    "hit_plus_10"
                ].mean()
                * 100
            ),

        "-2%到達率":
            (
                target[
                    "hit_minus_2"
                ].mean()
                * 100
            ),

        "-3%到達率":
            (
                target[
                    "hit_minus_3"
                ].mean()
                * 100
            ),

        "-5%到達率":
            (
                target[
                    "hit_minus_5"
                ].mean()
                * 100
            ),
    }


# ============================================================
# 5日騰落率 × Day2-Day1
# ============================================================

print()
print("==============================")
print(" 5DAY CHANGE x DAY2-DAY1")
print("==============================")
print()


summary_rows = []


for change_group in change5_order:

    for shape_group in shape_order:

        target = evaluation[
            (
                evaluation[
                    "change5_group"
                ]
                == change_group
            )
            & (
                evaluation[
                    "shape_group"
                ]
                == shape_group
            )
        ].copy()

        if target.empty:
            continue

        summary_rows.append(
            make_result_row(
                change_group,
                shape_group,
                target,
            )
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
# 5日騰落率だけ
# ============================================================

print()
print("==============================")
print(" 5DAY CHANGE ONLY")
print("==============================")
print()


change_rows = []


for change_group in change5_order:

    target = evaluation[
        evaluation[
            "change5_group"
        ] == change_group
    ].copy()

    if target.empty:
        continue

    change_rows.append(
        make_result_row(
            change_group,
            "ALL",
            target,
        )
    )


change_summary = pd.DataFrame(
    change_rows
)


if not change_summary.empty:

    print(
        change_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day2-Day1だけ
# ============================================================

print()
print("==============================")
print(" DAY2-DAY1 ONLY")
print("==============================")
print()


shape_rows = []


for shape_group in shape_order:

    target = evaluation[
        evaluation[
            "shape_group"
        ] == shape_group
    ].copy()

    if target.empty:
        continue

    shape_rows.append(
        make_result_row(
            "ALL",
            shape_group,
            target,
        )
    )


shape_summary = pd.DataFrame(
    shape_rows
)


if not shape_summary.empty:

    print(
        shape_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 危険仮説
#
# 5日騰落率 >= 15%
# かつ
# Day2-Day1 <= -3pt
#
# 「すでに上昇していて、Day2で失速」
# ============================================================

danger = evaluation[
    (
        evaluation[
            CHANGE5_COL
        ] >= 15
    )
    & (
        evaluation[
            "Day2_minus_Day1"
        ] <= -3
    )
].copy()


print()
print("==============================")
print(" DANGER CANDIDATE")
print(" 5DAY CHANGE >= 15%")
print(" DAY2-DAY1 <= -3pt")
print("==============================")
print()

print(
    "件数 :",
    len(danger),
)


if not danger.empty:

    print(
        "Day5実収益中央値 :",
        round(
            danger[
                "Day5_from_entry"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day5勝率 :",
        round(
            danger[
                "day5_win"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "最大利益中央値 :",
        round(
            danger[
                "entry_future_max"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "最大下落中央値 :",
        round(
            danger[
                "entry_future_min"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "+5%到達率 :",
        round(
            danger[
                "hit_plus_5"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "+10%到達率 :",
        round(
            danger[
                "hit_plus_10"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-3%到達率 :",
        round(
            danger[
                "hit_minus_3"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-5%到達率 :",
        round(
            danger[
                "hit_minus_5"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )


# ============================================================
# 危険候補 個別一覧
# ============================================================

print()
print("==============================")
print(" DANGER DETAILS")
print("==============================")
print()


if not danger.empty:

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
        "Day3_from_entry",
        "Day4_from_entry",
        "Day5_from_entry",
        "entry_future_max",
        "entry_future_min",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in danger.columns
    ]

    print(
        danger[
            display_columns
        ]
        .sort_values(
            "Day5_from_entry",
            ascending=True,
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 好調候補
#
# Day2-Day1 >= -1pt
#
# Day1からDay2まで大きく崩れていないグループ
# ============================================================

stable = evaluation[
    evaluation[
        "Day2_minus_Day1"
    ] >= -1
].copy()


print()
print("==============================")
print(" STABLE / IMPROVING")
print(" DAY2-DAY1 >= -1pt")
print("==============================")
print()

print(
    "件数 :",
    len(stable),
)


if not stable.empty:

    print(
        "Day5実収益中央値 :",
        round(
            stable[
                "Day5_from_entry"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day5勝率 :",
        round(
            stable[
                "day5_win"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "最大利益中央値 :",
        round(
            stable[
                "entry_future_max"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "最大下落中央値 :",
        round(
            stable[
                "entry_future_min"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "+5%到達率 :",
        round(
            stable[
                "hit_plus_5"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "+10%到達率 :",
        round(
            stable[
                "hit_plus_10"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-3%到達率 :",
        round(
            stable[
                "hit_minus_3"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-5%到達率 :",
        round(
            stable[
                "hit_minus_5"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )