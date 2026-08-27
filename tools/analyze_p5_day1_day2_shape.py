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
# 初動スコア 3～4
# 5日騰落率 > 0
# VolumeRatio20 > 1
# 回避条件を除外
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

complete = p5.dropna(
    subset=[
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
    ]
).copy()


# ============================================================
# 今回の中心
#
# 強い継続候補
#
# Day1 >= 4%
# Day2 >= 4%
# ============================================================

strong = complete[
    (complete["Day1"] >= 4)
    & (complete["Day2"] >= 4)
].copy()


# ============================================================
# Day1 -> Day2 の変化
#
# 単純なポイント差
# 例:
# Day1 +10%
# Day2 +7%
# -> -3pt
# ============================================================

strong["Day2_minus_Day1"] = (
    strong["Day2"]
    - strong["Day1"]
)


# ============================================================
# Day2終値買い後の実収益
# ============================================================

def return_from_entry(
    entry_return,
    future_return,
):

    return (
        (
            (1 + future_return / 100)
            /
            (1 + entry_return / 100)
        )
        - 1
    ) * 100


strong["Day3_from_entry"] = return_from_entry(
    strong["Day2"],
    strong["Day3"],
)

strong["Day4_from_entry"] = return_from_entry(
    strong["Day2"],
    strong["Day4"],
)

strong["Day5_from_entry"] = return_from_entry(
    strong["Day2"],
    strong["Day5"],
)


# ============================================================
# Day2買い後の最大・最小
# ============================================================

future_columns = [
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
]


strong["entry_future_max"] = (
    strong[
        future_columns
    ]
    .max(axis=1)
)


strong["entry_future_min"] = (
    strong[
        future_columns
    ]
    .min(axis=1)
)


# ============================================================
# 到達判定
# ============================================================

strong["day5_win"] = (
    strong["Day5_from_entry"] > 0
)

strong["hit_plus3"] = (
    strong["entry_future_max"] >= 3
)

strong["hit_plus5"] = (
    strong["entry_future_max"] >= 5
)

strong["hit_plus10"] = (
    strong["entry_future_max"] >= 10
)

strong["hit_minus2"] = (
    strong["entry_future_min"] <= -2
)

strong["hit_minus3"] = (
    strong["entry_future_min"] <= -3
)

strong["hit_minus5"] = (
    strong["entry_future_min"] <= -5
)


# ============================================================
# Day1 -> Day2 形状分類
# ============================================================

def classify_shape(value):

    if value < -5:
        return "<-5pt"

    if value < -3:
        return "-5~-3pt"

    if value < -1:
        return "-3~-1pt"

    if value < 1:
        return "-1~+1pt"

    if value < 3:
        return "+1~+3pt"

    return ">=+3pt"


strong["shape_group"] = (
    strong[
        "Day2_minus_Day1"
    ]
    .apply(
        classify_shape
    )
)


shape_order = [
    "<-5pt",
    "-5~-3pt",
    "-3~-1pt",
    "-1~+1pt",
    "+1~+3pt",
    ">=+3pt",
]


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY1 -> DAY2 SHAPE")
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
    "強い候補 Day1>=4 / Day2>=4 :",
    len(strong),
)


# ============================================================
# Day1 -> Day2変化幅
# ============================================================

print()
print("==============================")
print(" DAY1 -> DAY2 CHANGE")
print("==============================")
print()


if not strong.empty:

    print(
        strong[
            "Day2_minus_Day1"
        ]
        .describe()
        .round(2)
        .to_string()
    )


# ============================================================
# 形状分布
# ============================================================

print()
print("==============================")
print(" SHAPE DISTRIBUTION")
print("==============================")
print()


