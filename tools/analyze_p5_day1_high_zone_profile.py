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
# Day1-Day5 完備
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
# Drop
# ============================================================

evaluation["Drop"] = (
    evaluation["Day2"]
    - evaluation["Day1"]
)


# ============================================================
# Entry = Day2
# ============================================================

for day in [3, 4, 5]:

    evaluation[f"Day{day}_from_entry"] = (
        (
            (1 + evaluation[f"Day{day}"] / 100)
            / (1 + evaluation["Day2"] / 100)
        )
        - 1
    ) * 100


evaluation["entry_future_max"] = (
    evaluation[
        [
            "Day3_from_entry",
            "Day4_from_entry",
            "Day5_from_entry",
        ]
    ]
    .max(axis=1)
)


evaluation["entry_future_min"] = (
    evaluation[
        [
            "Day3_from_entry",
            "Day4_from_entry",
            "Day5_from_entry",
        ]
    ]
    .min(axis=1)
)


# ============================================================
# 集計関数
# ============================================================

def summarize(data, label, total):

    count = len(data)

    if count == 0:

        return {
            "条件": label,
            "件数": 0,
            "保持率": 0.0,
        }

    day5 = data["Day5_from_entry"]
    future_max = data["entry_future_max"]
    future_min = data["entry_future_min"]

    return {
        "条件": label,
        "件数": count,
        "保持率": round(
            count / total * 100,
            2,
        ),
        "5日騰落率中央値": round(
            data[CHANGE5_COL].median(),
            2,
        ),
        "VolumeRatio20中央値": round(
            data["VolumeRatio20"].median(),
            2,
        ),
        "Day1中央値": round(
            data["Day1"].median(),
            2,
        ),
        "Day2中央値": round(
            data["Day2"].median(),
            2,
        ),
        "Drop中央値": round(
            data["Drop"].median(),
            2,
        ),
        "Day3実収益中央値": round(
            data["Day3_from_entry"].median(),
            2,
        ),
        "Day4実収益中央値": round(
            data["Day4_from_entry"].median(),
            2,
        ),
        "Day5実収益平均": round(
            day5.mean(),
            2,
        ),
        "Day5実収益中央値": round(
            day5.median(),
            2,
        ),
        "Day5勝率": round(
            (day5 > 0).mean() * 100,
            2,
        ),
        "最大利益中央値": round(
            future_max.median(),
            2,
        ),
        "最大下落中央値": round(
            future_min.median(),
            2,
        ),
        "+3%到達率": round(
            (future_max >= 3).mean() * 100,
            2,
        ),
        "+5%到達率": round(
            (future_max >= 5).mean() * 100,
            2,
        ),
        "+10%到達率": round(
            (future_max >= 10).mean() * 100,
            2,
        ),
        "-2%到達率": round(
            (future_min <= -2).mean() * 100,
            2,
        ),
        "-3%到達率": round(
            (future_min <= -3).mean() * 100,
            2,
        ),
        "-5%到達率": round(
            (future_min <= -5).mean() * 100,
            2,
        ),
    }


# ============================================================
# 条件
# ============================================================

total = len(evaluation)

mask_all = pd.Series(
    True,
    index=evaluation.index,
)

mask_drop_5 = (
    evaluation["Drop"] >= -5.0
)

mask_drop_3_5 = (
    evaluation["Drop"] >= -3.5
)

mask_drop_3 = (
    evaluation["Drop"] >= -3.0
)


# ============================================================
# 段階条件
#
# 1. Drop >= -3.5 はそのまま残す
#
# 2. -5.0 <= Drop < -3.5 は
#    5日騰落率 < 20
#    VolumeRatio20 < 3
#    の両方を満たす場合だけ救済
#
# 3. Drop < -5.0 は除外
# ============================================================

safe_zone = (
    evaluation["Drop"] >= -3.5
)

mixed_zone_rescue = (
    (evaluation["Drop"] >= -5.0)
    & (evaluation["Drop"] < -3.5)
    & (evaluation[CHANGE5_COL] < 20)
    & (evaluation["VolumeRatio20"] < 3)
)

mask_step_rule = (
    safe_zone
    | mixed_zone_rescue
)


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 FINAL FILTER CANDIDATE")
print("==============================")
print()

print("全件数 :", len(df))
print("正式P5 :", len(p5))
print("Day1-Day5完備 :", total)


# ============================================================
# 全体比較
# ============================================================

