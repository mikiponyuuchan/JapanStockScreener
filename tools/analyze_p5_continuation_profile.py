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
# 今回は初動スコア3～4に限定
#
#   初動スコア >= 3
#   初動スコア <= 4
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
# 将来成績
#
# Day1・Day2で判定したあとを見るため
# Day3～Day5のみを将来成績とする
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


evaluation["future_hit_20pct"] = (
    evaluation["future_max"] >= 20
)


# ============================================================
# Day1 → Day2 の変化
# ============================================================

evaluation["day2_minus_day1"] = (
    evaluation["Day2"]
    - evaluation["Day1"]
)


# ============================================================
# 継続上昇型
#
# Day1 >= 3%
# Day2 >= 3%
# ============================================================

continuation = evaluation[
    (evaluation["Day1"] >= 3)
    & (evaluation["Day2"] >= 3)
].copy()


other = evaluation[
    ~(
        (evaluation["Day1"] >= 3)
        & (evaluation["Day2"] >= 3)
    )
].copy()


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 CONTINUATION PROFILE")
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

print(
    "継続上昇型 :",
    len(continuation),
)

print(
    "その他 :",
    len(other),
)


# ============================================================
# 集計関数
# ============================================================

def make_summary(
    label,
    target,
):

    if target.empty:

        return {
            "グループ": label,
            "件数": 0,
        }

    return {
        "グループ":
            label,

        "件数":
            len(target),

        "初動スコア中央値":
            target[
                SCORE_COL
            ].median(),

        "5日騰落率中央値":
            target[
                CHANGE5_COL
            ].median(),

        "VolumeRatio20中央値":
            target[
                "VolumeRatio20"
            ].median(),

        "Day1中央値":
            target[
                "Day1"
            ].median(),

        "Day2中央値":
            target[
                "Day2"
            ].median(),

        "Day2-Day1中央値":
            target[
                "day2_minus_day1"
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


# ============================================================
# 継続上昇型 vs その他
# ============================================================

print()
print("==============================")
print(" CONTINUATION vs OTHER")
print("==============================")
print()


comparison = pd.DataFrame(
    [
        make_summary(
            "Day1>=3 / Day2>=3",
            continuation,
        ),
        make_summary(
            "その他",
            other,
        ),
    ]
)


print(
    comparison
    .round(2)
    .to_string(
        index=False
    )
)


# ============================================================
# 初動スコア別
# ============================================================

print()
print("==============================")
print(" SCORE PROFILE")
print("==============================")
print()


score_rows = []


for score_value in [
    3,
    4,
]:

    target = continuation[
        continuation[
            SCORE_COL
        ] == score_value
    ].copy()

    if target.empty:
        continue

    row = make_summary(
        f"Score {score_value}",
        target,
    )

    score_rows.append(
        row
    )


score_summary = pd.DataFrame(
    score_rows
)


if not score_summary.empty:

    print(
        score_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# VolumeRatio20 閾値
#
# 継続上昇型の中で
# 出来高倍率を追加すると精度が上がるか確認
# ============================================================

print()
print("==============================")
print(" VOLUME RATIO THRESHOLD")
print("==============================")
print()


volume_thresholds = [
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    4.0,
    5.0,
]


volume_rows = []


for threshold in volume_thresholds:

    target = continuation[
        continuation[
            "VolumeRatio20"
        ] >= threshold
    ].copy()

    if target.empty:
        continue

    row = make_summary(
        f">={threshold}",
        target,
    )

    volume_rows.append(
        row
    )


volume_summary = pd.DataFrame(
    volume_rows
)


if not volume_summary.empty:

    print(
        volume_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 5日騰落率 閾値
#
# P5検出時点の勢いとの関係を見る
# ============================================================

print()
print("==============================")
print(" 5DAY CHANGE THRESHOLD")
print("==============================")
print()


change_thresholds = [
    0,
    5,
    10,
    15,
    20,
    30,
]


change_rows = []


for threshold in change_thresholds:

    target = continuation[
        continuation[
            CHANGE5_COL
        ] >= threshold
    ].copy()

    if target.empty:
        continue

    row = make_summary(
        f">={threshold}%",
        target,
    )

    change_rows.append(
        row
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
# Day1 閾値
#
# Day2 >= 3% を固定して
# Day1の強さを変える
# ============================================================

print()
print("==============================")
print(" DAY1 THRESHOLD / DAY2 >= 3")
print("==============================")
print()


day1_thresholds = [
    0,
    1,
    2,
    3,
    4,
    5,
]


day1_rows = []


for threshold in day1_thresholds:

    target = evaluation[
        (evaluation["Day1"] >= threshold)
        & (evaluation["Day2"] >= 3)
    ].copy()

    if target.empty:
        continue

    row = make_summary(
        f"Day1>={threshold}",
        target,
    )

    day1_rows.append(
        row
    )


day1_summary = pd.DataFrame(
    day1_rows
)


if not day1_summary.empty:

    print(
        day1_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day2 閾値
#
# Day1 >= 3% を固定して
# Day2の強さを変える
# ============================================================

print()
print("==============================")
print(" DAY2 THRESHOLD / DAY1 >= 3")
print("==============================")
print()


day2_thresholds = [
    0,
    1,
    2,
    3,
    4,
    5,
    7,
    10,
]


day2_rows = []


for threshold in day2_thresholds:

    target = evaluation[
        (evaluation["Day1"] >= 3)
        & (evaluation["Day2"] >= threshold)
    ].copy()

    if target.empty:
        continue

    row = make_summary(
        f"Day2>={threshold}",
        target,
    )

    day2_rows.append(
        row
    )


day2_summary = pd.DataFrame(
    day2_rows
)


if not day2_summary.empty:

    print(
        day2_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day1 x Day2 クロス
#
# 最適な境界が3%なのかを見る
# ============================================================

print()
print("==============================")
print(" DAY1 x DAY2 CROSS")
print("==============================")
print()


cross_rows = []


day1_cross = [
    1,
    2,
    3,
    4,
    5,
]


day2_cross = [
    1,
    2,
    3,
    4,
    5,
]


for day1_threshold in day1_cross:

    for day2_threshold in day2_cross:

        target = evaluation[
            (
                evaluation["Day1"]
                >= day1_threshold
            )
            & (
                evaluation["Day2"]
                >= day2_threshold
            )
        ].copy()

        if target.empty:
            continue

        cross_rows.append(
            {
                "Day1条件":
                    f">={day1_threshold}%",

                "Day2条件":
                    f">={day2_threshold}%",

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

                "VolumeRatio20中央値":
                    target[
                        "VolumeRatio20"
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


cross_summary = pd.DataFrame(
    cross_rows
)


if not cross_summary.empty:

    print(
        cross_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 継続上昇型 詳細
# ============================================================

print()
print("==============================")
print(" CONTINUATION DETAILS")
print("==============================")
print()


if not continuation.empty:

    display_columns = [
        DATE_COL,
        CODE_COL,
        NAME_COL,
        SCORE_COL,
        CHANGE5_COL,
        "VolumeRatio20",
        "Day1",
        "Day2",
        "day2_minus_day1",
        "Day3",
        "Day4",
        "Day5",
        "future_max",
        "future_min",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in continuation.columns
    ]

    print(
        continuation[
            display_columns
        ]
        .sort_values(
            [
                "Day1",
                "Day2",
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


# ============================================================
# 継続上昇型から外れた Day1 >= 3%
#
# Day1は強かったが
# Day2で継続しなかった銘柄を見る
# ============================================================

failed_continuation = evaluation[
    (evaluation["Day1"] >= 3)
    & (evaluation["Day2"] < 3)
].copy()


print()
print("==============================")
print(" DAY1 >= 3 BUT DAY2 < 3")
print("==============================")
print()

print(
    "件数 :",
    len(failed_continuation),
)


if not failed_continuation.empty:

    failed_summary = pd.DataFrame(
        [
            make_summary(
                "Day1>=3 / Day2<3",
                failed_continuation,
            )
        ]
    )

    print()

    print(
        failed_summary
        .round(2)
        .to_string(
            index=False
        )
    )

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
        "day2_minus_day1",
        "Day3",
        "Day4",
        "Day5",
        "future_max",
        "future_min",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in failed_continuation.columns
    ]

    print(
        failed_continuation[
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