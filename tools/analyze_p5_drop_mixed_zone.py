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
# Day2エントリー基準
#
# Day1 / Day2 は検出時株価からの騰落率
#
# Day3_from_entry
#   Day2終値で買った場合のDay3収益
#
# Drop
#   Day2 - Day1
# ============================================================

evaluation["Drop"] = (
    evaluation["Day2"]
    - evaluation["Day1"]
)

for day in [3, 4, 5]:

    evaluation[f"Day{day}_from_entry"] = (
        (
            (1 + evaluation[f"Day{day}"] / 100)
            / (1 + evaluation["Day2"] / 100)
        )
        - 1
    ) * 100


evaluation["entry_future_max"] = evaluation[
    [
        "Day3_from_entry",
        "Day4_from_entry",
        "Day5_from_entry",
    ]
].max(axis=1)


evaluation["entry_future_min"] = evaluation[
    [
        "Day3_from_entry",
        "Day4_from_entry",
        "Day5_from_entry",
    ]
].min(axis=1)


# ============================================================
# 集計関数
# ============================================================

def summarize(label, data):

    count = len(data)

    if count == 0:

        return {
            "条件": label,
            "件数": 0,
        }

    return {
        "条件": label,
        "件数": count,

        "5日騰落率中央値":
            data[CHANGE5_COL].median(),

        "VolumeRatio20中央値":
            data["VolumeRatio20"].median(),

        "Day1中央値":
            data["Day1"].median(),

        "Day2中央値":
            data["Day2"].median(),

        "Drop中央値":
            data["Drop"].median(),

        "Day3実収益中央値":
            data["Day3_from_entry"].median(),

        "Day4実収益中央値":
            data["Day4_from_entry"].median(),

        "Day5実収益平均":
            data["Day5_from_entry"].mean(),

        "Day5実収益中央値":
            data["Day5_from_entry"].median(),

        "Day5勝率":
            (data["Day5_from_entry"] > 0).mean() * 100,

        "最大利益中央値":
            data["entry_future_max"].median(),

        "最大下落中央値":
            data["entry_future_min"].median(),

        "+3%到達率":
            (data["entry_future_max"] >= 3).mean() * 100,

        "+5%到達率":
            (data["entry_future_max"] >= 5).mean() * 100,

        "+10%到達率":
            (data["entry_future_max"] >= 10).mean() * 100,

        "-2%到達率":
            (data["entry_future_min"] <= -2).mean() * 100,

        "-3%到達率":
            (data["entry_future_min"] <= -3).mean() * 100,

        "-5%到達率":
            (data["entry_future_min"] <= -5).mean() * 100,
    }


def print_table(rows):

    table = pd.DataFrame(rows)

    numeric = table.select_dtypes(
        include=[np.number]
    ).columns

    table[numeric] = table[numeric].round(2)

    print(
        table.to_string(
            index=False
        )
    )


# ============================================================
# 混在ゾーン
# ============================================================

mixed = evaluation[
    (evaluation["Drop"] >= -5.0)
    & (evaluation["Drop"] < -3.5)
].copy()


print()
print("==============================")
print(" P5 DROP MIXED ZONE ANALYSIS")
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

print_table([
    summarize(
        "-5.0 <= Drop < -3.5",
        mixed,
    )
])


# ============================================================
# Day2位置
# ============================================================

print()
print("==============================")
print(" DAY2 POSITION")
print("==============================")
print()

day2_conditions = [
    (
        "Day2 >= 3",
        mixed["Day2"] >= 3,
    ),
    (
        "0 <= Day2 < 3",
        (mixed["Day2"] >= 0)
        & (mixed["Day2"] < 3),
    ),
    (
        "-3 <= Day2 < 0",
        (mixed["Day2"] >= -3)
        & (mixed["Day2"] < 0),
    ),
    (
        "-5 <= Day2 < -3",
        (mixed["Day2"] >= -5)
        & (mixed["Day2"] < -3),
    ),
    (
        "Day2 < -5",
        mixed["Day2"] < -5,
    ),
]

rows = []

for label, condition in day2_conditions:

    rows.append(
        summarize(
            label,
            mixed[condition],
        )
    )

print_table(rows)


# ============================================================
# 5日騰落率
# ============================================================

print()
print("==============================")
print(" 5DAY CHANGE")
print("==============================")
print()

change_conditions = [
    (
        "Change < 5",
        mixed[CHANGE5_COL] < 5,
    ),
    (
        "5 <= Change < 10",
        (mixed[CHANGE5_COL] >= 5)
        & (mixed[CHANGE5_COL] < 10),
    ),
    (
        "10 <= Change < 15",
        (mixed[CHANGE5_COL] >= 10)
        & (mixed[CHANGE5_COL] < 15),
    ),
    (
        "15 <= Change < 20",
        (mixed[CHANGE5_COL] >= 15)
        & (mixed[CHANGE5_COL] < 20),
    ),
    (
        "Change >= 20",
        mixed[CHANGE5_COL] >= 20,
    ),
]