rows = [
    summarize(
        evaluation[mask_all],
        "除外なし",
        total,
    ),
    summarize(
        evaluation[mask_drop_5],
        "Drop >= -5.0",
        total,
    ),
    summarize(
        evaluation[mask_drop_3_5],
        "Drop >= -3.5",
        total,
    ),
    summarize(
        evaluation[mask_drop_3],
        "Drop >= -3.0",
        total,
    ),
    summarize(
        evaluation[mask_step_rule],
        "段階条件",
        total,
    ),
]


comparison = pd.DataFrame(rows)


print()
print("==============================")
print(" FINAL RULE COMPARISON")
print("==============================")
print()

print(
    comparison.to_string(
        index=False,
    )
)


# ============================================================
# 除外側の成績
# ============================================================

excluded_rows = [
    summarize(
        evaluation[~mask_drop_5],
        "Drop < -5.0",
        total,
    ),
    summarize(
        evaluation[~mask_drop_3_5],
        "Drop < -3.5",
        total,
    ),
    summarize(
        evaluation[~mask_drop_3],
        "Drop < -3.0",
        total,
    ),
    summarize(
        evaluation[~mask_step_rule],
        "段階条件で除外",
        total,
    ),
]


excluded_comparison = pd.DataFrame(
    excluded_rows
)


print()
print("==============================")
print(" EXCLUDED GROUP PERFORMANCE")
print("==============================")
print()

print(
    excluded_comparison.to_string(
        index=False,
    )
)


# ============================================================
# リスク改善量
# ============================================================

baseline = summarize(
    evaluation,
    "除外なし",
    total,
)


risk_rows = []

for label, mask in [
    ("Drop >= -5.0", mask_drop_5),
    ("Drop >= -3.5", mask_drop_3_5),
    ("Drop >= -3.0", mask_drop_3),
    ("段階条件", mask_step_rule),
]:

    result = summarize(
        evaluation[mask],
        label,
        total,
    )

    risk_rows.append(
        {
            "条件": label,
            "残存件数": result["件数"],
            "除外件数": total - result["件数"],
            "保持率": result["保持率"],
            "勝率改善": round(
                result["Day5勝率"]
                - baseline["Day5勝率"],
                2,
            ),
            "+3%到達率変化": round(
                result["+3%到達率"]
                - baseline["+3%到達率"],
                2,
            ),
            "+5%到達率変化": round(
                result["+5%到達率"]
                - baseline["+5%到達率"],
                2,
            ),
            "+10%到達率変化": round(
                result["+10%到達率"]
                - baseline["+10%到達率"],
                2,
            ),
            "-2%到達率改善": round(
                baseline["-2%到達率"]
                - result["-2%到達率"],
                2,
            ),
            "-3%到達率改善": round(
                baseline["-3%到達率"]
                - result["-3%到達率"],
                2,
            ),
            "-5%到達率改善": round(
                baseline["-5%到達率"]
                - result["-5%到達率"],
                2,
            ),
        }
    )


risk_comparison = pd.DataFrame(
    risk_rows
)


print()
print("==============================")
print(" FILTER EFFICIENCY")
print("==============================")
print()

print(
    risk_comparison.to_string(
        index=False,
    )
)


# ============================================================
# Drop >= -3.5 に対して
# 段階条件で救済される銘柄
# ============================================================

rescued = evaluation[
    mask_step_rule
    & ~mask_drop_3_5
].copy()


print()
print("==============================")
print(" RESCUED BY STEP RULE")
print(" Drop<-3.5 だが段階条件で残す")
print("==============================")
print()

print("件数 :", len(rescued))
print()


# ============================================================
# 段階条件によって除外される銘柄
# ============================================================

excluded = evaluation[
    ~mask_step_rule
].copy()


# ============================================================
# 個別表示用
# ============================================================

detail_columns = [
    DATE_COL,
    CODE_COL,
    NAME_COL,
    SCORE_COL,
    CHANGE5_COL,
    "VolumeRatio20",
    "Day1",
    "Day2",
    "Drop",
    "Day3",
    "Day4",
    "Day5",
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
    "entry_future_max",
    "entry_future_min",
]

detail_columns = [
    column
    for column in detail_columns
    if column in evaluation.columns
]


if len(rescued) > 0:

    rescued_details = rescued[
        detail_columns
    ].sort_values(
        "Drop",
        ascending=False,
    )

    print(
        rescued_details.to_string(
            index=False,
        )
    )


print()
print("==============================")
print(" EXCLUDED BY STEP RULE")
print("==============================")
print()

