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
# 回避条件なし
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
# Day2終値を買値 = 0% に変換
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
# 基本候補
#
# Day1 >= 3%
# Day2 >= 3%
# ============================================================

candidate = complete[
    (complete["Day1"] >= 3)
    & (complete["Day2"] >= 3)
].copy()


# ============================================================
# 強い候補
#
# Day1 >= 4%
# Day2 >= 4%
# ============================================================

strong_candidate = complete[
    (complete["Day1"] >= 4)
    & (complete["Day2"] >= 4)
].copy()


# ============================================================
# 利確・損切りルール
#
# 注意：
# Day3～Day5の終値だけで判定する。
#
# 日中高値・安値は使用していないため、
# 「その日の途中でどちらに先に到達したか」は判定しない。
# ============================================================

EXIT_RULES = [
    (3, 2),
    (5, 2),
    (5, 3),
    (7, 3),
    (10, 3),
]


# ============================================================
# 1銘柄の売買シミュレーション
# ============================================================

def simulate_trade(
    row,
    take_profit,
    stop_loss,
):

    day_columns = [
        (
            "Day3",
            "Day3_from_entry",
        ),
        (
            "Day4",
            "Day4_from_entry",
        ),
        (
            "Day5",
            "Day5_from_entry",
        ),
    ]

    for day_name, return_column in day_columns:

        value = row[
            return_column
        ]

        # --------------------------------------------
        # 終値が利確ライン以上
        # --------------------------------------------

        if value >= take_profit:

            return {
                "exit_day":
                    day_name,

                "exit_reason":
                    "利確",

                # 終値判定なので、
                # 実際の終値収益率を採用する
                "exit_return":
                    value,
            }

        # --------------------------------------------
        # 終値が損切りライン以下
        # --------------------------------------------

        if value <= -stop_loss:

            return {
                "exit_day":
                    day_name,

                "exit_reason":
                    "損切り",

                "exit_return":
                    value,
            }

    # --------------------------------------------
    # どちらにも該当しなければDay5終値決済
    # --------------------------------------------

    return {
        "exit_day":
            "Day5",

        "exit_reason":
            "期限",

        "exit_return":
            row[
                "Day5_from_entry"
            ],
    }


# ============================================================
# ルール評価
# ============================================================

def evaluate_rule(
    target,
    take_profit,
    stop_loss,
):

    if target.empty:

        return {
            "件数": 0,
        }

    trade_results = []

    for _, row in target.iterrows():

        result = simulate_trade(
            row,
            take_profit,
            stop_loss,
        )

        trade_results.append(
            result
        )

    result_df = pd.DataFrame(
        trade_results
    )

    returns = result_df[
        "exit_return"
    ]

    win_rate = (
        (returns > 0).mean()
        * 100
    )

    profit_exit_rate = (
        (
            result_df[
                "exit_reason"
            ]
            == "利確"
        ).mean()
        * 100
    )

    stop_exit_rate = (
        (
            result_df[
                "exit_reason"
            ]
            == "損切り"
        ).mean()
        * 100
    )

    time_exit_rate = (
        (
            result_df[
                "exit_reason"
            ]
            == "期限"
        ).mean()
        * 100
    )

    return {
        "件数":
            len(result_df),

        "平均収益":
            returns.mean(),

        "収益中央値":
            returns.median(),

        "勝率":
            win_rate,

        "利確率":
            profit_exit_rate,

        "損切り率":
            stop_exit_rate,

        "期限決済率":
            time_exit_rate,

        "最大利益":
            returns.max(),

        "最大損失":
            returns.min(),
    }


# ============================================================
# 基本情報
# ============================================================

print()
print("==============================")
print(" P5 DAY2 EXIT RULE TEST")
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
    "基本候補 Day1>=3 / Day2>=3 :",
    len(candidate),
)

print(
    "強い候補 Day1>=4 / Day2>=4 :",
    len(strong_candidate),
)


# ============================================================
# 基本候補のルール比較
# ============================================================

print()
print("==============================")
print(" MAIN CANDIDATE EXIT RULES")
print(" Day1 >= 3% / Day2 >= 3%")
print("==============================")
print()


main_rows = []