rows = []

for label, condition in change_conditions:

    rows.append(
        summarize(
            label,
            mixed[condition],
        )
    )

print_table(rows)


# ============================================================
# VolumeRatio20
# ============================================================

print()
print("==============================")
print(" VOLUME RATIO 20")
print("==============================")
print()

volume_conditions = [
    (
        "1.0 < VR < 1.5",
        (mixed["VolumeRatio20"] > 1.0)
        & (mixed["VolumeRatio20"] < 1.5),
    ),
    (
        "1.5 <= VR < 2.0",
        (mixed["VolumeRatio20"] >= 1.5)
        & (mixed["VolumeRatio20"] < 2.0),
    ),
    (
        "2.0 <= VR < 3.0",
        (mixed["VolumeRatio20"] >= 2.0)
        & (mixed["VolumeRatio20"] < 3.0),
    ),
    (
        "VR >= 3.0",
        mixed["VolumeRatio20"] >= 3.0,
    ),
]

rows = []

for label, condition in volume_conditions:

    rows.append(
        summarize(
            label,
            mixed[condition],
        )
    )

print_table(rows)


# ============================================================
# Day2 × 5日騰落率
# ============================================================

print()
print("==============================")
print(" DAY2 x 5DAY CHANGE")
print("==============================")
print()

combined_conditions = [
    (
        "Day2>=-3 / Change<10",
        (mixed["Day2"] >= -3)
        & (mixed[CHANGE5_COL] < 10),
    ),
    (
        "Day2>=-3 / Change>=10",
        (mixed["Day2"] >= -3)
        & (mixed[CHANGE5_COL] >= 10),
    ),
    (
        "Day2<-3 / Change<10",
        (mixed["Day2"] < -3)
        & (mixed[CHANGE5_COL] < 10),
    ),
    (
        "Day2<-3 / Change>=10",
        (mixed["Day2"] < -3)
        & (mixed[CHANGE5_COL] >= 10),
    ),
]

rows = []

for label, condition in combined_conditions:

    rows.append(
        summarize(
            label,
            mixed[condition],
        )
    )

print_table(rows)


# ============================================================
# Day2 × VolumeRatio20
# ============================================================

print()
print("==============================")
print(" DAY2 x VOLUME")
print("==============================")
print()

combined_conditions = [
    (
        "Day2>=-3 / VR<2",
        (mixed["Day2"] >= -3)
        & (mixed["VolumeRatio20"] < 2),
    ),
    (
        "Day2>=-3 / VR>=2",
        (mixed["Day2"] >= -3)
        & (mixed["VolumeRatio20"] >= 2),
    ),
    (
        "Day2<-3 / VR<2",
        (mixed["Day2"] < -3)
        & (mixed["VolumeRatio20"] < 2),
    ),
    (
        "Day2<-3 / VR>=2",
        (mixed["Day2"] < -3)
        & (mixed["VolumeRatio20"] >= 2),
    ),
]

rows = []

for label, condition in combined_conditions:

    rows.append(
        summarize(
            label,
            mixed[condition],
        )
    )

print_table(rows)


# ============================================================
# 勝ち・負け比較
# ============================================================

print()
print("==============================")
print(" WINNER vs LOSER")
print("==============================")
print()

winner = mixed[
    mixed["Day5_from_entry"] > 0
]

loser = mixed[
    mixed["Day5_from_entry"] <= 0
]

print_table([
    summarize(
        "Day5 > 0",
        winner,
    ),
    summarize(
        "Day5 <= 0",
        loser,
    ),
])


# ============================================================
# +5%到達 vs -3%到達
# ============================================================

print()
print("==============================")
print(" +5% HIT vs -3% HIT")
print("==============================")
print()

plus5 = mixed[
    mixed["entry_future_max"] >= 5
]

minus3 = mixed[
    mixed["entry_future_min"] <= -3
]

print_table([
    summarize(
        "+5%到達",
        plus5,
    ),
    summarize(
        "-3%到達",
        minus3,
    ),
])


# ============================================================
# 全12件詳細
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

detail = mixed[
    detail_columns
].copy()

detail = detail.sort_values(
    "Day5_from_entry",
    ascending=False,
)

numeric = detail.select_dtypes(
    include=[np.number]
).columns

detail[numeric] = detail[numeric].round(2)

print(
    detail.to_string(
        index=False
    )
)


print()
print("==============================")
print(" DONE")
print("==============================")