print("件数 :", len(excluded))
print()

if len(excluded) > 0:

    excluded_details = excluded[
        detail_columns
    ].sort_values(
        "Drop",
        ascending=False,
    )

    print(
        excluded_details.to_string(
            index=False,
        )
    )


# ============================================================
# 段階条件の内訳
# ============================================================

safe_count = (
    safe_zone
    & mask_step_rule
).sum()

rescue_count = (
    mixed_zone_rescue
).sum()

excluded_mixed = (
    (evaluation["Drop"] >= -5.0)
    & (evaluation["Drop"] < -3.5)
    & ~mixed_zone_rescue
).sum()

deep_excluded = (
    evaluation["Drop"] < -5.0
).sum()


print()
print("==============================")
print(" STEP RULE BREAKDOWN")
print("==============================")
print()

print(
    "Drop >= -3.5 で残存 :",
    safe_count,
)

print(
    "-5.0 <= Drop < -3.5 から救済 :",
    rescue_count,
)

print(
    "-5.0 <= Drop < -3.5 で除外 :",
    excluded_mixed,
)

print(
    "Drop < -5.0 で除外 :",
    deep_excluded,
)

print(
    "最終残存件数 :",
    mask_step_rule.sum(),
)

print(
    "最終保持率 :",
    round(
        mask_step_rule.mean() * 100,
        2,
    ),
    "%",
)

# ============================================================
# BUY PRIORITY ANALYSIS
#
# 段階条件通過銘柄のみを対象に、
# Day2時点で利用可能な情報を単独評価する。
#
# Day3-Day5は判定条件には使わず、
# 将来成績の評価専用。
# ============================================================

priority_base = evaluation[
    mask_step_rule
].copy()


print()
print("==============================")
print(" P5 DAY2 BUY PRIORITY ANALYSIS")
print("==============================")
print()

print(
    "段階条件通過 :",
    len(priority_base),
)


# ============================================================
# 優先度分析用サマリー
# ============================================================

def priority_summary(
    data,
    label,
):

    if data.empty:
        return None

    day5 = data[
        "Day5_from_entry"
    ]

    future_max = data[
        "entry_future_max"
    ]

    future_min = data[
        "entry_future_min"
    ]

    return {
        "条件": label,

        "件数":
            len(data),

        "Day1中央値":
            data["Day1"].median(),

        "Day2中央値":
            data["Day2"].median(),

        "Drop中央値":
            data["Drop"].median(),

        "5日騰落率中央値":
            data[CHANGE5_COL].median(),

        "VolumeRatio20中央値":
            data["VolumeRatio20"].median(),

        "Day5実収益平均":
            day5.mean(),

        "Day5実収益中央値":
            day5.median(),

        "Day5勝率":
            (day5 > 0).mean() * 100,

        "最大利益中央値":
            future_max.median(),

        "最大下落中央値":
            future_min.median(),

        "+3%到達率":
            (future_max >= 3).mean() * 100,

        "+5%到達率":
            (future_max >= 5).mean() * 100,

        "+10%到達率":
            (future_max >= 10).mean() * 100,

        "-2%到達率":
            (future_min <= -2).mean() * 100,

        "-3%到達率":
            (future_min <= -3).mean() * 100,

        "-5%到達率":
            (future_min <= -5).mean() * 100,
    }


