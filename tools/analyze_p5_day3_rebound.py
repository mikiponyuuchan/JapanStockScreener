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
# 集計関数
# ============================================================

def summarize(data, label):

    if data.empty:
        return {
            "条件": label,
            "件数": 0,
        }

    return {
        "条件": label,
        "件数": len(data),

        "Day2中央値":
            round(data["Day2"].median(), 2),

        "Day3中央値":
            round(data["Day3"].median(), 2),

        "Day2→Day3反発中央値":
            round(data["Day3_rebound"].median(), 2),

        "Day4実収益中央値":
            round(data["Day4_from_Day3"].median(), 2),

        "Day5実収益中央値":
            round(data["Day5_from_Day3"].median(), 2),

        "Day5勝率":
            round(
                (data["Day5_from_Day3"] > 0).mean() * 100,
                2,
            ),

        "最大利益中央値":
            round(data["future_max"].median(), 2),

        "最大下落中央値":
            round(data["future_min"].median(), 2),

        "+3%到達率":
            round(
                (data["future_max"] >= 3).mean() * 100,
                2,
            ),

        "+5%到達率":
            round(
                (data["future_max"] >= 5).mean() * 100,
                2,
            ),

        "+10%到達率":
            round(
                (data["future_max"] >= 10).mean() * 100,
                2,
            ),

        "-2%到達率":
            round(
                (data["future_min"] <= -2).mean() * 100,
                2,
            ),

        "-3%到達率":
            round(
                (data["future_min"] <= -3).mean() * 100,
                2,
            ),

        "-5%到達率":
            round(
                (data["future_min"] <= -5).mean() * 100,
                2,
            ),
    }


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
# これまでのP5検証と完全に同じ定義
#
# 初動スコア 3～4
# 5日騰落率 > 0
# VolumeRatio20 > 1
#
# 除外:
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
# Day2 → Day3 の実際の反発率
#
# Day1～Day5は検出日終値基準の累積騰落率。
# したがって単純な差ではなく、
# Day2終値 → Day3終値の実収益率を計算する。
# ============================================================

evaluation["Day3_rebound"] = (
    (
        (1 + evaluation["Day3"] / 100)
        / (1 + evaluation["Day2"] / 100)
    )
    - 1
) * 100


# ============================================================
# Day3終値で買った場合の実収益
#
# Day3までを買い条件に使用するため、
# 評価対象はDay4・Day5だけ。
# ============================================================

evaluation["Day4_from_Day3"] = (
    (
        (1 + evaluation["Day4"] / 100)
        / (1 + evaluation["Day3"] / 100)
    )
    - 1
) * 100


evaluation["Day5_from_Day3"] = (
    (
        (1 + evaluation["Day5"] / 100)
        / (1 + evaluation["Day3"] / 100)
    )
    - 1
) * 100


evaluation["future_max"] = evaluation[
    [
        "Day4_from_Day3",
        "Day5_from_Day3",
    ]
].max(axis=1)


evaluation["future_min"] = evaluation[
    [
        "Day4_from_Day3",
        "Day5_from_Day3",
    ]
].min(axis=1)


# ============================================================
# 基本表示
# ============================================================

print()
print("==============================")
print(" P5 DAY3 REBOUND ANALYSIS")
print("==============================")
print()

print("全件数 :", len(df))
print("正式P5 :", len(p5))
print("Day1-Day5完備 :", len(evaluation))


# ============================================================
# Day2マイナス
# ============================================================

day2_negative = evaluation[
    evaluation["Day2"] < 0
].copy()


print("Day2マイナス :", len(day2_negative))


# ============================================================
# DAY2 DROP PROFILE
# ============================================================

print()
print("==============================")
print(" DAY2 DROP PROFILE")
print("==============================")
print()

rows = []

conditions = [
    ("Day2 < 0", day2_negative["Day2"] < 0),
    ("Day2 <= -1", day2_negative["Day2"] <= -1),
    ("Day2 <= -2", day2_negative["Day2"] <= -2),
    ("Day2 <= -3", day2_negative["Day2"] <= -3),
    ("Day2 <= -5", day2_negative["Day2"] <= -5),
    ("Day2 <= -10", day2_negative["Day2"] <= -10),
]

