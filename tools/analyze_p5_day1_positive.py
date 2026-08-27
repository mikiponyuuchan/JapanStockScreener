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

DAY_COLS = [
    "Day1",
    "Day2",
    "Day3",
    "Day4",
    "Day5",
]

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
    *DAY_COLS,
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
# A/C/D/Fなし
# ============================================================

base_p5 = (
    df[SCORE_COL].between(
        3,
        4,
        inclusive="both",
    )
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
# Day1～Day5評価可能
# ============================================================

complete = p5.dropna(
    subset=DAY_COLS
).copy()


# ============================================================
# Day1プラス
# ============================================================

positive = complete[
    complete["Day1"] > 0
].copy()


# ============================================================
# 将来成績
#
# Day1をシグナル時点とした場合、
# Day2～Day5をその後の成績として評価
# ============================================================

FUTURE_COLS = [
    "Day2",
    "Day3",
    "Day4",
    "Day5",
]


positive["future_max"] = (
    positive[
        FUTURE_COLS
    ]
    .max(axis=1)
)


positive["future_min"] = (
    positive[
        FUTURE_COLS
    ]
    .min(axis=1)
)


positive["day5_positive"] = (
    positive["Day5"] > 0
)


positive["future_hit_5pct"] = (
    positive["future_max"] >= 5
)


positive["future_hit_10pct"] = (
    positive["future_max"] >= 10
)


positive["future_hit_20pct"] = (
    positive["future_max"] >= 20
)


# ============================================================
# 基本件数
# ============================================================

print()
print("==============================")
print(" P5 DAY1 POSITIVE ANALYSIS")
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
    "Day1プラス :",
    len(positive),
)


# ============================================================
# Day1プラス組 全体
# ============================================================

def print_result(
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
            target["Day1"].median(),
            2,
        ),
    )

    print(
        "Day2中央値 :",
        round(
            target["Day2"].median(),
            2,
        ),
    )

    print(
        "Day5中央値 :",
        round(
            target["Day5"].median(),
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
        "Day2-5 +5%以上率 :",
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
        "Day2-5 +10%以上率 :",
        round(
            target[
                "future_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "Day2-5 +20%以上率 :",
        round(
            target[
                "future_hit_20pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "将来最大中央値 :",
        round(
            target[
                "future_max"
            ].median(),
            2,
        ),
    )

    print(
        "将来最小中央値 :",
        round(
            target[
                "future_min"
            ].median(),
            2,
        ),
    )


print_result(
    " DAY1 > 0",
    positive,
)


# ============================================================
# Day1強度別
# ============================================================

print()
print("==============================")
print(" DAY1 THRESHOLD")
print("==============================")
print()


thresholds = [
    0,
    1,
    2,
    3,
    5,
]


rows = []


for threshold in thresholds:

    target = complete[
        complete["Day1"] > threshold
    ].copy()

    if target.empty:
        continue

    target["future_max"] = (
        target[
            FUTURE_COLS
        ]
        .max(axis=1)
    )

    target["future_min"] = (
        target[
            FUTURE_COLS
        ]
        .min(axis=1)
    )

    target["day5_positive"] = (
        target["Day5"] > 0
    )

    target["future_hit_5pct"] = (
        target["future_max"] >= 5
    )

    target["future_hit_10pct"] = (
        target["future_max"] >= 10
    )

    target["future_hit_20pct"] = (
        target["future_max"] >= 20
    )

    rows.append(
        {
            "Day1条件":
                f">{threshold}%",

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

            "Day2-5で+5%以上率":
                (
                    target[
                        "future_hit_5pct"
                    ].mean()
                    * 100
                ),

            "Day2-5で+10%以上率":
                (
                    target[
                        "future_hit_10pct"
                    ].mean()
                    * 100
                ),

            "Day2-5で+20%以上率":
                (
                    target[
                        "future_hit_20pct"
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


threshold_result = pd.DataFrame(
    rows
)


print(
    threshold_result
    .round(2)
    .to_string(
        index=False
    )
)


# ============================================================
# Day1プラス + Day2もプラス
# ============================================================

print()
print("==============================")
print(" DAY1 + DAY2 CONTINUATION")
print("==============================")
print()


continuation_conditions = [
    (
        "Day1>0 / Day2>0",
        (complete["Day1"] > 0)
        & (complete["Day2"] > 0),
    ),
    (
        "Day1>=1 / Day2>0",
        (complete["Day1"] >= 1)
        & (complete["Day2"] > 0),
    ),
    (
        "Day1>=2 / Day2>0",
        (complete["Day1"] >= 2)
        & (complete["Day2"] > 0),
    ),
    (
        "Day1>=3 / Day2>0",
        (complete["Day1"] >= 3)
        & (complete["Day2"] > 0),
    ),
    (
        "Day1>=2 / Day2>=2",
        (complete["Day1"] >= 2)
        & (complete["Day2"] >= 2),
    ),
    (
        "Day1>=3 / Day2>=3",
        (complete["Day1"] >= 3)
        & (complete["Day2"] >= 3),
    ),
]


rows = []


for name, mask in continuation_conditions:

    target = complete[
        mask
    ].copy()

    if target.empty:
        continue

    target["future_max"] = (
        target[
            [
                "Day3",
                "Day4",
                "Day5",
            ]
        ]
        .max(axis=1)
    )

    target["future_min"] = (
        target[
            [
                "Day3",
                "Day4",
                "Day5",
            ]
        ]
        .min(axis=1)
    )

    target["day5_positive"] = (
        target["Day5"] > 0
    )

    target["future_hit_5pct"] = (
        target["future_max"] >= 5
    )

    target["future_hit_10pct"] = (
        target["future_max"] >= 10
    )

    target["future_hit_20pct"] = (
        target["future_max"] >= 20
    )

    rows.append(
        {
            "条件":
                name,

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

            "Day3-5で+20%以上率":
                (
                    target[
                        "future_hit_20pct"
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


continuation_result = pd.DataFrame(
    rows
)


print(
    continuation_result
    .round(2)
    .to_string(
        index=False
    )
)


# ============================================================
# Day1プラス銘柄 明細
# ============================================================

print()
print("==============================")
print(" DAY1 POSITIVE DETAILS")
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
    "Day3",
    "Day4",
    "Day5",
    "future_max",
    "future_min",
]


display_columns = [
    column
    for column in display_columns
    if column in positive.columns
]


print(
    positive[
        display_columns
    ]
    .sort_values(
        "Day1",
        ascending=False,
    )
    .round(2)
    .to_string(
        index=False
    )
)