if not strong.empty:

    shape_counts = (
        strong[
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
# 形状別成績
# ============================================================

print()
print("==============================")
print(" SHAPE x DAY2 ENTRY RETURN")
print("==============================")
print()


summary_rows = []


for shape in shape_order:

    target = strong[
        strong[
            "shape_group"
        ] == shape
    ].copy()

    if target.empty:
        continue

    summary_rows.append(
        {
            "形状":
                shape,

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

            "Day2-Day1中央値":
                target[
                    "Day2_minus_Day1"
                ].median(),

            "Day3実収益中央値":
                target[
                    "Day3_from_entry"
                ].median(),

            "Day4実収益中央値":
                target[
                    "Day4_from_entry"
                ].median(),

            "Day5実収益中央値":
                target[
                    "Day5_from_entry"
                ].median(),

            "Day5勝率":
                target[
                    "day5_win"
                ].mean()
                * 100,

            "最大利益中央値":
                target[
                    "entry_future_max"
                ].median(),

            "最大下落中央値":
                target[
                    "entry_future_min"
                ].median(),

            "+3%到達率":
                target[
                    "hit_plus3"
                ].mean()
                * 100,

            "+5%到達率":
                target[
                    "hit_plus5"
                ].mean()
                * 100,

            "+10%到達率":
                target[
                    "hit_plus10"
                ].mean()
                * 100,

            "-2%到達率":
                target[
                    "hit_minus2"
                ].mean()
                * 100,

            "-3%到達率":
                target[
                    "hit_minus3"
                ].mean()
                * 100,

            "-5%到達率":
                target[
                    "hit_minus5"
                ].mean()
                * 100,
        }
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
# 「Day2がDay1以下」vs「Day2がDay1より上」
# ============================================================

print()
print("==============================")
print(" PULLBACK vs CONTINUATION")
print("==============================")
print()


comparison_groups = [
    (
        "Day2 <= Day1",
        strong[
            strong[
                "Day2_minus_Day1"
            ] <= 0
        ].copy(),
    ),
    (
        "Day2 > Day1",
        strong[
            strong[
                "Day2_minus_Day1"
            ] > 0
        ].copy(),
    ),
]


comparison_rows = []


for label, target in comparison_groups:

    if target.empty:
        continue

    comparison_rows.append(
        {
            "形":
                label,

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

            "変化幅中央値":
                target[
                    "Day2_minus_Day1"
                ].median(),

            "Day5実収益中央値":
                target[
                    "Day5_from_entry"
                ].median(),

            "Day5勝率":
                target[
                    "day5_win"
                ].mean()
                * 100,

            "最大利益中央値":
                target[
                    "entry_future_max"
                ].median(),

            "最大下落中央値":
                target[
                    "entry_future_min"
                ].median(),

            "+5%到達率":
                target[
                    "hit_plus5"
                ].mean()
                * 100,

            "+10%到達率":
                target[
                    "hit_plus10"
                ].mean()
                * 100,

            "-3%到達率":
                target[
                    "hit_minus3"
                ].mean()
                * 100,
        }
    )


comparison = pd.DataFrame(
    comparison_rows
)


if not comparison.empty:

    print(
        comparison
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 変化幅しきい値
#
# 「Day2で少し押している」条件が有効か確認
# ============================================================

print()
print("==============================")
print(" DAY2 CHANGE THRESHOLD")
print("==============================")
print()


threshold_tests = [
    (
        "Day2-Day1 <= 0",
        strong[
            strong[
                "Day2_minus_Day1"
            ] <= 0
        ].copy(),
    ),
    (
        "-5 <= change <= 0",
        strong[
            (
                strong[
                    "Day2_minus_Day1"
                ] >= -5
            )
            & (
                strong[
                    "Day2_minus_Day1"
                ] <= 0
            )
        ].copy(),
    ),
    (
        "-3 <= change <= 0",
        strong[
            (
                strong[
                    "Day2_minus_Day1"
                ] >= -3
            )
            & (
                strong[
                    "Day2_minus_Day1"
                ] <= 0
            )
        ].copy(),
    ),
    (
        "-2 <= change <= +2",
        strong[
            (
                strong[
                    "Day2_minus_Day1"
                ] >= -2
            )
            & (
                strong[
                    "Day2_minus_Day1"
                ] <= 2
            )
        ].copy(),
    ),
    (
        "change >= 0",
        strong[
            strong[
                "Day2_minus_Day1"
            ] >= 0
        ].copy(),
    ),
]


threshold_rows = []


for label, target in threshold_tests:

    if target.empty:
        continue

    threshold_rows.append(
        {
            "条件":
                label,

            "件数":
                len(target),

            "変化幅中央値":
                target[
                    "Day2_minus_Day1"
                ].median(),

            "Day5実収益中央値":
                target[
                    "Day5_from_entry"
                ].median(),

            "Day5勝率":
                target[
                    "day5_win"
                ].mean()
                * 100,

            "最大利益中央値":
                target[
                    "entry_future_max"
                ].median(),

            "最大下落中央値":
                target[
                    "entry_future_min"
                ].median(),

            "+3%到達率":
                target[
                    "hit_plus3"
                ].mean()
                * 100,

            "+5%到達率":
                target[
                    "hit_plus5"
                ].mean()
                * 100,

            "+10%到達率":
                target[
                    "hit_plus10"
                ].mean()
                * 100,

            "-2%到達率":
                target[
                    "hit_minus2"
                ].mean()
                * 100,

            "-3%到達率":
                target[
                    "hit_minus3"
                ].mean()
                * 100,
        }
    )


threshold_summary = pd.DataFrame(
    threshold_rows
)


if not threshold_summary.empty:

    print(
        threshold_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 個別銘柄
# ============================================================

print()
print("==============================")
print(" INDIVIDUAL DETAILS")
print("==============================")
print()


if not strong.empty:

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
        "shape_group",
        "Day3",
        "Day4",
        "Day5",
        "Day3_from_entry",
        "Day4_from_entry",
        "Day5_from_entry",
        "entry_future_max",
        "entry_future_min",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in strong.columns
    ]

    print(
        strong[
            display_columns
        ]
        .sort_values(
            "Day2_minus_Day1",
            ascending=True,
        )
        .round(2)
        .to_string(
            index=False
        )
    )