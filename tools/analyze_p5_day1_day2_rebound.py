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

SCORE_COL = "初動スコア"
CHG5_COL = "5日騰落率"
CODE_COL = "コード"
NAME_COL = "銘柄名"
DATE_COL = "検出日"

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
# データ読み込み
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
    low_memory=False,
)


# ============================================================
# 数値化
# ============================================================

score = pd.to_numeric(
    df[SCORE_COL],
    errors="coerce",
)

chg5 = pd.to_numeric(
    df[CHG5_COL],
    errors="coerce",
)

vr20 = pd.to_numeric(
    df["VolumeRatio20"],
    errors="coerce",
)


# ============================================================
# 基本P5条件
#
# 初動スコア >= 3
# 5日騰落率 > 0
# VolumeRatio20 > 1
# ============================================================

base = (
    (score >= 3)
    & (chg5 > 0)
    & (vr20 > 1)
)


# ============================================================
# 回避条件
# ============================================================

avoid = pd.Series(
    False,
    index=df.index,
)

for col in AVOID_COLUMNS:

    if col not in df.columns:
        continue

    values = (
        df[col]
        .fillna(False)
        .astype(bool)
    )

    avoid |= values


# ============================================================
# 正式P5
# ============================================================

p5 = df[
    base & ~avoid
].copy()

print()
print("==============================")
print(" P5")
print("==============================")
print()

print(
    "基本P5候補 :",
    int(base.sum()),
)

print(
    "回避条件該当 :",
    int(
        (
            base
            & avoid
        ).sum()
    ),
)

print(
    "正式P5 :",
    len(p5),
)


# ============================================================
# Day1～Day5 数値化
# ============================================================

for col in DAY_COLS:

    p5[col] = pd.to_numeric(
        p5[col],
        errors="coerce",
    )


# ============================================================
# Day1～Day5 完備ケース
# ============================================================

x = p5.dropna(
    subset=DAY_COLS
).copy()

print(
    "Day1-Day5完備 :",
    len(x),
)


# ============================================================
# 5日以内の底
# ============================================================

x["bottom_value"] = (
    x[DAY_COLS]
    .min(axis=1)
)

x["bottom_day"] = (
    x[DAY_COLS]
    .idxmin(axis=1)
)


# ============================================================
# Day1が底だったケース
# ============================================================

day1_bottom = x[
    x["bottom_day"] == "Day1"
].copy()

print(
    "Day1が底 :",
    len(day1_bottom),
)


# ============================================================
# Day1 → Day2 反発幅
# ============================================================

day1_bottom["rebound_size"] = (
    day1_bottom["Day2"]
    - day1_bottom["Day1"]
)


# ============================================================
# Day2で5ポイント以上反発
# ============================================================

candidate = day1_bottom[
    day1_bottom["rebound_size"] >= 5
].copy()


# ============================================================
# 反発後の最大値
# ============================================================

candidate["post_rebound_max"] = (
    candidate[
        [
            "Day2",
            "Day3",
            "Day4",
            "Day5",
        ]
    ]
    .max(axis=1)
)


# ============================================================
# Day5プラス
# ============================================================

candidate["day5_positive"] = (
    candidate["Day5"] > 0
)


# ============================================================
# 5日以内 +5%以上
# ============================================================

candidate["hit_5pct"] = (
    candidate[DAY_COLS]
    .max(axis=1)
    >= 5
)


# ============================================================
# 5日以内 +10%以上
# ============================================================

candidate["hit_10pct"] = (
    candidate[DAY_COLS]
    .max(axis=1)
    >= 10
)


# ============================================================
# メイン結果
# ============================================================

print()
print("==============================")
print(" DAY1 BOTTOM -> DAY2 REBOUND 5+")
print("==============================")
print()

print(
    "count :",
    len(candidate),
)

print()


# ============================================================
# 明細
# ============================================================

cols = [
    DATE_COL,
    CODE_COL,
    NAME_COL,
    SCORE_COL,
    CHG5_COL,
    "VolumeRatio20",
    "Day1",
    "Day2",
    "Day3",
    "Day4",
    "Day5",
    "rebound_size",
    "post_rebound_max",
    "day5_positive",
    "hit_5pct",
    "hit_10pct",
]

if candidate.empty:

    print(
        "該当銘柄なし"
    )

else:

    print(
        candidate[
            cols
        ]
        .sort_values(
            "rebound_size",
            ascending=False,
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 全体成績
# ============================================================

print()
print("==============================")
print(" RESULT")
print("==============================")
print()

if candidate.empty:

    print(
        "集計対象なし"
    )

else:

    print(
        "件数 :",
        len(candidate),
    )

    print(
        "Day1中央値 :",
        round(
            candidate[
                "Day1"
            ].median(),
            2,
        ),
    )

    print(
        "Day2中央値 :",
        round(
            candidate[
                "Day2"
            ].median(),
            2,
        ),
    )

    print(
        "反発幅中央値 :",
        round(
            candidate[
                "rebound_size"
            ].median(),
            2,
        ),
    )

    print(
        "Day5中央値 :",
        round(
            candidate[
                "Day5"
            ].median(),
            2,
        ),
    )

    print(
        "Day5プラス率 :",
        round(
            candidate[
                "day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "5日内+5%以上率 :",
        round(
            candidate[
                "hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "5日内+10%以上率 :",
        round(
            candidate[
                "hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )


# ============================================================
# Day1押し目深度
# ============================================================

print()
print("==============================")
print(" DAY1 DEPTH")
print("==============================")
print()

bins = [
    -999,
    -10,
    -6,
    -4,
    -2,
    0,
]

labels = [
    "<-10",
    "-10~-6",
    "-6~-4",
    "-4~-2",
    "-2~0",
]

candidate["depth_group"] = pd.cut(
    candidate["Day1"],
    bins=bins,
    labels=labels,
    right=False,
)


# ============================================================
# 深度別集計
# ============================================================

if candidate.empty:

    print(
        "集計対象なし"
    )

else:

    depth = (
        candidate
        .groupby(
            "depth_group",
            observed=True,
        )
        .agg(
            count=(
                CODE_COL,
                "size",
            ),
            day1_median=(
                "Day1",
                "median",
            ),
            rebound_median=(
                "rebound_size",
                "median",
            ),
            day5_median=(
                "Day5",
                "median",
            ),
            day5_positive_rate=(
                "day5_positive",
                "mean",
            ),
            hit_5pct_rate=(
                "hit_5pct",
                "mean",
            ),
            hit_10pct_rate=(
                "hit_10pct",
                "mean",
            ),
        )
    )

    for col in [
        "day5_positive_rate",
        "hit_5pct_rate",
        "hit_10pct_rate",
    ]:

        depth[col] = (
            depth[col]
            * 100
        ).round(2)

    print(
        depth
        .round(2)
        .to_string()
    )