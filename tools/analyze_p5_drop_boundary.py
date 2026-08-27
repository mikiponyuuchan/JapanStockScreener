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
# Day2買い基準
# ============================================================

evaluation["Drop"] = (
    evaluation["Day2"]
    - evaluation["Day1"]
)

evaluation["Day3_from_entry"] = (
    (1 + evaluation["Day3"] / 100)
    / (1 + evaluation["Day2"] / 100)
    - 1
) * 100

evaluation["Day4_from_entry"] = (
    (1 + evaluation["Day4"] / 100)
    / (1 + evaluation["Day2"] / 100)
    - 1
) * 100

evaluation["Day5_from_entry"] = (
    (1 + evaluation["Day5"] / 100)
    / (1 + evaluation["Day2"] / 100)
    - 1
) * 100


future_columns = [
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
]

evaluation["entry_future_max"] = (
    evaluation[future_columns]
    .max(axis=1)
)

evaluation["entry_future_min"] = (
    evaluation[future_columns]
    .min(axis=1)
)


# ============================================================
# 集計関数
# ============================================================

def summarize(data, condition):

    count = len(data)

    if count == 0:

        return {
            "条件": condition,
            "件数": 0,
            "5日騰落率中央値": np.nan,
            "VolumeRatio20中央値": np.nan,
            "Day1中央値": np.nan,
            "Day2中央値": np.nan,
            "Drop中央値": np.nan,
            "Day3実収益中央値": np.nan,
            "Day4実収益中央値": np.nan,
            "Day5実収益平均": np.nan,
            "Day5実収益中央値": np.nan,
            "Day5勝率": np.nan,
            "最大利益中央値": np.nan,
            "最大下落中央値": np.nan,
            "+3%到達率": np.nan,
            "+5%到達率": np.nan,
            "+10%到達率": np.nan,
            "-2%到達率": np.nan,
            "-3%到達率": np.nan,
            "-5%到達率": np.nan,
        }

    return {
        "条件": condition,
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
            data["Day5_from_entry"].gt(0).mean()
            * 100,
        "最大利益中央値":
            data["entry_future_max"].median(),
        "最大下落中央値":
            data["entry_future_min"].median(),
        "+3%到達率":
            data["entry_future_max"].ge(3).mean()
            * 100,
        "+5%到達率":
            data["entry_future_max"].ge(5).mean()
            * 100,
        "+10%到達率":
            data["entry_future_max"].ge(10).mean()
            * 100,
        "-2%到達率":
            data["entry_future_min"].le(-2).mean()
            * 100,
        "-3%到達率":
            data["entry_future_min"].le(-3).mean()
            * 100,
        "-5%到達率":
            data["entry_future_min"].le(-5).mean()
            * 100,
    }


# ============================================================
# 4つの境界帯
# ============================================================

ranges = [
    (
        "Drop >= -3.0pt",
        evaluation[
            evaluation["Drop"] >= -3.0
        ],
    ),
    (
        "-3.5 <= Drop < -3.0pt",
        evaluation[
            (evaluation["Drop"] >= -3.5)
            & (evaluation["Drop"] < -3.0)
        ],
    ),
    (
        "-5.0 <= Drop < -3.5pt",
        evaluation[
            (evaluation["Drop"] >= -5.0)
            & (evaluation["Drop"] < -3.5)
        ],
    ),
    (
        "Drop < -5.0pt",
        evaluation[
            evaluation["Drop"] < -5.0
        ],
    ),
]


# ============================================================
# 基本表示
# ============================================================

print()
print("==============================")
print(" P5 DROP BOUNDARY ANALYSIS")
print("==============================")
print()

print("全件数 :", len(df))
print("正式P5 :", len(p5))
print("Day1-Day5完備 :", len(evaluation))


# ============================================================
# 境界帯比較
# ============================================================

rows = []

for condition, data in ranges:

    rows.append(
        summarize(
            data,
            condition,
        )
    )


result = pd.DataFrame(rows)


print()
print("==============================")
print(" DROP RANGE COMPARISON")
print("==============================")
print()

print(
    result.round(2).to_string(
        index=False
    )
)


# ============================================================
# -3.5 ～ -3.0pt の個別確認
# ============================================================

boundary = evaluation[
    (evaluation["Drop"] >= -3.5)
    & (evaluation["Drop"] < -3.0)
].copy()

boundary = boundary.sort_values(
    "Drop",
    ascending=False,
)


print()
print("==============================")
print(" BOUNDARY DETAILS")
print(" -3.5 <= Drop < -3.0pt")
print("==============================")
print()

print("件数 :", len(boundary))
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
    if column in boundary.columns
]

if len(boundary) > 0:

    print(
        boundary[
            detail_columns
        ].round(2).to_string(
            index=False
        )
    )


# ============================================================
# -3.5境界の直上も確認
#
# -3.0以上のうち、
# -3.0 ～ -2.5 の銘柄を見る
# ============================================================

upper_boundary = evaluation[
    (evaluation["Drop"] >= -3.0)
    & (evaluation["Drop"] < -2.5)
].copy()

upper_boundary = upper_boundary.sort_values(
    "Drop",
    ascending=True,
)


print()
print("==============================")
print(" UPPER BOUNDARY DETAILS")
print(" -3.0 <= Drop < -2.5pt")
print("==============================")
print()

print("件数 :", len(upper_boundary))
print()

if len(upper_boundary) > 0:

    print(
        upper_boundary[
            [
                column
                for column in detail_columns
                if column in upper_boundary.columns
            ]
        ].round(2).to_string(
            index=False
        )
    )


# ============================================================
# -3.5未満の直下
#
# -4.0 ～ -3.5 の銘柄を見る
# ============================================================

lower_boundary = evaluation[
    (evaluation["Drop"] >= -4.0)
    & (evaluation["Drop"] < -3.5)
].copy()

lower_boundary = lower_boundary.sort_values(
    "Drop",
    ascending=False,
)


print()
print("==============================")
print(" LOWER BOUNDARY DETAILS")
print(" -4.0 <= Drop < -3.5pt")
print("==============================")
print()

print("件数 :", len(lower_boundary))
print()

if len(lower_boundary) > 0:

    print(
        lower_boundary[
            [
                column
                for column in detail_columns
                if column in lower_boundary.columns
            ]
        ].round(2).to_string(
            index=False
        )
    )


# ============================================================
# 境界周辺まとめ
# ============================================================

near_boundary_ranges = [
    (
        "-4.0 <= Drop < -3.5",
        lower_boundary,
    ),
    (
        "-3.5 <= Drop < -3.0",
        boundary,
    ),
    (
        "-3.0 <= Drop < -2.5",
        upper_boundary,
    ),
]

near_rows = []

for condition, data in near_boundary_ranges:

    near_rows.append(
        summarize(
            data,
            condition,
        )
    )


near_result = pd.DataFrame(
    near_rows
)


print()
print("==============================")
print(" NEAR BOUNDARY COMPARISON")
print("==============================")
print()

print(
    near_result.round(2).to_string(
        index=False
    )
)


print()
print("==============================")
print(" DONE")
print("==============================")