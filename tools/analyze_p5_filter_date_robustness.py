from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATH
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "buy_decision_backtest_panel.csv"
)


# ============================================================
# COLUMN NAMES
# ============================================================

DATE_COL = "検出日"
CODE_COL = "コード"
NAME_COL = "銘柄名"

SCORE_COL = "初動スコア"
CHANGE5_COL = "5日騰落率"

VOLUME_COL = "VolumeRatio20"

DAY1_COL = "Day1"
DAY2_COL = "Day2"
DAY3_COL = "Day3"
DAY4_COL = "Day4"
DAY5_COL = "Day5"

AVOID_COLUMNS = [
    "A_STALL",
    "C_SPIKE",
    "D_OVERHEAT",
    "F_DECEL",
]


# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
    low_memory=False,
)


# ============================================================
# NUMERIC
# ============================================================

numeric_columns = [
    SCORE_COL,
    CHANGE5_COL,
    VOLUME_COL,
    DAY1_COL,
    DAY2_COL,
    DAY3_COL,
    DAY4_COL,
    DAY5_COL,
]

for column in numeric_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )


# ============================================================
# DATE
# ============================================================

df[DATE_COL] = pd.to_datetime(
    df[DATE_COL],
    errors="coerce",
)


# ============================================================
# OFFICIAL P5
# ============================================================

