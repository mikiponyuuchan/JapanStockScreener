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
# 読み込み
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
    low_memory=False,
)


# ============================================================
# 正式P5
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

base = (
    (score >= 3)
    & (chg5 > 0)
    & (vr20 > 1)
)

avoid = pd.Series(
    False,
    index=df.index,
)

for col in AVOID_COLUMNS:

    if col in df.columns:

        avoid |= (
            df[col]
            .fillna(False)
            .astype(bool)
        )

p5 = df[
    base & ~avoid
].copy()


# ============================================================
# Dayデータ数値化
# ============================================================

for col in DAY_COLS:

    p5[col] = pd.to_numeric(
        p5[col],
        errors="coerce",
    )


# ============================================================
# Day1～Day5完備
# ============================================================

x = p5.dropna(
    subset=DAY_COLS
).copy()


# ============================================================
# Day1が5日間の底
# ============================================================

x["bottom_day"] = (
    x[DAY_COLS]
    .idxmin(axis=1)
)

x = x[
    x["bottom_day"] == "Day1"
].copy()


# ============================================================
# Day1 → Day2反発幅
# ============================================================

x["rebound_size"] = (
    x["Day2"]
    - x["Day1"]
)


# ============================================================
# その後の成績
#
# Day2終了時点でシグナルを確認する想定なので、
# 成績判定はDay3～Day5を中心に見る
# ============================================================

POST_COLS = [
    "Day3",
    "Day4",
    "Day5",
]

x["post_day2_max"] = (
    x[POST_COLS]
    .max(axis=1)
)

x["post_day2_min"] = (
    x[POST_COLS]
    .min(axis=1)
)

x["day5_positive"] = (
    x["Day5"] > 0
)

x["post_hit_5"] = (
    x["post_day2_max"] >= 5
)

x["post_hit_10"] = (
    x["post_day2_max"] >= 10
)


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY2 REBOUND CROSS")
print("==============================")
print()

print(
    "正式P5 :",
    len(p5),
)

print(
    "Day1-Day5完備 :",
    len(
        p5.dropna(
            subset=DAY_COLS
        )
    ),
)

print(
    "Day1が底 :",
    len(x),
)


# ============================================================
# 閾値
# ============================================================

DAY2_THRESHOLDS = [
    0,
    3,
    5,
]

REBOUND_THRESHOLDS = [
    3,
    5,
    7,
    10,
]


# ============================================================
# クロス集計
# ============================================================

rows = []

for day2_threshold in DAY2_THRESHOLDS:

    for rebound_threshold in REBOUND_THRESHOLDS:

        mask = (
            (x["Day2"] >= day2_threshold)
            & (
                x["rebound_size"]
                >= rebound_threshold
            )
        )

        target = x[
            mask
        ].copy()

        count = len(target)

        if count == 0:

            rows.append(
                {
                    "Day2条件": (
                        f">={day2_threshold}%"
                    ),
                    "反発幅条件": (
                        f">={rebound_threshold}pt"
                    ),
                    "件数": 0,
                    "Day1中央値": None,
                    "Day2中央値": None,
                    "反発幅中央値": None,
                    "Day5中央値": None,
                    "Day5プラス率": None,
                    "Day3-5で+5%以上率": None,
                    "Day3-5で+10%以上率": None,
                }
            )

            continue

        rows.append(
            {
                "Day2条件": (
                    f">={day2_threshold}%"
                ),
                "反発幅条件": (
                    f">={rebound_threshold}pt"
                ),
                "件数": count,
                "Day1中央値": round(
                    target[
                        "Day1"
                    ].median(),
                    2,
                ),
                "Day2中央値": round(
                    target[
                        "Day2"
                    ].median(),
                    2,
                ),
                "反発幅中央値": round(
                    target[
                        "rebound_size"
                    ].median(),
                    2,
                ),
                "Day5中央値": round(
                    target[
                        "Day5"
                    ].median(),
                    2,
                ),
                "Day5プラス率": round(
                    target[
                        "day5_positive"
                    ].mean()
                    * 100,
                    2,
                ),
                "Day3-5で+5%以上率": round(
                    target[
                        "post_hit_5"
                    ].mean()
                    * 100,
                    2,
                ),
                "Day3-5で+10%以上率": round(
                    target[
                        "post_hit_10"
                    ].mean()
                    * 100,
                    2,
                ),
            }
        )


result = pd.DataFrame(
    rows
)


# ============================================================
# 結果表示
# ============================================================

print()
print("==============================")
print(" DAY2 POSITION x REBOUND SIZE")
print("==============================")
print()

print(
    result.to_string(
        index=False
    )
)


# ============================================================
# 参考：Day2位置だけ
# ============================================================

print()
print("==============================")
print(" DAY2 POSITION ONLY")
print("==============================")
print()

for threshold in DAY2_THRESHOLDS:

    target = x[
        x["Day2"] >= threshold
    ]

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
                "post_hit_5"
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
                "post_hit_10"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print()


# ============================================================
# 参考：反発幅だけ
# ============================================================

print()
print("==============================")
print(" REBOUND SIZE ONLY")
print("==============================")
print()

for threshold in REBOUND_THRESHOLDS:

    target = x[
        x["rebound_size"]
        >= threshold
    ]

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
                "post_hit_5"
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
                "post_hit_10"
            ].mean()
            * 100,
            2,
        ),
        "%",
    )

    print()