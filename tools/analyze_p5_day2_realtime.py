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
# データ読込
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
    *DAY_COLS,
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
# Day2時点で利用可能な情報だけにする
#
# Day3～Day5は「成績判定」にのみ使用する。
# Day1が5日間の底だったかどうかは判定条件に使わない。
# ============================================================

day2_ready = p5.dropna(
    subset=[
        "Day1",
        "Day2",
    ]
).copy()


# ============================================================
# P5後、Day1で一度押した銘柄
# ============================================================

pullback = day2_ready[
    day2_ready["Day1"] < 0
].copy()


# ============================================================
# Day1 -> Day2 反発幅
# ============================================================

pullback["rebound_size"] = (
    pullback["Day2"]
    - pullback["Day1"]
)


# ============================================================
# Day3～Day5の将来成績
#
# ここは「判定条件」ではなく、
# Day2時点で買った場合の結果評価にだけ使用する。
# ============================================================

future_columns = [
    "Day3",
    "Day4",
    "Day5",
]

evaluation = pullback.dropna(
    subset=future_columns
).copy()


evaluation["future_max"] = (
    evaluation[
        future_columns
    ]
    .max(axis=1)
)


evaluation["future_min"] = (
    evaluation[
        future_columns
    ]
    .min(axis=1)
)


evaluation["day5_positive"] = (
    evaluation["Day5"] > 0
)


evaluation["future_hit_5pct"] = (
    evaluation["future_max"] >= 5
)


evaluation["future_hit_10pct"] = (
    evaluation["future_max"] >= 10
)


# ============================================================
# 基本件数
# ============================================================

print()
print("==============================")
print(" P5 DAY2 REALTIME TEST")
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
    "Day1-Day2あり :",
    len(day2_ready),
)

print(
    "Day1マイナス :",
    len(pullback),
)

print(
    "Day3-Day5まで評価可能 :",
    len(evaluation),
)


# ============================================================
# Day1分布
# ============================================================

print()
print("==============================")
print(" DAY1 PULLBACK DISTRIBUTION")
print("==============================")
print()

print(
    evaluation["Day1"]
    .describe()
    .round(2)
)


# ============================================================
# Day2位置 × 反発幅
# ============================================================

print()
print("==============================")
print(" DAY2 POSITION x REBOUND SIZE")
print("==============================")
print()


day2_thresholds = [
    0,
    1,
    2,
    3,
    4,
    5,
]

rebound_thresholds = [
    1,
    2,
    3,
    4,
    5,
    7,
    10,
]


summary_rows = []