base_p5 = (
    (df[SCORE_COL] >= 3)
    & (df[SCORE_COL] <= 4)
    & (df[CHANGE5_COL] > 0)
    & (df[VOLUME_COL] > 1)
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
# COMPLETE DAY1-DAY5
# ============================================================

evaluation = p5.dropna(
    subset=[
        DAY1_COL,
        DAY2_COL,
        DAY3_COL,
        DAY4_COL,
        DAY5_COL,
    ]
).copy()


# ============================================================
# ENTRY = DAY2
# ============================================================

evaluation["Drop"] = (
    evaluation[DAY2_COL]
    - evaluation[DAY1_COL]
)


for day in [3, 4, 5]:

    evaluation[f"Day{day}_from_entry"] = (
        (
            1.0 + evaluation[f"Day{day}"] / 100.0
        )
        /
        (
            1.0 + evaluation[DAY2_COL] / 100.0
        )
        - 1.0
    ) * 100.0


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
# STEP RULE
#
# Keep:
#   Drop >= -3.5
#
# Rescue:
#   -5.0 <= Drop < -3.5
#   AND 5-day change < 20
#   AND VolumeRatio20 < 3
#
# Exclude:
#   otherwise
# ============================================================

normal_keep = (
    evaluation["Drop"] >= -3.5
)


rescue_keep = (
    (evaluation["Drop"] >= -5.0)
    & (evaluation["Drop"] < -3.5)
    & (evaluation[CHANGE5_COL] < 20.0)
    & (evaluation[VOLUME_COL] < 3.0)
)


evaluation["step_keep"] = (
    normal_keep
    | rescue_keep
)


# ============================================================
# SUMMARY FUNCTION
# ============================================================

def summarize(label, data):

    count = len(data)

    if count == 0:

        return {
            "条件": label,
            "件数": 0,
            "Day5収益平均": np.nan,
            "Day5収益中央値": np.nan,
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
        "条件": label,
        "件数": count,

        "Day5収益平均":
            data["Day5_from_entry"].mean(),

        "Day5収益中央値":
            data["Day5_from_entry"].median(),

        "Day5勝率":
            (data["Day5_from_entry"] > 0).mean() * 100.0,

        "最大利益中央値":
            data["entry_future_max"].median(),

        "最大下落中央値":
            data["entry_future_min"].median(),

        "+3%到達率":
            (data["entry_future_max"] >= 3).mean() * 100.0,

        "+5%到達率":
            (data["entry_future_max"] >= 5).mean() * 100.0,

        "+10%到達率":
            (data["entry_future_max"] >= 10).mean() * 100.0,

        "-2%到達率":
            (data["entry_future_min"] <= -2).mean() * 100.0,

        "-3%到達率":
            (data["entry_future_min"] <= -3).mean() * 100.0,

        "-5%到達率":
            (data["entry_future_min"] <= -5).mean() * 100.0,
    }


def show_table(rows):

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
# HEADER
# ============================================================

print()
print("==============================")
print(" P5 FILTER DATE ROBUSTNESS")
print("==============================")
print()

print("全件数 :", len(df))
print("正式P5 :", len(p5))
print("Day1-Day5完備 :", len(evaluation))
print()


# ============================================================
# OVERALL
# ============================================================

print("==============================")
print(" OVERALL")
print("==============================")
print()

overall_rows = [
    summarize(
        "除外なし",
        evaluation,
    ),
    summarize(
        "段階条件",
        evaluation[
            evaluation["step_keep"]
        ],
    ),
]

show_table(overall_rows)

print()


# ============================================================
# DATE COUNTS
# ============================================================

print("==============================")
print(" DATE COUNTS")
print("==============================")
print()

date_counts = (
    evaluation
    .groupby(DATE_COL)
    .size()
    .reset_index(name="件数")
)

date_counts["検出日"] = (
    date_counts[DATE_COL]
    .dt.strftime("%Y-%m-%d")
)

date_counts = date_counts[
    [
        "検出日",
        "件数",
    ]
]

print(
    date_counts.to_string(
        index=False
    )
)

print()


# ============================================================
# BY DATE
# ============================================================

print("==============================")
print(" BY DATE")
print("==============================")
print()

by_date_rows = []

dates = sorted(
    evaluation[DATE_COL]
    .dropna()
    .unique()
)


for date_value in dates:

    day_data = evaluation[
        evaluation[DATE_COL] == date_value
    ].copy()

    kept = day_data[
        day_data["step_keep"]
    ].copy()

    total_count = len(day_data)
    kept_count = len(kept)

    label_date = pd.Timestamp(
        date_value
    ).strftime("%Y-%m-%d")

    baseline = summarize(
        "除外なし",
        day_data,
    )

    filtered = summarize(
        "段階条件",
        kept,
    )

    row = {
        "検出日": label_date,

        "全件数":
            total_count,

        "残存件数":
            kept_count,

        "保持率":
            (
                kept_count
                / total_count
                * 100.0
                if total_count > 0
                else np.nan
            ),

        "基準Day5中央値":
            baseline["Day5収益中央値"],

        "条件Day5中央値":
            filtered["Day5収益中央値"],

        "基準Day5勝率":
            baseline["Day5勝率"],

        "条件Day5勝率":
            filtered["Day5勝率"],

        "基準+5%到達率":
            baseline["+5%到達率"],

        "条件+5%到達率":
            filtered["+5%到達率"],

        "基準-3%到達率":
            baseline["-3%到達率"],

        "条件-3%到達率":
            filtered["-3%到達率"],

        "基準-5%到達率":
            baseline["-5%到達率"],

        "条件-5%到達率":
            filtered["-5%到達率"],
    }

    by_date_rows.append(row)


show_table(by_date_rows)

print()


# ============================================================
# LEAVE ONE DATE OUT
# ============================================================

print("==============================")
print(" LEAVE ONE DATE OUT")
print("==============================")
print()

leave_rows = []


for excluded_date in dates:

    test_data = evaluation[
        evaluation[DATE_COL]
        != excluded_date
    ].copy()

    kept = test_data[
        test_data["step_keep"]
    ].copy()

    baseline = summarize(
        "除外なし",
        test_data,
    )

    filtered = summarize(
        "段階条件",
        kept,
    )

    label_date = pd.Timestamp(
        excluded_date
    ).strftime("%Y-%m-%d")

    row = {
        "除外日":
            label_date,

        "基準件数":
            len(test_data),

        "条件件数":
            len(kept),

        "保持率":
            (
                len(kept)
                / len(test_data)
                * 100.0
                if len(test_data) > 0
                else np.nan
            ),

        "Day5中央値変化":
            (
                filtered["Day5収益中央値"]
                - baseline["Day5収益中央値"]
            ),

        "勝率改善":
            (
                filtered["Day5勝率"]
                - baseline["Day5勝率"]
            ),

        "+3%到達率変化":
            (
                filtered["+3%到達率"]
                - baseline["+3%到達率"]
            ),

        "+5%到達率変化":
            (
                filtered["+5%到達率"]
                - baseline["+5%到達率"]
            ),

        "+10%到達率変化":
            (
                filtered["+10%到達率"]
                - baseline["+10%到達率"]
            ),

        "-2%到達率改善":
            (
                baseline["-2%到達率"]
                - filtered["-2%到達率"]
            ),

        "-3%到達率改善":
            (
                baseline["-3%到達率"]
                - filtered["-3%到達率"]
            ),

        "-5%到達率改善":
            (
                baseline["-5%到達率"]
                - filtered["-5%到達率"]
            ),
    }

    leave_rows.append(row)


show_table(leave_rows)

print()


# ============================================================
# LEAVE ONE DATE OUT STABILITY
# ============================================================

print("==============================")
print(" LEAVE ONE DATE OUT STABILITY")
print("==============================")
print()

leave_df = pd.DataFrame(
    leave_rows
)


stability_rows = []


metrics = [
    "Day5中央値変化",
    "勝率改善",
    "+3%到達率変化",
    "+5%到達率変化",
    "+10%到達率変化",
    "-2%到達率改善",
    "-3%到達率改善",
    "-5%到達率改善",
]


for metric in metrics:

    values = pd.to_numeric(
        leave_df[metric],
        errors="coerce",
    )

    stability_rows.append(
        {
            "指標": metric,
            "平均": values.mean(),
            "最小": values.min(),
            "最大": values.max(),
            "全ケース改善":
                bool(
                    (values >= 0)
                    .fillna(False)
                    .all()
                ),
        }
    )


show_table(stability_rows)

print()


# ============================================================
# EXCLUDED DATE DISTRIBUTION
# ============================================================

print("==============================")
print(" EXCLUDED GROUP BY DATE")
print("==============================")
print()

excluded = evaluation[
    ~evaluation["step_keep"]
].copy()


excluded_rows = []


for date_value in dates:

    day_excluded = excluded[
        excluded[DATE_COL] == date_value
    ].copy()

    if len(day_excluded) == 0:
        continue

    label_date = pd.Timestamp(
        date_value
    ).strftime("%Y-%m-%d")

    result = summarize(
        label_date,
        day_excluded,
    )

    result["検出日"] = label_date

    excluded_rows.append(result)


if excluded_rows:

    excluded_table = pd.DataFrame(
        excluded_rows
    )

    cols = [
        "検出日",
        "件数",
        "Day5収益平均",
        "Day5収益中央値",
        "Day5勝率",
        "最大利益中央値",
        "最大下落中央値",
        "+3%到達率",
        "+5%到達率",
        "+10%到達率",
        "-2%到達率",
        "-3%到達率",
        "-5%到達率",
    ]

    excluded_table = excluded_table[
        cols
    ]

    numeric_cols = excluded_table.select_dtypes(
        include="number"
    ).columns

    excluded_table[numeric_cols] = (
        excluded_table[
            numeric_cols
        ].round(2)
    )

    print(
        excluded_table.to_string(
            index=False
        )
    )

else:

    print("除外銘柄なし")


print()


# ============================================================
# DONE
# ============================================================

print("==============================")
print(" DONE")
print("==============================")