def print_priority_table(
    title,
    groups,
):

    rows = []

    for label, target in groups:

        result = priority_summary(
            target,
            label,
        )

        if result is not None:
            rows.append(result)

    print()
    print("==============================")
    print(f" {title}")
    print("==============================")
    print()

    if not rows:

        print("該当なし")
        return

    summary = pd.DataFrame(
        rows
    )

    print(
        summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# SCORE
# ============================================================

print_priority_table(
    "INITIAL SCORE",
    [
        (
            "Score=3",
            priority_base[
                priority_base[
                    SCORE_COL
                ] == 3
            ].copy(),
        ),
        (
            "Score=4",
            priority_base[
                priority_base[
                    SCORE_COL
                ] == 4
            ].copy(),
        ),
    ],
)


# ============================================================
# DROP
# ============================================================

print_priority_table(
    "DROP RANGE",
    [
        (
            "Drop < -3",
            priority_base[
                priority_base[
                    "Drop"
                ] < -3
            ].copy(),
        ),
        (
            "-3 <= Drop < -1",
            priority_base[
                (
                    priority_base[
                        "Drop"
                    ] >= -3
                )
                & (
                    priority_base[
                        "Drop"
                    ] < -1
                )
            ].copy(),
        ),
        (
            "-1 <= Drop <= 1",
            priority_base[
                (
                    priority_base[
                        "Drop"
                    ] >= -1
                )
                & (
                    priority_base[
                        "Drop"
                    ] <= 1
                )
            ].copy(),
        ),
        (
            "Drop > 1",
            priority_base[
                priority_base[
                    "Drop"
                ] > 1
            ].copy(),
        ),
    ],
)


# ============================================================
# DAY2 POSITION
# ============================================================

print_priority_table(
    "DAY2 POSITION",
    [
        (
            "Day2 < -5",
            priority_base[
                priority_base[
                    "Day2"
                ] < -5
            ].copy(),
        ),
        (
            "-5 <= Day2 < -3",
            priority_base[
                (
                    priority_base[
                        "Day2"
                    ] >= -5
                )
                & (
                    priority_base[
                        "Day2"
                    ] < -3
                )
            ].copy(),
        ),
        (
            "-3 <= Day2 < 0",
            priority_base[
                (
                    priority_base[
                        "Day2"
                    ] >= -3
                )
                & (
                    priority_base[
                        "Day2"
                    ] < 0
                )
            ].copy(),
        ),
        (
            "0 <= Day2 < 3",
            priority_base[
                (
                    priority_base[
                        "Day2"
                    ] >= 0
                )
                & (
                    priority_base[
                        "Day2"
                    ] < 3
                )
            ].copy(),
        ),
        (
            "Day2 >= 3",
            priority_base[
                priority_base[
                    "Day2"
                ] >= 3
            ].copy(),
        ),
    ],
)


# ============================================================
# 5DAY CHANGE
# ============================================================

print_priority_table(
    "5DAY CHANGE",
    [
        (
            "Change < 5",
            priority_base[
                priority_base[
                    CHANGE5_COL
                ] < 5
            ].copy(),
        ),
        (
            "5 <= Change < 10",
            priority_base[
                (
                    priority_base[
                        CHANGE5_COL
                    ] >= 5
                )
                & (
                    priority_base[
                        CHANGE5_COL
                    ] < 10
                )
            ].copy(),
        ),
        (
            "10 <= Change < 20",
            priority_base[
                (
                    priority_base[
                        CHANGE5_COL
                    ] >= 10
                )
                & (
                    priority_base[
                        CHANGE5_COL
                    ] < 20
                )
            ].copy(),
        ),
        (
            "Change >= 20",
            priority_base[
                priority_base[
                    CHANGE5_COL
                ] >= 20
            ].copy(),
        ),
    ],
)


# ============================================================
# VOLUME RATIO 20
# ============================================================

print_priority_table(
    "VOLUME RATIO 20",
    [
        (
            "VR < 1.5",
            priority_base[
                priority_base[
                    "VolumeRatio20"
                ] < 1.5
            ].copy(),
        ),
        (
            "1.5 <= VR < 2",
            priority_base[
                (
                    priority_base[
                        "VolumeRatio20"
                    ] >= 1.5
                )
                & (
                    priority_base[
                        "VolumeRatio20"
                    ] < 2
                )
            ].copy(),
        ),
        (
            "2 <= VR < 3",
            priority_base[
                (
                    priority_base[
                        "VolumeRatio20"
                    ] >= 2
                )
                & (
                    priority_base[
                        "VolumeRatio20"
                    ] < 3
                )
            ].copy(),
        ),
        (
            "VR >= 3",
            priority_base[
                priority_base[
                    "VolumeRatio20"
                ] >= 3
            ].copy(),
        ),
    ],
)


# ============================================================
# DAY1 POSITION
# ============================================================

print_priority_table(
    "DAY1 POSITION",
    [
        (
            "Day1 < -5",
            priority_base[
                priority_base[
                    "Day1"
                ] < -5
            ].copy(),
        ),
        (
            "-5 <= Day1 < 0",
            priority_base[
                (
                    priority_base[
                        "Day1"
                    ] >= -5
                )
                & (
                    priority_base[
                        "Day1"
                    ] < 0
                )
            ].copy(),
        ),
        (
            "0 <= Day1 < 3",
            priority_base[
                (
                    priority_base[
                        "Day1"
                    ] >= 0
                )
                & (
                    priority_base[
                        "Day1"
                    ] < 3
                )
            ].copy(),
        ),
        (
            "Day1 >= 3",
            priority_base[
                priority_base[
                    "Day1"
                ] >= 3
            ].copy(),
        ),
    ],
)


# ============================================================
# PRIORITY CROSS ANALYSIS
#
# 段階条件通過64件について
# 初動スコア × Day1位置 × Drop
# をクロス分析する。
#
# Day3-Day5は評価専用。
# ============================================================

cross_base = priority_base.copy()


def add_cross_summary(
    rows,
    data,
    label,
):

    result = priority_summary(
        data,
        label,
    )

    if result is not None:
        rows.append(result)


# ============================================================
# SCORE x DAY1
# ============================================================

score_day1_rows = []

for score_value in [3, 4]:

    score_df = cross_base[
        cross_base[SCORE_COL] == score_value
    ].copy()

    add_cross_summary(
        score_day1_rows,
        score_df[
            score_df["Day1"] < 0
        ],
        f"Score{score_value} / Day1<0",
    )

    add_cross_summary(
        score_day1_rows,
        score_df[
            (score_df["Day1"] >= 0)
            & (score_df["Day1"] < 3)
        ],
        f"Score{score_value} / 0<=Day1<3",
    )

    add_cross_summary(
        score_day1_rows,
        score_df[
            score_df["Day1"] >= 3
        ],
        f"Score{score_value} / Day1>=3",
    )


print()
print("==============================")
print(" SCORE x DAY1")
print("==============================")
print()

if score_day1_rows:

    print(
        pd.DataFrame(
            score_day1_rows
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# SCORE x DROP
# ============================================================

score_drop_rows = []

for score_value in [3, 4]:

    score_df = cross_base[
        cross_base[SCORE_COL] == score_value
    ].copy()

    add_cross_summary(
        score_drop_rows,
        score_df[
            score_df["Drop"] < -3
        ],
        f"Score{score_value} / Drop<-3",
    )

    add_cross_summary(
        score_drop_rows,
        score_df[
            (score_df["Drop"] >= -3)
            & (score_df["Drop"] < -1)
        ],
        f"Score{score_value} / -3<=Drop<-1",
    )

    add_cross_summary(
        score_drop_rows,
        score_df[
            (score_df["Drop"] >= -1)
            & (score_df["Drop"] <= 1)
        ],
        f"Score{score_value} / -1<=Drop<=1",
    )

    add_cross_summary(
        score_drop_rows,
        score_df[
            score_df["Drop"] > 1
        ],
        f"Score{score_value} / Drop>1",
    )


print()
print("==============================")
print(" SCORE x DROP")
print("==============================")
print()

if score_drop_rows:

    print(
        pd.DataFrame(
            score_drop_rows
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# DAY1 x DROP
# ============================================================

day1_drop_rows = []

day1_groups = [
    (
        "Day1<0",
        cross_base[
            cross_base["Day1"] < 0
        ].copy(),
    ),
    (
        "0<=Day1<3",
        cross_base[
            (cross_base["Day1"] >= 0)
            & (cross_base["Day1"] < 3)
        ].copy(),
    ),
    (
        "Day1>=3",
        cross_base[
            cross_base["Day1"] >= 3
        ].copy(),
    ),
]


for day1_label, day1_df in day1_groups:

    add_cross_summary(
        day1_drop_rows,
        day1_df[
            day1_df["Drop"] < -3
        ],
        f"{day1_label} / Drop<-3",
    )

    add_cross_summary(
        day1_drop_rows,
        day1_df[
            (day1_df["Drop"] >= -3)
            & (day1_df["Drop"] < -1)
        ],
        f"{day1_label} / -3<=Drop<-1",
    )

    add_cross_summary(
        day1_drop_rows,
        day1_df[
            (day1_df["Drop"] >= -1)
            & (day1_df["Drop"] <= 1)
        ],
        f"{day1_label} / -1<=Drop<=1",
    )

    add_cross_summary(
        day1_drop_rows,
        day1_df[
            day1_df["Drop"] > 1
        ],
        f"{day1_label} / Drop>1",
    )


print()
print("==============================")
print(" DAY1 x DROP")
print("==============================")
print()

if day1_drop_rows:

    print(
        pd.DataFrame(
            day1_drop_rows
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# THREE-WAY CROSS
#
# Score × Day1 × Drop
#
# 小サンプルが多くなるため、
# 件数3以上だけ表示する。
# ============================================================

three_way_rows = []

for score_value in [3, 4]:

    for day1_label, day1_df in day1_groups:

        score_day1_df = day1_df[
            day1_df[
                SCORE_COL
            ] == score_value
        ].copy()

        drop_groups = [
            (
                "Drop<-3",
                score_day1_df[
                    score_day1_df[
                        "Drop"
                    ] < -3
                ].copy(),
            ),
            (
                "-3<=Drop<-1",
                score_day1_df[
                    (
                        score_day1_df[
                            "Drop"
                        ] >= -3
                    )
                    & (
                        score_day1_df[
                            "Drop"
                        ] < -1
                    )
                ].copy(),
            ),
            (
                "-1<=Drop<=1",
                score_day1_df[
                    (
                        score_day1_df[
                            "Drop"
                        ] >= -1
                    )
                    & (
                        score_day1_df[
                            "Drop"
                        ] <= 1
                    )
                ].copy(),
            ),
            (
                "Drop>1",
                score_day1_df[
                    score_day1_df[
                        "Drop"
                    ] > 1
                ].copy(),
            ),
        ]

        for drop_label, target in drop_groups:

            if len(target) < 3:
                continue

            add_cross_summary(
                three_way_rows,
                target,
                (
                    f"Score{score_value}"
                    f" / {day1_label}"
                    f" / {drop_label}"
                ),
            )


print()
print("==============================")
print(" SCORE x DAY1 x DROP")
print(" 件数3以上のみ")
print("==============================")
print()

if three_way_rows:

    print(
        pd.DataFrame(
            three_way_rows
        )
        .round(2)
        .to_string(
            index=False
        )
    )

else:

    print("該当なし")


print()
print("==============================")


# ============================================================
# DAY1 THRESHOLD SCAN
#
# ??????????????
# ??????ASCII??????????
# ============================================================

def day1_scan_summary(data, label):

    if data.empty:
        return None

    day5 = data["Day5_from_entry"]
    future_max = data["entry_future_max"]
    future_min = data["entry_future_min"]

    return {
        "Rule": label,
        "Count": len(data),

        "Day1_med":
            data["Day1"].median(),

        "Day2_med":
            data["Day2"].median(),

        "Drop_med":
            data["Drop"].median(),

        "Change5_med":
            data[CHANGE5_COL].median(),

        "VR20_med":
            data["VolumeRatio20"].median(),

        "Day5_mean":
            day5.mean(),

        "Day5_med":
            day5.median(),

        "WinRate":
            (day5 > 0).mean() * 100,

        "MaxGain_med":
            future_max.median(),

        "MaxLoss_med":
            future_min.median(),

        "Hit3":
            (future_max >= 3).mean() * 100,

        "Hit5":
            (future_max >= 5).mean() * 100,

        "Hit10":
            (future_max >= 10).mean() * 100,

        "HitMinus2":
            (future_min <= -2).mean() * 100,

        "HitMinus3":
            (future_min <= -3).mean() * 100,

        "HitMinus5":
            (future_min <= -5).mean() * 100,
    }


print()
print("==============================")
print(" DAY1 THRESHOLD SCAN")
print("==============================")
print()

thresholds = [
    0.0,
    0.5,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    3.5,
    4.0,
    5.0,
    6.0,
    8.0,
    10.0,
]

threshold_rows = []

base_count = len(priority_base)

for threshold in thresholds:

    target = priority_base[
        priority_base["Day1"] < threshold
    ].copy()

    result = day1_scan_summary(
        target,
        f"Day1<{threshold:g}",
    )

    if result is None:
        continue

    result["KeepRate"] = (
        len(target)
        / base_count
        * 100
    )

    threshold_rows.append(result)


threshold_table = pd.DataFrame(
    threshold_rows
)

threshold_columns = [
    "Rule",
    "Count",
    "KeepRate",
    "Day1_med",
    "Day2_med",
    "Drop_med",
    "Change5_med",
    "VR20_med",
    "Day5_mean",
    "Day5_med",
    "WinRate",
    "MaxGain_med",
    "MaxLoss_med",
    "Hit3",
    "Hit5",
    "Hit10",
    "HitMinus2",
    "HitMinus3",
    "HitMinus5",
]

print(
    threshold_table[
        threshold_columns
    ]
    .round(2)
    .to_string(index=False)
)


# ============================================================
# DAY1 BAND SCAN
# ============================================================

print()
print("==============================")
print(" DAY1 BAND SCAN")
print("==============================")
print()

bands = [
    (-999.0, 0.0, "Day1<0"),
    (0.0, 1.0, "0<=Day1<1"),
    (1.0, 2.0, "1<=Day1<2"),
    (2.0, 3.0, "2<=Day1<3"),
    (3.0, 4.0, "3<=Day1<4"),
    (4.0, 5.0, "4<=Day1<5"),
    (5.0, 6.0, "5<=Day1<6"),
    (6.0, 8.0, "6<=Day1<8"),
    (8.0, 10.0, "8<=Day1<10"),
    (10.0, 999.0, "Day1>=10"),
]

band_rows = []

for lower, upper, label in bands:

    target = priority_base[
        (priority_base["Day1"] >= lower)
        & (priority_base["Day1"] < upper)
    ].copy()

    result = day1_scan_summary(
        target,
        label,
    )

    if result is None:
        continue

    result["Share"] = (
        len(target)
        / base_count
        * 100
    )

    band_rows.append(result)


band_table = pd.DataFrame(
    band_rows
)

band_columns = [
    "Rule",
    "Count",
    "Share",
    "Day1_med",
    "Day2_med",
    "Drop_med",
    "Change5_med",
    "VR20_med",
    "Day5_mean",
    "Day5_med",
    "WinRate",
    "MaxGain_med",
    "MaxLoss_med",
    "Hit3",
    "Hit5",
    "Hit10",
    "HitMinus2",
    "HitMinus3",
    "HitMinus5",
]

print(
    band_table[
        band_columns
    ]
    .round(2)
    .to_string(index=False)
)


print()
print("==============================")
print(" DONE : DAY1 THRESHOLD SCAN")
print("==============================")
print()


# ============================================================
# DAY1 HIGH ZONE PROFILE
#
# Day1 >= 3% ???????????
# ???????????????????????
# ============================================================

high_zone = priority_base[
    priority_base["Day1"] >= 3.0
].copy()


print()
print("==============================")
print(" DAY1 HIGH ZONE PROFILE")
print("==============================")
print()

print(
    "Count :",
    len(high_zone),
)
print()


# ============================================================
# DETAIL
# ============================================================

high_zone["D3_entry"] = (
    high_zone["Day3_from_entry"]
)

high_zone["D4_entry"] = (
    high_zone["Day4_from_entry"]
)

high_zone["D5_entry"] = (
    high_zone["Day5_from_entry"]
)

high_zone["FutureMax"] = (
    high_zone["entry_future_max"]
)

high_zone["FutureMin"] = (
    high_zone["entry_future_min"]
)


detail_map = {
    DATE_COL: "Date",
    CODE_COL: "Code",
    NAME_COL: "Name",
    SCORE_COL: "Score",
    CHANGE5_COL: "Change5",
    "VolumeRatio20": "VR20",
    "Day1": "Day1",
    "Day2": "Day2",
    "Drop": "Drop",
    "Day3": "Day3",
    "Day4": "Day4",
    "Day5": "Day5",
    "D3_entry": "D3_entry",
    "D4_entry": "D4_entry",
    "D5_entry": "D5_entry",
    "FutureMax": "FutureMax",
    "FutureMin": "FutureMin",
}

available_detail = [
    column
    for column in detail_map
    if column in high_zone.columns
]

detail = high_zone[
    available_detail
].rename(
    columns={
        column: detail_map[column]
        for column in available_detail
    }
)

sort_columns = [
    column
    for column in [
        "Day1",
        "Score",
    ]
    if column in detail.columns
]

if sort_columns:

    detail = detail.sort_values(
        sort_columns,
        ascending=False,
    )


print(
    detail
    .round(2)
    .to_string(index=False)
)


# ============================================================
# HIGH ZONE BAND
# ============================================================

print()
print("==============================")
print(" HIGH ZONE BAND")
print("==============================")
print()

high_bands = [
    (
        3.0,
        5.0,
        "3<=Day1<5",
    ),
    (
        5.0,
        8.0,
        "5<=Day1<8",
    ),
    (
        8.0,
        10.0,
        "8<=Day1<10",
    ),
    (
        10.0,
        999.0,
        "Day1>=10",
    ),
]

rows = []

for lower, upper, label in high_bands:

    target = high_zone[
        (high_zone["Day1"] >= lower)
        & (high_zone["Day1"] < upper)
    ].copy()

    result = day1_scan_summary(
        target,
        label,
    )

    if result is not None:
        rows.append(result)


if rows:

    high_band_table = pd.DataFrame(
        rows
    )

    print(
        high_band_table
        .round(2)
        .to_string(index=False)
    )

else:

    print("No data")


# ============================================================
# SCORE PROFILE
# ============================================================

print()
print("==============================")
print(" HIGH ZONE x SCORE")
print("==============================")
print()

rows = []

for score_value in [3, 4]:

    target = high_zone[
        high_zone[SCORE_COL]
        == score_value
    ].copy()

    result = day1_scan_summary(
        target,
        f"Score={score_value}",
    )

    if result is not None:
        rows.append(result)


if rows:

    print(
        pd.DataFrame(rows)
        .round(2)
        .to_string(index=False)
    )

else:

    print("No data")


# ============================================================
# DAY2 SIGN
# ============================================================

print()
print("==============================")
print(" HIGH ZONE x DAY2")
print("==============================")
print()

day2_groups = [
    (
        "Day2<0",
        high_zone[
            high_zone["Day2"] < 0
        ].copy(),
    ),
    (
        "0<=Day2<3",
        high_zone[
            (high_zone["Day2"] >= 0)
            & (high_zone["Day2"] < 3)
        ].copy(),
    ),
    (
        "Day2>=3",
        high_zone[
            high_zone["Day2"] >= 3
        ].copy(),
    ),
]

rows = []

for label, target in day2_groups:

    result = day1_scan_summary(
        target,
        label,
    )

    if result is not None:
        rows.append(result)


if rows:

    print(
        pd.DataFrame(rows)
        .round(2)
        .to_string(index=False)
    )

else:

    print("No data")


# ============================================================
# DROP PROFILE
# ============================================================

print()
print("==============================")
print(" HIGH ZONE x DROP")
print("==============================")
print()

drop_groups_high = [
    (
        "Drop<-3",
        high_zone[
            high_zone["Drop"] < -3
        ].copy(),
    ),
    (
        "-3<=Drop<0",
        high_zone[
            (high_zone["Drop"] >= -3)
            & (high_zone["Drop"] < 0)
        ].copy(),
    ),
    (
        "Drop>=0",
        high_zone[
            high_zone["Drop"] >= 0
        ].copy(),
    ),
]

rows = []

for label, target in drop_groups_high:

    result = day1_scan_summary(
        target,
        label,
    )

    if result is not None:
        rows.append(result)


if rows:

    print(
        pd.DataFrame(rows)
        .round(2)
        .to_string(index=False)
    )

else:

    print("No data")


# ============================================================
# CHANGE5 PROFILE
# ============================================================

print()
print("==============================")
print(" HIGH ZONE x CHANGE5")
print("==============================")
print()

change_groups_high = [
    (
        "Change5<10",
        high_zone[
            high_zone[CHANGE5_COL] < 10
        ].copy(),
    ),
    (
        "10<=Change5<20",
        high_zone[
            (high_zone[CHANGE5_COL] >= 10)
            & (high_zone[CHANGE5_COL] < 20)
        ].copy(),
    ),
    (
        "Change5>=20",
        high_zone[
            high_zone[CHANGE5_COL] >= 20
        ].copy(),
    ),
]

rows = []

for label, target in change_groups_high:

    result = day1_scan_summary(
        target,
        label,
    )

    if result is not None:
        rows.append(result)


if rows:

    print(
        pd.DataFrame(rows)
        .round(2)
        .to_string(index=False)
    )

else:

    print("No data")


# ============================================================
# VOLUME PROFILE
# ============================================================

print()
print("==============================")
print(" HIGH ZONE x VR20")
print("==============================")
print()

vr_groups_high = [
    (
        "VR20<2",
        high_zone[
            high_zone["VolumeRatio20"] < 2
        ].copy(),
    ),
    (
        "2<=VR20<3",
        high_zone[
            (high_zone["VolumeRatio20"] >= 2)
            & (high_zone["VolumeRatio20"] < 3)
        ].copy(),
    ),
    (
        "VR20>=3",
        high_zone[
            high_zone["VolumeRatio20"] >= 3
        ].copy(),
    ),
]

rows = []

for label, target in vr_groups_high:

    result = day1_scan_summary(
        target,
        label,
    )

    if result is not None:
        rows.append(result)


if rows:

    print(
        pd.DataFrame(rows)
        .round(2)
        .to_string(index=False)
    )

else:

    print("No data")


print()
print("==============================")
print(" DONE : HIGH ZONE PROFILE")
print("==============================")
print()

print(" DONE : PRIORITY CROSS")
print("==============================")