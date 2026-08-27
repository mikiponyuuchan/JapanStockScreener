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
#
# Day3以降をDay2購入時点からの実収益に変換
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

def summarize(data, label):

    count = len(data)

    if count == 0:

        return {
            "条件": label,
            "件数": 0,
        }

    day5 = data["Day5_from_entry"]
    future_max = data["entry_future_max"]
    future_min = data["entry_future_min"]

    return {
        "条件": label,
        "件数": count,
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


def print_summary(title, groups):

    print()
    print("==============================")
    print(title)
    print("==============================")
    print()

    rows = []

    for label, mask in groups:

        rows.append(
            summarize(
                mixed[mask],
                label,
            )
        )

    result = pd.DataFrame(rows)

    print(
        result.to_string(
            index=False,
        )
    )


# ============================================================
# 混在ゾーン
# ============================================================

mixed = evaluation[
    (evaluation["Drop"] >= -5.0)
    & (evaluation["Drop"] < -3.5)
].copy()


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 OVERHEAT x VOLUME")
print("==============================")
print()

print("全件数 :", len(df))
print("正式P5 :", len(p5))
print("Day1-Day5完備 :", len(evaluation))
print("混在ゾーン :", len(mixed))


# ============================================================
# BASELINE
# ============================================================

print()
print("==============================")
print(" MIXED ZONE BASELINE")
print(" -5.0 <= Drop < -3.5")
print("==============================")
print()

baseline = pd.DataFrame(
    [
        summarize(
            mixed,
            "-5.0 <= Drop < -3.5",
        )
    ]
)

print(
    baseline.to_string(
        index=False,
    )
)


# ============================================================
# 5日騰落率 閾値
# ============================================================

change_thresholds = [
    5,
    10,
    15,
    20,
    25,
    30,
]


change_groups = []

for threshold in change_thresholds:

    change_groups.append(
        (
            f"Change < {threshold}",
            mixed[CHANGE5_COL] < threshold,
        )
    )

print_summary(
    "5DAY CHANGE THRESHOLD",
    change_groups,
)


# ============================================================
# 過熱側だけを見る
# ============================================================

overheat_groups = []

for threshold in [
    10,
    15,
    20,
    25,
    30,
]:

    overheat_groups.append(
        (
            f"Change >= {threshold}",
            mixed[CHANGE5_COL] >= threshold,
        )
    )

print_summary(
    "OVERHEAT SIDE",
    overheat_groups,
)


# ============================================================
# VolumeRatio20 閾値
# ============================================================

volume_groups = []

for threshold in [
    1.5,
    2.0,
    2.5,
    3.0,
    4.0,
    5.0,
]:

    volume_groups.append(
        (
            f"VR < {threshold}",
            mixed["VolumeRatio20"] < threshold,
        )
    )

print_summary(
    "VOLUME THRESHOLD",
    volume_groups,
)


# ============================================================
# 出来高急増側
# ============================================================

high_volume_groups = []

for threshold in [
    1.5,
    2.0,
    2.5,
    3.0,
    4.0,
    5.0,
]:

    high_volume_groups.append(
        (
            f"VR >= {threshold}",
            mixed["VolumeRatio20"] >= threshold,
        )
    )

print_summary(
    "HIGH VOLUME SIDE",
    high_volume_groups,
)


# ============================================================
# 5日騰落率 × Volume
#
# ここが今回の中心
# ============================================================

combo_groups = [
    (
        "Change<15 / VR<2",
        (mixed[CHANGE5_COL] < 15)
        & (mixed["VolumeRatio20"] < 2),
    ),
    (
        "Change<15 / VR>=2",
        (mixed[CHANGE5_COL] < 15)
        & (mixed["VolumeRatio20"] >= 2),
    ),
    (
        "Change>=15 / VR<2",
        (mixed[CHANGE5_COL] >= 15)
        & (mixed["VolumeRatio20"] < 2),
    ),
    (
        "Change>=15 / VR>=2",
        (mixed[CHANGE5_COL] >= 15)
        & (mixed["VolumeRatio20"] >= 2),
    ),
    (
        "Change<20 / VR<2",
        (mixed[CHANGE5_COL] < 20)
        & (mixed["VolumeRatio20"] < 2),
    ),
    (
        "Change<20 / VR>=2",
        (mixed[CHANGE5_COL] < 20)
        & (mixed["VolumeRatio20"] >= 2),
    ),
    (
        "Change>=20 / VR<2",
        (mixed[CHANGE5_COL] >= 20)
        & (mixed["VolumeRatio20"] < 2),
    ),
    (
        "Change>=20 / VR>=2",
        (mixed[CHANGE5_COL] >= 20)
        & (mixed["VolumeRatio20"] >= 2),
    ),
    (
        "Change<20 / VR<3",
        (mixed[CHANGE5_COL] < 20)
        & (mixed["VolumeRatio20"] < 3),
    ),
    (
        "Change<20 / VR>=3",
        (mixed[CHANGE5_COL] < 20)
        & (mixed["VolumeRatio20"] >= 3),
    ),
    (
        "Change>=20 / VR<3",
        (mixed[CHANGE5_COL] >= 20)
        & (mixed["VolumeRatio20"] < 3),
    ),
    (
        "Change>=20 / VR>=3",
        (mixed[CHANGE5_COL] >= 20)
        & (mixed["VolumeRatio20"] >= 3),
    ),
]

print_summary(
    "5DAY CHANGE x VOLUME",
    combo_groups,
)


# ============================================================
# 危険候補
#
# 前回結果から特に確認したい組み合わせ
# ============================================================

danger_groups = [
    (
        "Change>=20",
        mixed[CHANGE5_COL] >= 20,
    ),
    (
        "VR>=3",
        mixed["VolumeRatio20"] >= 3,
    ),
    (
        "Change>=20 OR VR>=3",
        (mixed[CHANGE5_COL] >= 20)
        | (mixed["VolumeRatio20"] >= 3),
    ),
    (
        "Change>=20 AND VR>=3",
        (mixed[CHANGE5_COL] >= 20)
        & (mixed["VolumeRatio20"] >= 3),
    ),
    (
        "Change<20 AND VR<3",
        (mixed[CHANGE5_COL] < 20)
        & (mixed["VolumeRatio20"] < 3),
    ),
]

print_summary(
    "DANGER RULE CANDIDATES",
    danger_groups,
)


# ============================================================
# 危険候補を除外した残存側
# ============================================================

survivor_groups = [
    (
        "Keep : Change<20",
        mixed[CHANGE5_COL] < 20,
    ),
    (
        "Keep : VR<3",
        mixed["VolumeRatio20"] < 3,
    ),
    (
        "Keep : Change<20 AND VR<3",
        (mixed[CHANGE5_COL] < 20)
        & (mixed["VolumeRatio20"] < 3),
    ),
    (
        "Keep : Change<15 AND VR<3",
        (mixed[CHANGE5_COL] < 15)
        & (mixed["VolumeRatio20"] < 3),
    ),
    (
        "Keep : Change<20 AND VR<2",
        (mixed[CHANGE5_COL] < 20)
        & (mixed["VolumeRatio20"] < 2),
    ),
]

print_summary(
    "SURVIVOR CANDIDATES",
    survivor_groups,
)


# ============================================================
# 個別一覧
# ============================================================

print()
print("==============================")
print(" MIXED ZONE DETAILS")
print("==============================")
print()

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
    if column in mixed.columns
]

details = mixed[
    detail_columns
].copy()

details = details.sort_values(
    [
        CHANGE5_COL,
        "VolumeRatio20",
    ],
    ascending=[
        False,
        False,
    ],
)

print(
    details.to_string(
        index=False,
    )
)


# ============================================================
# 危険候補個別
# ============================================================

danger = mixed[
    (mixed[CHANGE5_COL] >= 20)
    | (mixed["VolumeRatio20"] >= 3)
].copy()


print()
print("==============================")
print(" DANGER CANDIDATE DETAILS")
print(" Change >= 20 OR VR >= 3")
print("==============================")
print()

print("件数 :", len(danger))
print()

if len(danger) > 0:

    danger_details = danger[
        detail_columns
    ].sort_values(
        [
            CHANGE5_COL,
            "VolumeRatio20",
        ],
        ascending=[
            False,
            False,
        ],
    )

    print(
        danger_details.to_string(
            index=False,
        )
    )


print()
print("==============================")
print(" DONE")
print("==============================")