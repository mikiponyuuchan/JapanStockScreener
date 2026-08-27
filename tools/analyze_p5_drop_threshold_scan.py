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

evaluation["Day2_minus_Day1"] = (
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
            "保持率": 0.0,
            "Day1中央値": np.nan,
            "Day2中央値": np.nan,
            "Drop中央値": np.nan,
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

    total = len(evaluation)

    return {
        "条件": condition,
        "件数": count,
        "保持率": count / total * 100,
        "Day1中央値": data["Day1"].median(),
        "Day2中央値": data["Day2"].median(),
        "Drop中央値": data["Day2_minus_Day1"].median(),
        "Day5収益平均": data["Day5_from_entry"].mean(),
        "Day5収益中央値": data["Day5_from_entry"].median(),
        "Day5勝率": (
            data["Day5_from_entry"].gt(0).mean()
            * 100
        ),
        "最大利益中央値": data["entry_future_max"].median(),
        "最大下落中央値": data["entry_future_min"].median(),
        "+3%到達率": (
            data["entry_future_max"].ge(3).mean()
            * 100
        ),
        "+5%到達率": (
            data["entry_future_max"].ge(5).mean()
            * 100
        ),
        "+10%到達率": (
            data["entry_future_max"].ge(10).mean()
            * 100
        ),
        "-2%到達率": (
            data["entry_future_min"].le(-2).mean()
            * 100
        ),
        "-3%到達率": (
            data["entry_future_min"].le(-3).mean()
            * 100
        ),
        "-5%到達率": (
            data["entry_future_min"].le(-5).mean()
            * 100
        ),
    }


# ============================================================
# 基準
# ============================================================

print()
print("==============================")
print(" P5 DROP THRESHOLD SCAN")
print("==============================")
print()

print("全件数 :", len(df))
print("正式P5 :", len(p5))
print("Day1-Day5完備 :", len(evaluation))


print()
print("==============================")
print(" BASELINE")
print("==============================")
print()

baseline = pd.DataFrame(
    [
        summarize(
            evaluation,
            "除外なし",
        )
    ]
)

print(
    baseline.round(2).to_string(
        index=False
    )
)


# ============================================================
# 0.5pt刻み
# ============================================================

thresholds = np.arange(
    -5.0,
    0.01,
    0.5,
)

rows = []

for threshold in thresholds:

    target = evaluation[
        evaluation["Day2_minus_Day1"]
        >= threshold
    ].copy()

    condition = (
        f"Drop >= {threshold:.1f}pt"
    )

    rows.append(
        summarize(
            target,
            condition,
        )
    )


result = pd.DataFrame(rows)


print()
print("==============================")
print(" DROP THRESHOLD SCAN")
print("==============================")
print()

print(
    result.round(2).to_string(
        index=False
    )
)


# ============================================================
# -4.0 ～ -2.0 を重点表示
# ============================================================

focus_thresholds = [
    -4.0,
    -3.5,
    -3.0,
    -2.5,
    -2.0,
]

focus_rows = []

for threshold in focus_thresholds:

    target = evaluation[
        evaluation["Day2_minus_Day1"]
        >= threshold
    ].copy()

    focus_rows.append(
        summarize(
            target,
            f"Drop >= {threshold:.1f}pt",
        )
    )


focus = pd.DataFrame(focus_rows)


print()
print("==============================")
print(" FOCUS : -4.0pt TO -2.0pt")
print("==============================")
print()

print(
    focus.round(2).to_string(
        index=False
    )
)


# ============================================================
# 除外される側も確認
# ============================================================

excluded_rows = []

for threshold in focus_thresholds:

    excluded = evaluation[
        evaluation["Day2_minus_Day1"]
        < threshold
    ].copy()

    excluded_rows.append(
        summarize(
            excluded,
            f"Drop < {threshold:.1f}pt",
        )
    )


excluded_result = pd.DataFrame(
    excluded_rows
)


print()
print("==============================")
print(" EXCLUDED SIDE")
print("==============================")
print()

print(
    excluded_result.round(2).to_string(
        index=False
    )
)


# ============================================================
# 1件除外するごとの改善効率
# ============================================================

baseline_count = len(evaluation)

baseline_win = (
    evaluation["Day5_from_entry"]
    .gt(0)
    .mean()
    * 100
)

baseline_loss3 = (
    evaluation["entry_future_min"]
    .le(-3)
    .mean()
    * 100
)

baseline_loss5 = (
    evaluation["entry_future_min"]
    .le(-5)
    .mean()
    * 100
)


efficiency_rows = []

for threshold in thresholds:

    target = evaluation[
        evaluation["Day2_minus_Day1"]
        >= threshold
    ].copy()

    count = len(target)

    if count == 0:
        continue

    excluded_count = (
        baseline_count
        - count
    )

    win_rate = (
        target["Day5_from_entry"]
        .gt(0)
        .mean()
        * 100
    )

    loss3_rate = (
        target["entry_future_min"]
        .le(-3)
        .mean()
        * 100
    )

    loss5_rate = (
        target["entry_future_min"]
        .le(-5)
        .mean()
        * 100
    )

    efficiency_rows.append(
        {
            "条件":
                f"Drop >= {threshold:.1f}pt",
            "残存件数": count,
            "除外件数": excluded_count,
            "保持率":
                count
                / baseline_count
                * 100,
            "勝率改善":
                win_rate
                - baseline_win,
            "-3%到達率改善":
                baseline_loss3
                - loss3_rate,
            "-5%到達率改善":
                baseline_loss5
                - loss5_rate,
        }
    )


efficiency = pd.DataFrame(
    efficiency_rows
)


print()
print("==============================")
print(" EXCLUSION EFFICIENCY")
print("==============================")
print()

print(
    efficiency.round(2).to_string(
        index=False
    )
)


print()
print("==============================")
print(" DONE")
print("==============================")