for take_profit, stop_loss in EXIT_RULES:

    result = evaluate_rule(
        candidate,
        take_profit,
        stop_loss,
    )

    result[
        "ルール"
    ] = (
        f"+{take_profit}% / -{stop_loss}%"
    )

    main_rows.append(
        result
    )


main_summary = pd.DataFrame(
    main_rows
)


column_order = [
    "ルール",
    "件数",
    "平均収益",
    "収益中央値",
    "勝率",
    "利確率",
    "損切り率",
    "期限決済率",
    "最大利益",
    "最大損失",
]


main_summary = main_summary[
    column_order
]


print(
    main_summary
    .round(2)
    .to_string(
        index=False
    )
)


# ============================================================
# 強い候補のルール比較
# ============================================================

print()
print("==============================")
print(" STRONG CANDIDATE EXIT RULES")
print(" Day1 >= 4% / Day2 >= 4%")
print("==============================")
print()


strong_rows = []


for take_profit, stop_loss in EXIT_RULES:

    result = evaluate_rule(
        strong_candidate,
        take_profit,
        stop_loss,
    )

    result[
        "ルール"
    ] = (
        f"+{take_profit}% / -{stop_loss}%"
    )

    strong_rows.append(
        result
    )


strong_summary = pd.DataFrame(
    strong_rows
)


strong_summary = strong_summary[
    column_order
]


print(
    strong_summary
    .round(2)
    .to_string(
        index=False
    )
)


# ============================================================
# 個別シミュレーション
#
# 代表として
# +5%利確 / -3%損切り
# ============================================================

TAKE_PROFIT = 5
STOP_LOSS = 3


print()
print("==============================")
print(" INDIVIDUAL TRADES")
print(" Day1 >= 3% / Day2 >= 3%")
print(" TAKE +5% / STOP -3%")
print("==============================")
print()


detail_rows = []


for _, row in candidate.iterrows():

    result = simulate_trade(
        row,
        TAKE_PROFIT,
        STOP_LOSS,
    )

    detail_rows.append(
        {
            DATE_COL:
                row.get(
                    DATE_COL
                ),

            CODE_COL:
                row.get(
                    CODE_COL
                ),

            NAME_COL:
                row.get(
                    NAME_COL
                ),

            SCORE_COL:
                row.get(
                    SCORE_COL
                ),

            CHANGE5_COL:
                row.get(
                    CHANGE5_COL
                ),

            "VolumeRatio20":
                row.get(
                    "VolumeRatio20"
                ),

            "Day1":
                row[
                    "Day1"
                ],

            "Day2":
                row[
                    "Day2"
                ],

            "Day3実収益":
                row[
                    "Day3_from_entry"
                ],

            "Day4実収益":
                row[
                    "Day4_from_entry"
                ],

            "Day5実収益":
                row[
                    "Day5_from_entry"
                ],

            "決済日":
                result[
                    "exit_day"
                ],

            "決済理由":
                result[
                    "exit_reason"
                ],

            "決済収益":
                result[
                    "exit_return"
                ],
        }
    )


detail = pd.DataFrame(
    detail_rows
)


if detail.empty:

    print(
        "該当なし"
    )

else:

    print(
        detail
        .sort_values(
            "決済収益",
            ascending=False,
        )
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 参考
#
# 利確・損切りを使わずDay5まで保有
# ============================================================

print()
print("==============================")
print(" HOLD TO DAY5")
print("==============================")
print()


def print_hold_result(
    title,
    target,
):

    print(
        title
    )

    print(
        " 件数 :",
        len(target),
    )

    if target.empty:
        print()
        return

    returns = target[
        "Day5_from_entry"
    ]

    print(
        " 平均収益 :",
        round(
            returns.mean(),
            2,
        ),
        "%",
    )

    print(
        " 収益中央値 :",
        round(
            returns.median(),
            2,
        ),
        "%",
    )

    print(
        " 勝率 :",
        round(
            (
                returns > 0
            ).mean()
            * 100,
            2,
        ),
        "%",
    )

    print(
        " 最大利益 :",
        round(
            returns.max(),
            2,
        ),
        "%",
    )

    print(
        " 最大損失 :",
        round(
            returns.min(),
            2,
        ),
        "%",
    )

    print()


print_hold_result(
    "Day1>=3 / Day2>=3",
    candidate,
)


print_hold_result(
    "Day1>=4 / Day2>=4",
    strong_candidate,
)