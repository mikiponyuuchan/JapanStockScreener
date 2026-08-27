from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ============================================================
# PATH
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from services.yahoo_service import _download_history_batch

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
# Day1-Day5完備
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
# 正式P5 段階条件
#
# Drop = Day2 - Day1
#
# 通常採用:
#   Drop >= -3.5
#
# 救済採用:
#   -5.0 <= Drop < -3.5
#   AND 5日騰落率 < 20
#   AND VolumeRatio20 < 3
#
# analyze_p5_high_low_exit.py と完全一致
# ============================================================

complete["Drop"] = (
    complete["Day2"]
    - complete["Day1"]
)


normal_keep = (
    complete["Drop"] >= -3.5
)


rescue_keep = (
    (complete["Drop"] >= -5.0)
    & (complete["Drop"] < -3.5)
    & (complete[CHANGE5_COL] < 20.0)
    & (complete["VolumeRatio20"] < 3.0)
)


candidate = complete[
    normal_keep
    | rescue_keep
].copy()

# ============================================================
# 日付・コード正規化
# ============================================================

candidate[DATE_COL] = pd.to_datetime(
    candidate[DATE_COL],
    errors="coerce",
).dt.normalize()


candidate[CODE_COL] = (
    candidate[CODE_COL]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
)


codes = sorted(
    candidate[CODE_COL]
    .dropna()
    .unique()
    .tolist()
)


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 30)
print(" P5 PARTIAL EXIT TEST")
print("=" * 30)
print()

print(
    f"全件数 : {len(df)}"
)

print(
    f"正式P5 : {len(p5)}"
)

print(
    f"Day1-Day5完備 : {len(complete)}"
)

print(
    f"段階条件通過 : {len(candidate)}"
)

print(
    f"取得対象コード数 : {len(codes)}"
)

print()


# ============================================================
# Yahoo OHLC
# ============================================================

print(
    "P5対象のOHLCをYahooから取得します..."
)

history_map = _download_history_batch(
    codes,
    period="1mo",
    batch_size=100,
)

print()

print(
    f"OHLC取得成功 : "
    f"{len(history_map)} / {len(codes)}"
)

print()


# ============================================================
# Day2終値・Day3～Day5 OHLC取得
# ============================================================

trade_rows = []


for _, row in candidate.iterrows():

    code = str(
        row[CODE_COL]
    )

    detection_date = row[DATE_COL]

    history = history_map.get(code)

    if (
        history is None
        or history.empty
        or pd.isna(detection_date)
    ):
        continue

    h = history.copy()

    h["Date"] = pd.to_datetime(
        h["Date"],
        errors="coerce",
    ).dt.normalize()

    h = (
        h
        .dropna(subset=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )

    # 検出日の位置
    positions = h.index[
        h["Date"] == detection_date
    ].tolist()

    if not positions:
        continue

    detection_pos = positions[-1]

    # Day2 = 検出日の2営業日後
    entry_pos = (
        detection_pos + 2
    )

    # Day3～Day5
    exit_positions = [
        detection_pos + 3,
        detection_pos + 4,
        detection_pos + 5,
    ]

    if (
        entry_pos >= len(h)
        or max(exit_positions) >= len(h)
    ):
        continue

    entry_price = pd.to_numeric(
        h.loc[
            entry_pos,
            "Close"
        ],
        errors="coerce",
    )

    if (
        pd.isna(entry_price)
        or entry_price <= 0
    ):
        continue

    record = {
        DATE_COL: detection_date,
        CODE_COL: code,
        NAME_COL: row.get(
            NAME_COL,
            "",
        ),
        SCORE_COL: row.get(
            SCORE_COL,
            np.nan,
        ),
        CHANGE5_COL: row.get(
            CHANGE5_COL,
            np.nan,
        ),
        "VolumeRatio20": row.get(
            "VolumeRatio20",
            np.nan,
        ),
        "Day1": row.get(
            "Day1",
            np.nan,
        ),
        "Day2": row.get(
            "Day2",
            np.nan,
        ),
        "Drop": row.get(
            "Drop",
            np.nan,
        ),
        "entry_price": float(
            entry_price
        ),
    }

    valid = True

    for day_number, pos in zip(
        [3, 4, 5],
        exit_positions,
    ):

        high_price = pd.to_numeric(
            h.loc[pos, "High"],
            errors="coerce",
        )

        low_price = pd.to_numeric(
            h.loc[pos, "Low"],
            errors="coerce",
        )

        close_price = pd.to_numeric(
            h.loc[pos, "Close"],
            errors="coerce",
        )

        if (
            pd.isna(high_price)
            or pd.isna(low_price)
            or pd.isna(close_price)
        ):
            valid = False
            break

        record[
            f"Day{day_number}_high_pct"
        ] = (
            high_price
            / entry_price
            - 1
        ) * 100

        record[
            f"Day{day_number}_low_pct"
        ] = (
            low_price
            / entry_price
            - 1
        ) * 100

        record[
            f"Day{day_number}_close_pct"
        ] = (
            close_price
            / entry_price
            - 1
        ) * 100

    if valid:
        trade_rows.append(record)


trades = pd.DataFrame(
    trade_rows
)


# ============================================================
# MATCH RESULT
# ============================================================

print("=" * 30)
print(" OHLC MATCH RESULT")
print("=" * 30)
print()

print(
    f"段階条件通過 : "
    f"{len(candidate)}"
)

print(
    f"High/Low評価可能 : "
    f"{len(trades)}"
)

print(
    f"High/Low不足 : "
    f"{len(candidate) - len(trades)}"
)

print()


if trades.empty:

    print(
        "評価可能なデータがありません。"
    )

    raise SystemExit


# ============================================================
# +5%初回到達日
# ============================================================

def first_hit_day(
    row,
    target=5.0,
):

    for day in [
        3,
        4,
        5,
    ]:

        high_pct = row[
            f"Day{day}_high_pct"
        ]

        if high_pct >= target:
            return day

    return None


trades["tp5_day"] = (
    trades.apply(
        first_hit_day,
        axis=1,
    )
)


hit5 = trades[
    trades["tp5_day"].notna()
].copy()


# ============================================================
# 戦略シミュレーション
#
# A : +5%で全売却
#
# B : +5%で50%利確
#     残り50%はDay5終値
#
# C : +5%で50%利確
#     残り50%は+10%狙い
#     +10%未到達ならDay5終値
#
# D : +5%で50%利確
#     残り50%は+10%狙い
#     建値まで下落したら撤退
#
# 注意:
# 同一日内で +10% と建値の両方に
# 到達した場合は順序不明。
# Dでは保守的に建値撤退として扱う。
# ============================================================

def simulate_after_tp5(
    row,
):

    hit_day = int(
        row["tp5_day"]
    )

    # ----------------------------------------
    # A
    # +5%全売却
    # ----------------------------------------

    strategy_a = 5.0

    # ----------------------------------------
    # B
    # 半分+5%、半分Day5終値
    # ----------------------------------------

    day5_close = row[
        "Day5_close_pct"
    ]

    strategy_b = (
        0.5 * 5.0
        + 0.5 * day5_close
    )

    # ----------------------------------------
    # C
    # 半分+5%
    # 残り+10%
    # 未到達ならDay5
    # ----------------------------------------

    second_c = None
    second_c_exit = None

    for day in range(
        hit_day,
        6,
    ):

        high_pct = row[
            f"Day{day}_high_pct"
        ]

        if high_pct >= 10.0:

            second_c = 10.0
            second_c_exit = (
                f"Day{day} +10%"
            )
            break

    if second_c is None:

        second_c = day5_close
        second_c_exit = (
            "Day5 Close"
        )

    strategy_c = (
        0.5 * 5.0
        + 0.5 * second_c
    )

    # ----------------------------------------
    # D
    # 半分+5%
    # 残り+10% / 建値撤退
    #
    # +5%初回到達日の「その後」の
    # intraday順序は分からないため、
    # 初回+5%到達日は建値判定しない。
    #
    # 翌営業日以降で
    # +10%と建値を判定する。
    #
    # 同一日に両方到達なら
    # 保守的に建値撤退。
    # ----------------------------------------

    second_d = None
    second_d_exit = None

    for day in range(
        hit_day + 1,
        6,
    ):

        high_pct = row[
            f"Day{day}_high_pct"
        ]

        low_pct = row[
            f"Day{day}_low_pct"
        ]

        hit10 = (
            high_pct >= 10.0
        )

        hit_break_even = (
            low_pct <= 0.0
        )

        if (
            hit10
            and hit_break_even
        ):

            second_d = 0.0
            second_d_exit = (
                f"Day{day} BOTH -> BE"
            )
            break

        if hit_break_even:

            second_d = 0.0
            second_d_exit = (
                f"Day{day} BE"
            )
            break

        if hit10:

            second_d = 10.0
            second_d_exit = (
                f"Day{day} +10%"
            )
            break

    if second_d is None:

        second_d = day5_close
        second_d_exit = (
            "Day5 Close"
        )

    strategy_d = (
        0.5 * 5.0
        + 0.5 * second_d
    )

    return pd.Series(
        {
            "A_full_tp5": strategy_a,
            "B_half_day5": strategy_b,
            "C_half_tp10": strategy_c,
            "D_half_tp10_be": strategy_d,
            "C_second_exit": second_c_exit,
            "D_second_exit": second_d_exit,
        }
    )


if not hit5.empty:

    simulation = (
        hit5.apply(
            simulate_after_tp5,
            axis=1,
        )
    )

    hit5 = pd.concat(
        [
            hit5,
            simulation,
        ],
        axis=1,
    )


# ============================================================
# +5%到達 PROFILE
# ============================================================

print("=" * 30)
print(" +5% HIT PROFILE")
print("=" * 30)
print()

print(
    f"評価件数 : {len(trades)}"
)

print(
    f"+5%到達件数 : "
    f"{len(hit5)}"
)

print(
    f"+5%到達率 : "
    f"{len(hit5) / len(trades) * 100:.2f} %"
)

print()


if hit5.empty:

    print(
        "+5%到達銘柄がありません。"
    )

    raise SystemExit


hit_day_counts = (
    hit5["tp5_day"]
    .value_counts()
    .sort_index()
)

print(
    "+5%初回到達日:"
)

for day, count in (
    hit_day_counts.items()
):

    print(
        f"Day{int(day)} : "
        f"{count} 件"
    )

print()


# ============================================================
# STRATEGY SUMMARY
# ============================================================

strategy_names = {
    "A_full_tp5":
        "+5%全売却",

    "B_half_day5":
        "50%+5% / 残りDay5",

    "C_half_tp10":
        "50%+5% / 残り+10%",

    "D_half_tp10_be":
        "50%+5% / 残り+10%・建値",
}


summary_rows = []


for column, label in (
    strategy_names.items()
):

    values = pd.to_numeric(
        hit5[column],
        errors="coerce",
    ).dropna()

    if values.empty:
        continue

    summary_rows.append(
        {
            "戦略": label,
            "件数": len(values),
            "平均収益": values.mean(),
            "収益中央値": values.median(),
            "勝率": (
                values.gt(0).mean()
                * 100
            ),
            "+5%以上率": (
                values.ge(5).mean()
                * 100
            ),
            "+7%以上率": (
                values.ge(7).mean()
                * 100
            ),
            "マイナス率": (
                values.lt(0).mean()
                * 100
            ),
            "最低収益": values.min(),
            "最高収益": values.max(),
        }
    )


summary = pd.DataFrame(
    summary_rows
)


print("=" * 30)
print(" STRATEGY COMPARISON")
print("=" * 30)
print()

print(
    summary.to_string(
        index=False,
        formatters={
            "平均収益":
                lambda x: f"{x:.2f}",
            "収益中央値":
                lambda x: f"{x:.2f}",
            "勝率":
                lambda x: f"{x:.2f}",
            "+5%以上率":
                lambda x: f"{x:.2f}",
            "+7%以上率":
                lambda x: f"{x:.2f}",
            "マイナス率":
                lambda x: f"{x:.2f}",
            "最低収益":
                lambda x: f"{x:.2f}",
            "最高収益":
                lambda x: f"{x:.2f}",
        }
    )
)

print()


# ============================================================
# SECOND HALF EXIT COUNTS
# ============================================================

print("=" * 30)
print(" SECOND HALF EXIT")
print("=" * 30)
print()

print(
    "50%+5% / 残り+10%:"
)

print(
    hit5[
        "C_second_exit"
    ]
    .value_counts()
    .to_string()
)

print()

print(
    "50%+5% / 残り+10%・建値:"
)

print(
    hit5[
        "D_second_exit"
    ]
    .value_counts()
    .to_string()
)

print()


# ============================================================
# DETAIL
# ============================================================

detail_columns = [
    DATE_COL,
    CODE_COL,
    NAME_COL,
    SCORE_COL,
    CHANGE5_COL,
    "VolumeRatio20",
    "Drop",
    "entry_price",
    "tp5_day",
    "Day3_high_pct",
    "Day3_low_pct",
    "Day4_high_pct",
    "Day4_low_pct",
    "Day5_high_pct",
    "Day5_low_pct",
    "Day5_close_pct",
    "A_full_tp5",
    "B_half_day5",
    "C_half_tp10",
    "D_half_tp10_be",
    "C_second_exit",
    "D_second_exit",
]


detail_columns = [
    column
    for column in detail_columns
    if column in hit5.columns
]


detail = (
    hit5[
        detail_columns
    ]
    .sort_values(
        "C_half_tp10",
        ascending=False,
    )
)


print("=" * 30)
print(" +5% HIT DETAILS")
print("=" * 30)
print()

print(
    detail.to_string(
        index=False
    )
)

print()


# ============================================================
# BIG WINNERS
#
# +10%以上まで伸びた銘柄
# ============================================================

hit5[
    "period_high_pct"
] = hit5[
    [
        "Day3_high_pct",
        "Day4_high_pct",
        "Day5_high_pct",
    ]
].max(
    axis=1
)


big_winners = (
    hit5[
        hit5[
            "period_high_pct"
        ] >= 10
    ]
    .copy()
    .sort_values(
        "period_high_pct",
        ascending=False,
    )
)


print("=" * 30)
print(" BIG WINNERS >= +10%")
print("=" * 30)
print()

if big_winners.empty:

    print(
        "該当なし"
    )

else:

    columns = [
        DATE_COL,
        CODE_COL,
        NAME_COL,
        "entry_price",
        "tp5_day",
        "period_high_pct",
        "Day5_close_pct",
        "B_half_day5",
        "C_half_tp10",
        "D_half_tp10_be",
        "D_second_exit",
    ]

    print(
        big_winners[
            columns
        ].to_string(
            index=False
        )
    )

print()


# ============================================================
# DONE
# ============================================================

print("=" * 30)
print(" DONE")
print("=" * 30)