for label, mask in conditions:

    temp = day2_negative[mask].copy()

    rows.append(
        summarize(temp, label)
    )


print(
    pd.DataFrame(rows).to_string(index=False)
)


# ============================================================
# DAY3 REBOUND THRESHOLD
# Day2 < 0
# ============================================================

print()
print("==============================")
print(" DAY3 REBOUND THRESHOLD")
print(" DAY2 < 0")
print("==============================")
print()

rows = []

for threshold in [0, 1, 2, 3, 5, 7, 10]:

    temp = day2_negative[
        day2_negative["Day3_rebound"] >= threshold
    ].copy()

    rows.append(
        summarize(
            temp,
            f"Rebound >= {threshold}%",
        )
    )


print(
    pd.DataFrame(rows).to_string(index=False)
)


# ============================================================
# DAY2 <= -3 × DAY3 REBOUND
# ============================================================

print()
print("==============================")
print(" DAY2 <= -3 x DAY3 REBOUND")
print("==============================")
print()

deep3 = evaluation[
    evaluation["Day2"] <= -3
].copy()

rows = []

for threshold in [0, 1, 2, 3, 5, 7, 10]:

    temp = deep3[
        deep3["Day3_rebound"] >= threshold
    ].copy()

    rows.append(
        summarize(
            temp,
            f"Rebound >= {threshold}%",
        )
    )


print(
    pd.DataFrame(rows).to_string(index=False)
)


# ============================================================
# DAY2 <= -5 × DAY3 REBOUND
# ============================================================

print()
print("==============================")
print(" DAY2 <= -5 x DAY3 REBOUND")
print("==============================")
print()

deep5 = evaluation[
    evaluation["Day2"] <= -5
].copy()

rows = []

for threshold in [0, 1, 2, 3, 5, 7, 10]:

    temp = deep5[
        deep5["Day3_rebound"] >= threshold
    ].copy()

    rows.append(
        summarize(
            temp,
            f"Rebound >= {threshold}%",
        )
    )


print(
    pd.DataFrame(rows).to_string(index=False)
)


# ============================================================
# Day3の絶対位置
#
# Day2でマイナスだった銘柄が、
# Day3時点で検出日終値に対して
# どこまで戻ったかを見る。
# ============================================================

print()
print("==============================")
print(" DAY3 POSITION")
print(" DAY2 < 0")
print("==============================")
print()

position_conditions = [
    (
        "Day3 < -5",
        day2_negative["Day3"] < -5,
    ),
    (
        "-5 <= Day3 < -3",
        (day2_negative["Day3"] >= -5)
        & (day2_negative["Day3"] < -3),
    ),
    (
        "-3 <= Day3 < 0",
        (day2_negative["Day3"] >= -3)
        & (day2_negative["Day3"] < 0),
    ),
    (
        "0 <= Day3 < 3",
        (day2_negative["Day3"] >= 0)
        & (day2_negative["Day3"] < 3),
    ),
    (
        "Day3 >= 3",
        day2_negative["Day3"] >= 3,
    ),
]

rows = []

for label, mask in position_conditions:

    temp = day2_negative[mask].copy()

    rows.append(
        summarize(temp, label)
    )


print(
    pd.DataFrame(rows).to_string(index=False)
)


# ============================================================
# 反発幅 × Day3絶対位置
# ============================================================

print()
print("==============================")
print(" REBOUND x DAY3 POSITION")
print(" DAY2 < 0")
print("==============================")
print()