for day2_threshold in day2_thresholds:

    for rebound_threshold in rebound_thresholds:

        target = evaluation[
            (evaluation["Day2"] >= day2_threshold)
            & (
                evaluation["rebound_size"]
                >= rebound_threshold
            )
        ].copy()

        count = len(target)

        if count == 0:
            continue

        summary_rows.append(
            {
                "Day2条件":
                    f">={day2_threshold}%",

                "反発幅条件":
                    f">={rebound_threshold}pt",

                "件数":
                    count,

                "Day1中央値":
                    target["Day1"].median(),

                "Day2中央値":
                    target["Day2"].median(),

                "反発幅中央値":
                    target[
                        "rebound_size"
                    ].median(),

                "Day5中央値":
                    target["Day5"].median(),

                "Day5プラス率":
                    (
                        target[
                            "day5_positive"
                        ].mean()
                        * 100
                    ),

                "Day3-5で+5%以上率":
                    (
                        target[
                            "future_hit_5pct"
                        ].mean()
                        * 100
                    ),

                "Day3-5で+10%以上率":
                    (
                        target[
                            "future_hit_10pct"
                        ].mean()
                        * 100
                    ),

                "Day3-5最大中央値":
                    target[
                        "future_max"
                    ].median(),

                "Day3-5最小中央値":
                    target[
                        "future_min"
                    ].median(),
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
# Day2位置だけで比較
# ============================================================

print()
print("==============================")
print(" DAY2 POSITION ONLY")
print("==============================")
print()


for threshold in [
    0,
    1,
    2,
    3,
    4,
    5,
]:

    target = evaluation[
        evaluation["Day2"] >= threshold
    ].copy()

    if target.empty:
        continue

    print(
        f"Day2 >= {threshold}%"
    )

    print(
        " 件数 :",
        len(target),
    )

    print(
        " Day1中央値 :",
        round(
            target["Day1"].median(),
            2,
        ),
    )

    print(
        " Day2中央値 :",
        round(
            target["Day2"].median(),
            2,
        ),
    )

    print(
        " 反発幅中央値 :",
        round(
            target[
                "rebound_size"
            ].median(),
            2,
        ),
    )

    print(
        " Day5中央値 :",
        round(
            target["Day5"].median(),
            2,
        ),
    )

    print(
        " Day5プラス率 :",
        round(
            target[
                "day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        " Day3-5 +5%以上率 :",
        round(
            target[
                "future_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        " Day3-5 +10%以上率 :",
        round(
            target[
                "future_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print()


# ============================================================
# 反発幅だけで比較
# ============================================================

print()
print("==============================")
print(" REBOUND SIZE ONLY")
print("==============================")
print()


for threshold in [
    1,
    2,
    3,
    4,
    5,
    7,
    10,
]:

    target = evaluation[
        evaluation[
            "rebound_size"
        ] >= threshold
    ].copy()

    if target.empty:
        continue

    print(
        f"Rebound >= {threshold}pt"
    )

    print(
        " 件数 :",
        len(target),
    )

    print(
        " Day2中央値 :",
        round(
            target["Day2"].median(),
            2,
        ),
    )

    print(
        " Day5中央値 :",
        round(
            target["Day5"].median(),
            2,
        ),
    )

    print(
        " Day5プラス率 :",
        round(
            target[
                "day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        " Day3-5 +5%以上率 :",
        round(
            target[
                "future_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        " Day3-5 +10%以上率 :",
        round(
            target[
                "future_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print()


# ============================================================
# 有力候補
#
# Day2 >= +3%
# かつ
# Day1 -> Day2 反発幅 >= 5pt
#
# 未来情報は選別に使わない。
# ============================================================

candidate = evaluation[
    (evaluation["Day2"] >= 3)
    & (
        evaluation[
            "rebound_size"
        ] >= 5
    )
].copy()


print()
print("==============================")
print(" REALTIME CANDIDATE")
print(" Day2 >= 3% / Rebound >= 5pt")
print("==============================")
print()

print(
    "件数 :",
    len(candidate),
)


if not candidate.empty:

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
        "Day3-5 +5%以上率 :",
        round(
            candidate[
                "future_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "Day3-5 +10%以上率 :",
        round(
            candidate[
                "future_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

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
        "rebound_size",
        "Day3",
        "Day4",
        "Day5",
        "future_max",
        "future_min",
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
            [
                "Day2",
                "rebound_size",
            ],
            ascending=[
                False,
                False,
            ],
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# Day2 >= +5% 単独
#
# 前回非常に強かった条件。
# 「Day1が5日間の底」という未来情報を除外して再検証する。
# ============================================================

strong_day2 = evaluation[
    evaluation["Day2"] >= 5
].copy()


print()
print("==============================")
print(" DAY2 >= 5% REALTIME")
print("==============================")
print()

print(
    "件数 :",
    len(strong_day2),
)


if not strong_day2.empty:

    print(
        "Day1中央値 :",
        round(
            strong_day2[
                "Day1"
            ].median(),
            2,
        ),
    )

    print(
        "Day2中央値 :",
        round(
            strong_day2[
                "Day2"
            ].median(),
            2,
        ),
    )

    print(
        "反発幅中央値 :",
        round(
            strong_day2[
                "rebound_size"
            ].median(),
            2,
        ),
    )

    print(
        "Day5中央値 :",
        round(
            strong_day2[
                "Day5"
            ].median(),
            2,
        ),
    )

    print(
        "Day5プラス率 :",
        round(
            strong_day2[
                "day5_positive"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "Day3-5 +5%以上率 :",
        round(
            strong_day2[
                "future_hit_5pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        "Day3-5 +10%以上率 :",
        round(
            strong_day2[
                "future_hit_10pct"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )