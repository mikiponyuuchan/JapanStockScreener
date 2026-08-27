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
# Day2 買い後の実収益
#
# Day2終値で買ったと仮定
# ============================================================

for day in [3, 4, 5]:

    evaluation[f"Day{day}_from_entry"] = (
        (
            1 + evaluation[f"Day{day}"] / 100
        )
        /
        (
            1 + evaluation["Day2"] / 100
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


evaluation["Day2_minus_Day1"] = (
    evaluation["Day2"]
    - evaluation["Day1"]
)


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

        "Day1中央値":
            data["Day1"].median(),

        "Day2中央値":
            data["Day2"].median(),

        "Day2-Day1中央値":
            data["Day2_minus_Day1"].median(),

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

    numeric_cols = table.select_dtypes(
        include="number"
    ).columns

    table[numeric_cols] = table[
        numeric_cols
    ].round(2)

    print(
        table.to_string(
            index=False
        )
    )


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 EXCLUSION RULE TEST")
print("==============================")
print()

print("全件数 :", len(df))
print("正式P5 :", len(p5))
print("Day1-Day5完備 :", len(evaluation))


# ============================================================
# BASELINE
# ============================================================

print()
print("==============================")
print(" BASELINE")
print("==============================")
print()

print_table([
    summarize(
        "除外なし",
        evaluation,
    )
])


# ============================================================
# 単独除外ルール
# ============================================================

single_rules = {

    "失速<-3ptを除外":
        evaluation["Day2_minus_Day1"] >= -3,

    "失速<-5ptを除外":
        evaluation["Day2_minus_Day1"] >= -5,

    "Day2<-3%を除外":
        evaluation["Day2"] >= -3,

    "Day2<-5%を除外":
        evaluation["Day2"] >= -5,

    "5日騰落率>=15%を除外":
        evaluation[CHANGE5_COL] < 15,

    "5日騰落率>=20%を除外":
        evaluation[CHANGE5_COL] < 20,
}


print()
print("==============================")
print(" SINGLE EXCLUSION RULE")
print("==============================")
print()

rows = []

for label, keep_mask in single_rules.items():

    rows.append(
        summarize(
            label,
            evaluation[keep_mask],
        )
    )

print_table(rows)


# ============================================================
# 複合危険条件
#
# 条件に該当する銘柄だけ除外する
# ============================================================

danger_rules = {

    "過熱15% + 失速-3pt":
        (
            (evaluation[CHANGE5_COL] >= 15)
            & (
                evaluation["Day2_minus_Day1"]
                <= -3
            )
        ),

    "過熱20% + 失速-3pt":
        (
            (evaluation[CHANGE5_COL] >= 20)
            & (
                evaluation["Day2_minus_Day1"]
                <= -3
            )
        ),

    "過熱15% + Day2<-3":
        (
            (evaluation[CHANGE5_COL] >= 15)
            & (evaluation["Day2"] < -3)
        ),

    "過熱20% + Day2<-3":
        (
            (evaluation[CHANGE5_COL] >= 20)
            & (evaluation["Day2"] < -3)
        ),

    "失速-3pt + Day2<-3":
        (
            (
                evaluation["Day2_minus_Day1"]
                <= -3
            )
            & (evaluation["Day2"] < -3)
        ),

    "過熱15% + 失速-3pt + Day2<-3":
        (
            (evaluation[CHANGE5_COL] >= 15)
            & (
                evaluation["Day2_minus_Day1"]
                <= -3
            )
            & (evaluation["Day2"] < -3)
        ),

    "過熱20% + 失速-3pt + Day2<-3":
        (
            (evaluation[CHANGE5_COL] >= 20)
            & (
                evaluation["Day2_minus_Day1"]
                <= -3
            )
            & (evaluation["Day2"] < -3)
        ),
}


print()
print("==============================")
print(" COMBINED DANGER EXCLUSION")
print("==============================")
print()

rows = []

for label, danger_mask in danger_rules.items():

    kept = evaluation[
        ~danger_mask
    ]

    rows.append(
        summarize(
            label + " を除外",
            kept,
        )
    )

print_table(rows)


# ============================================================
# 除外された側の成績
#
# 本当に危険群なのか確認
# ============================================================

print()
print("==============================")
print(" EXCLUDED GROUP PERFORMANCE")
print("==============================")
print()

rows = []

for label, danger_mask in danger_rules.items():

    excluded = evaluation[
        danger_mask
    ]

    rows.append(
        summarize(
            label,
            excluded,
        )
    )

print_table(rows)


# ============================================================
# 失速幅 × 過熱度
# ============================================================

print()
print("==============================")
print(" DECELERATION x OVERHEAT")
print("==============================")
print()

test_rules = {

    "Change<15 / Drop>=-3":
        (
            (evaluation[CHANGE5_COL] < 15)
            & (
                evaluation["Day2_minus_Day1"]
                >= -3
            )
        ),

    "Change<20 / Drop>=-3":
        (
            (evaluation[CHANGE5_COL] < 20)
            & (
                evaluation["Day2_minus_Day1"]
                >= -3
            )
        ),

    "Change<15 / Drop>=-5":
        (
            (evaluation[CHANGE5_COL] < 15)
            & (
                evaluation["Day2_minus_Day1"]
                >= -5
            )
        ),

    "Change<20 / Drop>=-5":
        (
            (evaluation[CHANGE5_COL] < 20)
            & (
                evaluation["Day2_minus_Day1"]
                >= -5
            )
        ),

    "Change<15 / Day2>=-3":
        (
            (evaluation[CHANGE5_COL] < 15)
            & (evaluation["Day2"] >= -3)
        ),

    "Change<20 / Day2>=-3":
        (
            (evaluation[CHANGE5_COL] < 20)
            & (evaluation["Day2"] >= -3)
        ),
}


rows = []

for label, keep_mask in test_rules.items():

    rows.append(
        summarize(
            label,
            evaluation[keep_mask],
        )
    )

print_table(rows)


# ============================================================
# バランス候補
#
# 過度に件数を減らさず、
# 深い失速・深い崩れを避ける
# ============================================================

balanced_rules = {

    "B1 Drop>=-3":
        (
            evaluation["Day2_minus_Day1"]
            >= -3
        ),

    "B2 Drop>=-3 / Day2>=-3":
        (
            (
                evaluation["Day2_minus_Day1"]
                >= -3
            )
            & (evaluation["Day2"] >= -3)
        ),

    "B3 Drop>=-3 / Change<20":
        (
            (
                evaluation["Day2_minus_Day1"]
                >= -3
            )
            & (
                evaluation[CHANGE5_COL]
                < 20
            )
        ),

    "B4 Drop>=-3 / Day2>=-3 / Change<20":
        (
            (
                evaluation["Day2_minus_Day1"]
                >= -3
            )
            & (evaluation["Day2"] >= -3)
            & (
                evaluation[CHANGE5_COL]
                < 20
            )
        ),

    "B5 Drop>=-1":
        (
            evaluation["Day2_minus_Day1"]
            >= -1
        ),

    "B6 Drop>=-1 / Change<20":
        (
            (
                evaluation["Day2_minus_Day1"]
                >= -1
            )
            & (
                evaluation[CHANGE5_COL]
                < 20
            )
        ),
}


print()
print("==============================")
print(" BALANCED FINAL CANDIDATES")
print("==============================")
print()

rows = []

for label, keep_mask in balanced_rules.items():

    rows.append(
        summarize(
            label,
            evaluation[keep_mask],
        )
    )

print_table(rows)


# ============================================================
# B候補の件数維持率
# ============================================================

print()
print("==============================")
print(" RETENTION RATE")
print("==============================")
print()

for label, keep_mask in balanced_rules.items():

    count = int(
        keep_mask.sum()
    )

    rate = (
        count
        / len(evaluation)
        * 100
    )

    print(
        f"{label} : "
        f"{count}件 / "
        f"{rate:.2f}%"
    )


# ============================================================
# 完了
# ============================================================

print()
print("==============================")
print(" DONE")
print("==============================")