cross_conditions = [
    (
        "Rebound>=1 / Day3<0",
        (day2_negative["Day3_rebound"] >= 1)
        & (day2_negative["Day3"] < 0),
    ),
    (
        "Rebound>=2 / Day3<0",
        (day2_negative["Day3_rebound"] >= 2)
        & (day2_negative["Day3"] < 0),
    ),
    (
        "Rebound>=3 / Day3<0",
        (day2_negative["Day3_rebound"] >= 3)
        & (day2_negative["Day3"] < 0),
    ),
    (
        "Rebound>=5 / Day3<0",
        (day2_negative["Day3_rebound"] >= 5)
        & (day2_negative["Day3"] < 0),
    ),
    (
        "Rebound>=1 / Day3>=0",
        (day2_negative["Day3_rebound"] >= 1)
        & (day2_negative["Day3"] >= 0),
    ),
    (
        "Rebound>=2 / Day3>=0",
        (day2_negative["Day3_rebound"] >= 2)
        & (day2_negative["Day3"] >= 0),
    ),
    (
        "Rebound>=3 / Day3>=0",
        (day2_negative["Day3_rebound"] >= 3)
        & (day2_negative["Day3"] >= 0),
    ),
    (
        "Rebound>=5 / Day3>=0",
        (day2_negative["Day3_rebound"] >= 5)
        & (day2_negative["Day3"] >= 0),
    ),
    (
        "Rebound>=3 / Day3>=3",
        (day2_negative["Day3_rebound"] >= 3)
        & (day2_negative["Day3"] >= 3),
    ),
    (
        "Rebound>=5 / Day3>=3",
        (day2_negative["Day3_rebound"] >= 5)
        & (day2_negative["Day3"] >= 3),
    ),
]

rows = []

for label, mask in cross_conditions:

    temp = day2_negative[mask].copy()

    rows.append(
        summarize(temp, label)
    )


print(
    pd.DataFrame(rows).to_string(index=False)
)


# ============================================================
# 深押し → Day3反発
#
# 今回の本命
# ============================================================

print()
print("==============================")
print(" DEEP PULLBACK REBOUND")
print("==============================")
print()

deep_conditions = [
    (
        "Day2<=-3 / rebound>=2",
        (evaluation["Day2"] <= -3)
        & (evaluation["Day3_rebound"] >= 2),
    ),
    (
        "Day2<=-3 / rebound>=3",
        (evaluation["Day2"] <= -3)
        & (evaluation["Day3_rebound"] >= 3),
    ),
    (
        "Day2<=-3 / rebound>=5",
        (evaluation["Day2"] <= -3)
        & (evaluation["Day3_rebound"] >= 5),
    ),
    (
        "Day2<=-5 / rebound>=2",
        (evaluation["Day2"] <= -5)
        & (evaluation["Day3_rebound"] >= 2),
    ),
    (
        "Day2<=-5 / rebound>=3",
        (evaluation["Day2"] <= -5)
        & (evaluation["Day3_rebound"] >= 3),
    ),
    (
        "Day2<=-5 / rebound>=5",
        (evaluation["Day2"] <= -5)
        & (evaluation["Day3_rebound"] >= 5),
    ),
    (
        "Day2<=-10 / rebound>=3",
        (evaluation["Day2"] <= -10)
        & (evaluation["Day3_rebound"] >= 3),
    ),
    (
        "Day2<=-10 / rebound>=5",
        (evaluation["Day2"] <= -10)
        & (evaluation["Day3_rebound"] >= 5),
    ),
]

rows = []

for label, mask in deep_conditions:

    temp = evaluation[mask].copy()

    rows.append(
        summarize(temp, label)
    )


print(
    pd.DataFrame(rows).to_string(index=False)
)


# ============================================================
# TARGET DETAILS
#
# Day2 <= -3%
# Day2 → Day3 実反発率 >= 3%
# ============================================================

target = evaluation[
    (evaluation["Day2"] <= -3)
    & (evaluation["Day3_rebound"] >= 3)
].copy()


target = target.sort_values(
    "Day3_rebound",
    ascending=False,
)


print()
print("==============================")
print(" TARGET DETAILS")
print(" DAY2 <= -3")
print(" DAY3 REBOUND >= 3%")
print("==============================")
print()

print("件数 :", len(target))
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
    "Day3",
    "Day3_rebound",
    "Day4",
    "Day5",
    "Day4_from_Day3",
    "Day5_from_Day3",
    "future_max",
    "future_min",
]


detail = target[
    [
        column
        for column in detail_columns
        if column in target.columns
    ]
].copy()


detail = detail.rename(
    columns={
        "Day3_rebound": "Day2→Day3反発",
        "Day4_from_Day3": "Day4実収益",
        "Day5_from_Day3": "Day5実収益",
        "future_max": "最大利益",
        "future_min": "最大下落",
    }
)


numeric_detail_columns = detail.select_dtypes(
    include=[np.number]
).columns


detail[numeric_detail_columns] = detail[
    numeric_detail_columns
].round(2)


print(
    detail.to_string(index=False)
)