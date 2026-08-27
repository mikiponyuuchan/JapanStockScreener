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
#
# 回避条件
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
# Day1～Day5 完備
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
# Day2終値エントリー後リターン
#
# DayN は「検出日終値 = 0%」基準。
#
# 例えば
#
# Day2 = +5%
# Day3 = +10%
#
# の場合、
#
# Day2終値 = 1.05
# Day3終値 = 1.10
#
# Day2終値で買った実際のDay3利益率は
#
# (1.10 / 1.05 - 1) * 100
#
# となる。
# ============================================================

for day in [
    "Day3",
    "Day4",
    "Day5",
]:

    complete[
        f"{day}_from_entry"
    ] = (
        (
            (
                1
                + complete[day] / 100
            )
            /
            (
                1
                + complete["Day2"] / 100
            )
        )
        - 1
    ) * 100


# ============================================================
# Day2買い後の将来成績
# ============================================================

entry_future_columns = [
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
]


complete["entry_future_max"] = (
    complete[
        entry_future_columns
    ]
    .max(axis=1)
)


complete["entry_future_min"] = (
    complete[
        entry_future_columns
    ]
    .min(axis=1)
)


complete["entry_day5_positive"] = (
    complete["Day5_from_entry"] > 0
)


# ============================================================
# 利益到達
# ============================================================

complete["entry_hit_3pct"] = (
    complete["entry_future_max"] >= 3
)

complete["entry_hit_5pct"] = (
    complete["entry_future_max"] >= 5
)

complete["entry_hit_10pct"] = (
    complete["entry_future_max"] >= 10
)


# ============================================================
# 下落到達
# ============================================================

complete["entry_hit_minus2pct"] = (
    complete["entry_future_min"] <= -2
)

complete["entry_hit_minus3pct"] = (
    complete["entry_future_min"] <= -3
)

complete["entry_hit_minus5pct"] = (
    complete["entry_future_min"] <= -5
)


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY2 ENTRY RETURN")
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


# ============================================================
# 集計関数
# ============================================================

def make_summary(
    label,
    target,
):

    if target.empty:

        return {
            "条件": label,
            "件数": 0,
        }

    return {
        "条件":
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
            (
                target[
                    "entry_day5_positive"
                ].mean()
                * 100
            ),

        "最大利益中央値":
            target[
                "entry_future_max"
            ].median(),

        "最大下落中央値":
            target[
                "entry_future_min"
            ].median(),

        "+3%到達率":
            (
                target[
                    "entry_hit_3pct"
                ].mean()
                * 100
            ),

        "+5%到達率":
            (
                target[
                    "entry_hit_5pct"
                ].mean()
                * 100
            ),

        "+10%到達率":
            (
                target[
                    "entry_hit_10pct"
                ].mean()
                * 100
            ),

        "-2%到達率":
            (
                target[
                    "entry_hit_minus2pct"
                ].mean()
                * 100
            ),

        "-3%到達率":
            (
                target[
                    "entry_hit_minus3pct"
                ].mean()
                * 100
            ),

        "-5%到達率":
            (
                target[
                    "entry_hit_minus5pct"
                ].mean()
                * 100
            ),
    }


# ============================================================
# 条件比較
# ============================================================

conditions = [
    (
        "Day1>=3 / Day2>=3",
        (
            (complete["Day1"] >= 3)
            & (complete["Day2"] >= 3)
        ),
    ),
    (
        "Day1>=3 / Day2>=4",
        (
            (complete["Day1"] >= 3)
            & (complete["Day2"] >= 4)
        ),
    ),
    (
        "Day1>=3 / Day2>=5",
        (
            (complete["Day1"] >= 3)
            & (complete["Day2"] >= 5)
        ),
    ),
    (
        "Day1>=4 / Day2>=4",
        (
            (complete["Day1"] >= 4)
            & (complete["Day2"] >= 4)
        ),
    ),
    (
        "Day1>=4 / Day2>=5",
        (
            (complete["Day1"] >= 4)
            & (complete["Day2"] >= 5)
        ),
    ),
    (
        "Day1>=5 / Day2>=5",
        (
            (complete["Day1"] >= 5)
            & (complete["Day2"] >= 5)
        ),
    ),
]


summary_rows = []


for label, condition in conditions:

    target = complete[
        condition
    ].copy()

    summary_rows.append(
        make_summary(
            label,
            target,
        )
    )


summary = pd.DataFrame(
    summary_rows
)


print()
print("==============================")
print(" DAY2 ENTRY CONDITION COMPARISON")
print("==============================")
print()

print(
    summary
    .round(2)
    .to_string(
        index=False
    )
)


# ============================================================
# 基本候補
#
# Day1 >= 3%
# Day2 >= 3%
# ============================================================

candidate = complete[
    (complete["Day1"] >= 3)
    & (complete["Day2"] >= 3)
].copy()


print()
print("==============================")
print(" MAIN CANDIDATE")
print(" Day1 >= 3% / Day2 >= 3%")
print("==============================")
print()

print(
    "件数 :",
    len(candidate),
)


if not candidate.empty:

    print(
        "Day2買い -> Day3中央値 :",
        round(
            candidate[
                "Day3_from_entry"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day2買い -> Day4中央値 :",
        round(
            candidate[
                "Day4_from_entry"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day2買い -> Day5中央値 :",
        round(
            candidate[
                "Day5_from_entry"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day5勝率 :",
        round(
            candidate[
                "entry_day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "最大利益中央値 :",
        round(
            candidate[
                "entry_future_max"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "最大下落中央値 :",
        round(
            candidate[
                "entry_future_min"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "+3%到達率 :",
        round(
            candidate[
                "entry_hit_3pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "+5%到達率 :",
        round(
            candidate[
                "entry_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "+10%到達率 :",
        round(
            candidate[
                "entry_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-2%到達率 :",
        round(
            candidate[
                "entry_hit_minus2pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-3%到達率 :",
        round(
            candidate[
                "entry_hit_minus3pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-5%到達率 :",
        round(
            candidate[
                "entry_hit_minus5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )


# ============================================================
# 個別結果
# ============================================================

print()
print("==============================")
print(" MAIN CANDIDATE DETAILS")
print("==============================")
print()


if not candidate.empty:

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
        "Day3_from_entry",
        "Day4_from_entry",
        "Day5_from_entry",
        "entry_future_max",
        "entry_future_min",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in candidate.columns
    ]

    print(
        candidate[
            display_columns
        ]
        .sort_values(
            "Day5_from_entry",
            ascending=False,
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day2 >= 4 の強い継続型
# ============================================================

strong = complete[
    (complete["Day1"] >= 3)
    & (complete["Day2"] >= 4)
].copy()


print()
print("==============================")
print(" STRONG CONTINUATION")
print(" Day1 >= 3% / Day2 >= 4%")
print("==============================")
print()


if strong.empty:

    print("件数 : 0")

else:

    print(
        "件数 :",
        len(strong),
    )

    print(
        "Day5実収益中央値 :",
        round(
            strong[
                "Day5_from_entry"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "Day5勝率 :",
        round(
            strong[
                "entry_day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "最大利益中央値 :",
        round(
            strong[
                "entry_future_max"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "最大下落中央値 :",
        round(
            strong[
                "entry_future_min"
            ].median(),
            2,
        ),
        "%",
    )

    print(
        "+5%到達率 :",
        round(
            strong[
                "entry_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "-3%到達率 :",
        round(
            strong[
                "entry_hit_minus3pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )