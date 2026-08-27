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
# 回避条件除外
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

x = p5.dropna(
    subset=[
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
    ]
).copy()


# ============================================================
# Day1 -> Day2変化幅
# ============================================================

x["Day2_minus_Day1"] = (
    x["Day2"]
    - x["Day1"]
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


x["Day3_from_entry"] = return_from_entry(
    x["Day2"],
    x["Day3"],
)

x["Day4_from_entry"] = return_from_entry(
    x["Day2"],
    x["Day4"],
)

x["Day5_from_entry"] = return_from_entry(
    x["Day2"],
    x["Day5"],
)


# ============================================================
# Day2買い後の最大利益・最大下落
# ============================================================

entry_future_columns = [
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
]


x["entry_future_max"] = (
    x[entry_future_columns]
    .max(axis=1)
)

x["entry_future_min"] = (
    x[entry_future_columns]
    .min(axis=1)
)


# ============================================================
# 結果フラグ
# ============================================================

x["day5_win"] = (
    x["Day5_from_entry"] > 0
)

x["hit_plus3"] = (
    x["entry_future_max"] >= 3
)

x["hit_plus5"] = (
    x["entry_future_max"] >= 5
)

x["hit_plus10"] = (
    x["entry_future_max"] >= 10
)

x["hit_minus2"] = (
    x["entry_future_min"] <= -2
)

x["hit_minus3"] = (
    x["entry_future_min"] <= -3
)

x["hit_minus5"] = (
    x["entry_future_min"] <= -5
)


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY2 ENTRY FULL PROFILE")
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
    len(x),
)


# ============================================================
# Day2買い後 全体成績
# ============================================================

print()
print("==============================")
print(" ALL P5 : DAY2 ENTRY RESULT")
print("==============================")
print()

print(
    "Day3実収益中央値 :",
    round(
        x["Day3_from_entry"].median(),
        2,
    ),
    "%",
)

print(
    "Day4実収益中央値 :",
    round(
        x["Day4_from_entry"].median(),
        2,
    ),
    "%",
)

print(
    "Day5実収益中央値 :",
    round(
        x["Day5_from_entry"].median(),
        2,
    ),
    "%",
)

print(
    "Day5勝率 :",
    round(
        x["day5_win"].mean() * 100,
        2,
    ),
    "%",
)

print(
    "最大利益中央値 :",
    round(
        x["entry_future_max"].median(),
        2,
    ),
    "%",
)

print(
    "最大下落中央値 :",
    round(
        x["entry_future_min"].median(),
        2,
    ),
    "%",
)

print(
    "+3%到達率 :",
    round(
        x["hit_plus3"].mean() * 100,
        2,
    ),
    "%",
)

print(
    "+5%到達率 :",
    round(
        x["hit_plus5"].mean() * 100,
        2,
    ),
    "%",
)

print(
    "+10%到達率 :",
    round(
        x["hit_plus10"].mean() * 100,
        2,
    ),
    "%",
)

print(
    "-2%到達率 :",
    round(
        x["hit_minus2"].mean() * 100,
        2,
    ),
    "%",
)

print(
    "-3%到達率 :",
    round(
        x["hit_minus3"].mean() * 100,
        2,
    ),
    "%",
)

print(
    "-5%到達率 :",
    round(
        x["hit_minus5"].mean() * 100,
        2,
    ),
    "%",
)


# ============================================================
# 相関
#
# まず閾値を決めず、
# 各変数と買い後成績の関係を見る
# ============================================================

print()
print("==============================")
print(" CORRELATION")
print("==============================")
print()


correlation_columns = [
    SCORE_COL,
    CHANGE5_COL,
    "VolumeRatio20",
    "Day1",
    "Day2",
    "Day2_minus_Day1",
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
    "entry_future_max",
    "entry_future_min",
]


corr = (
    x[correlation_columns]
    .corr()
)


target_columns = [
    "Day5_from_entry",
    "entry_future_max",
    "entry_future_min",
]


print(
    corr[
        target_columns
    ]
    .round(3)
    .to_string()
)


# ============================================================
# 成功組・失敗組プロフィール
# ============================================================

def profile_group(
    label,
    target,
):

    if target.empty:
        return None

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
                "Day2_minus_Day1"
            ].median(),

        "Day5実収益中央値":
            target[
                "Day5_from_entry"
            ].median(),

        "最大利益中央値":
            target[
                "entry_future_max"
            ].median(),

        "最大下落中央値":
            target[
                "entry_future_min"
            ].median(),
    }


print()
print("==============================")
print(" SUCCESS PROFILE")
print("==============================")
print()


success_groups = [
    (
        "+3%以上到達",
        x[
            x["hit_plus3"]
        ].copy(),
    ),
    (
        "+5%以上到達",
        x[
            x["hit_plus5"]
        ].copy(),
    ),
    (
        "+10%以上到達",
        x[
            x["hit_plus10"]
        ].copy(),
    ),
]


success_rows = []


for label, target in success_groups:

    row = profile_group(
        label,
        target,
    )

    if row is not None:
        success_rows.append(row)


success_summary = pd.DataFrame(
    success_rows
)


if not success_summary.empty:

    print(
        success_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 失敗プロフィール
# ============================================================

print()
print("==============================")
print(" FAILURE PROFILE")
print("==============================")
print()


failure_groups = [
    (
        "-2%以下到達",
        x[
            x["hit_minus2"]
        ].copy(),
    ),
    (
        "-3%以下到達",
        x[
            x["hit_minus3"]
        ].copy(),
    ),
    (
        "-5%以下到達",
        x[
            x["hit_minus5"]
        ].copy(),
    ),
]


failure_rows = []


for label, target in failure_groups:

    row = profile_group(
        label,
        target,
    )

    if row is not None:
        failure_rows.append(row)


failure_summary = pd.DataFrame(
    failure_rows
)


if not failure_summary.empty:

    print(
        failure_summary
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 勝ち組 vs 負け組
#
# +5%到達を勝ち組
# -3%到達を負け組
# ============================================================

print()
print("==============================")
print(" +5 WINNER vs -3 LOSER")
print("==============================")
print()


winner = x[
    x["hit_plus5"]
].copy()

loser = x[
    x["hit_minus3"]
].copy()


compare_rows = []


winner_row = profile_group(
    "+5%到達",
    winner,
)

loser_row = profile_group(
    "-3%到達",
    loser,
)


if winner_row is not None:
    compare_rows.append(
        winner_row
    )

if loser_row is not None:
    compare_rows.append(
        loser_row
    )


compare = pd.DataFrame(
    compare_rows
)


if not compare.empty:

    print(
        compare
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day1しきい値
# ============================================================

print()
print("==============================")
print(" DAY1 THRESHOLD")
print("==============================")
print()


day1_thresholds = [
    -5,
    -3,
    -2,
    -1,
    0,
    1,
    2,
    3,
    4,
    5,
]


day1_rows = []


for threshold in day1_thresholds:

    target = x[
        x["Day1"] >= threshold
    ].copy()

    if target.empty:
        continue

    day1_rows.append(
        {
            "Day1条件":
                f">={threshold}%",

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

            "-3%到達率":
                target[
                    "hit_minus3"
                ].mean()
                * 100,
        }
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
# Day2しきい値
# ============================================================

print()
print("==============================")
print(" DAY2 THRESHOLD")
print("==============================")
print()


day2_thresholds = [
    -5,
    -3,
    -2,
    -1,
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

    target = x[
        x["Day2"] >= threshold
    ].copy()

    if target.empty:
        continue

    day2_rows.append(
        {
            "Day2条件":
                f">={threshold}%",

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

            "-3%到達率":
                target[
                    "hit_minus3"
                ].mean()
                * 100,
        }
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
# Day2-Day1変化幅
# ============================================================

print()
print("==============================")
print(" DAY2 - DAY1 GROUP")
print("==============================")
print()


def classify_change(value):

    if value < -5:
        return "<-5"

    if value < -3:
        return "-5~-3"

    if value < -1:
        return "-3~-1"

    if value < 1:
        return "-1~+1"

    if value < 3:
        return "+1~+3"

    return ">=+3"


x["change_group"] = (
    x[
        "Day2_minus_Day1"
    ]
    .apply(
        classify_change
    )
)


change_order = [
    "<-5",
    "-5~-3",
    "-3~-1",
    "-1~+1",
    "+1~+3",
    ">=+3",
]


change_rows = []


for group in change_order:

    target = x[
        x[
            "change_group"
        ] == group
    ].copy()

    if target.empty:
        continue

    change_rows.append(
        {
            "変化幅":
                group,

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
# +5%到達銘柄 詳細
# ============================================================

print()
print("==============================")
print(" +5% WINNER DETAILS")
print("==============================")
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
    "Day2_minus_Day1",
    "Day3_from_entry",
    "Day4_from_entry",
    "Day5_from_entry",
    "entry_future_max",
    "entry_future_min",
]


display_columns = [
    column
    for column in display_columns
    if column in x.columns
]


if not winner.empty:

    print(
        winner[
            display_columns
        ]
        .sort_values(
            "entry_future_max",
            ascending=False,
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# -3%到達銘柄 詳細
# ============================================================

print()
print("==============================")
print(" -3% LOSER DETAILS")
print("==============================")
print()


if not loser.empty:

    print(
        loser[
            display_columns
        ]
        .sort_values(
            "entry_future_min",
            ascending=True,
        )
        .round(2)
        .to_string(
            index=False
        )
    )