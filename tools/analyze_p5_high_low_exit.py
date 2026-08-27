from pathlib import Path
import sys

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

AVOID_COLUMNS = [
    "A_STALL",
    "C_SPIKE",
    "D_OVERHEAT",
    "F_DECEL",
]


# ============================================================
# EXIT RULES
#
# take profit %, stop loss %
# ============================================================

EXIT_RULES = [
    (3, 2),
    (3, 3),
    (5, 2),
    (5, 3),
    (5, 5),
    (7, 3),
    (7, 5),
    (10, 3),
    (10, 5),
]


# ============================================================
# LOAD PANEL
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig",
    low_memory=False,
)


numeric_columns = [
    SCORE_COL,
    CHANGE5_COL,
    VOLUME_COL,
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
# DAY1-DAY5 COMPLETE
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
# DROP
# ============================================================

complete["Drop"] = (
    complete["Day2"]
    - complete["Day1"]
)


# ============================================================
# FIXED STEP FILTER
#
# Keep:
#   Drop >= -3.5
#
# Rescue:
#   -5 <= Drop < -3.5
#   AND 5-day change < 20
#   AND VolumeRatio20 < 3
# ============================================================

normal_keep = (
    complete["Drop"] >= -3.5
)


rescue_keep = (
    (complete["Drop"] >= -5.0)
    & (complete["Drop"] < -3.5)
    & (complete[CHANGE5_COL] < 20.0)
    & (complete[VOLUME_COL] < 3.0)
)


candidate = complete[
    normal_keep
    | rescue_keep
].copy()


# ============================================================
# CODE NORMALIZATION
# ============================================================

candidate[CODE_COL] = (
    candidate[CODE_COL]
    .astype(str)
    .str.strip()
)


codes = (
    candidate[CODE_COL]
    .dropna()
    .unique()
    .tolist()
)


# ============================================================
# HEADER
# ============================================================

print()
print("==============================")
print(" P5 HIGH / LOW EXIT TEST")
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
    "段階条件通過 :",
    len(candidate),
)

print(
    "取得対象コード数 :",
    len(codes),
)

print()


# ============================================================
# YAHOO OHLC DOWNLOAD
#
# Only P5 candidates.
# 1 month is enough for current Aug 2026 sample.
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
    "OHLC取得成功 :",
    len(history_map),
    "/",
    len(codes),
)

print()


# ============================================================
# PREPARE ONE TRADE
#
# Detection date = Day0
# Next trading row = Day1
# Second trading row = Day2 entry
# Day3-Day5 = exit evaluation
# ============================================================

def prepare_trade(row):

    code = str(
        row[CODE_COL]
    )

    detect_date = pd.Timestamp(
        row[DATE_COL]
    ).normalize()

    history = history_map.get(
        code
    )

    if history is None or history.empty:
        return None

    history = history.copy()

    history["Date"] = pd.to_datetime(
        history["Date"],
        errors="coerce",
    )

    if (
        getattr(
            history["Date"].dt,
            "tz",
            None,
        )
        is not None
    ):

        history["Date"] = (
            history["Date"]
            .dt
            .tz_localize(None)
        )

    history["Date"] = (
        history["Date"]
        .dt
        .normalize()
    )

    history = (
        history
        .dropna(
            subset=[
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )
        .sort_values("Date")
        .drop_duplicates(
            subset=["Date"],
            keep="last",
        )
    )

    # Detection day itself is Day0.
    # We need five subsequent trading sessions.
    future = history[
        history["Date"] > detect_date
    ].copy()

    if len(future) < 5:
        return None

    future = (
        future
        .head(5)
        .reset_index(drop=True)
    )

    day1 = future.iloc[0]
    day2 = future.iloc[1]
    day3 = future.iloc[2]
    day4 = future.iloc[3]
    day5 = future.iloc[4]

    entry_price = float(
        day2["Close"]
    )

    if entry_price <= 0:
        return None

    result = {
        DATE_COL:
            row[DATE_COL],

        CODE_COL:
            code,

        NAME_COL:
            row.get(
                NAME_COL,
                "",
            ),

        SCORE_COL:
            row[SCORE_COL],

        CHANGE5_COL:
            row[CHANGE5_COL],

        VOLUME_COL:
            row[VOLUME_COL],

        "Day1":
            row["Day1"],

        "Day2":
            row["Day2"],

        "Drop":
            row["Drop"],

        "Day2_date":
            day2["Date"],

        "entry_price":
            entry_price,
    }

    for index, day_row in [
        (3, day3),
        (4, day4),
        (5, day5),
    ]:

        result[
            f"Day{index}_date"
        ] = day_row["Date"]

        result[
            f"Day{index}_open"
        ] = float(
            day_row["Open"]
        )

        result[
            f"Day{index}_high"
        ] = float(
            day_row["High"]
        )

        result[
            f"Day{index}_low"
        ] = float(
            day_row["Low"]
        )

        result[
            f"Day{index}_close"
        ] = float(
            day_row["Close"]
        )

        result[
            f"Day{index}_high_pct"
        ] = (
            float(day_row["High"])
            / entry_price
            - 1.0
        ) * 100.0

        result[
            f"Day{index}_low_pct"
        ] = (
            float(day_row["Low"])
            / entry_price
            - 1.0
        ) * 100.0

        result[
            f"Day{index}_close_pct"
        ] = (
            float(day_row["Close"])
            / entry_price
            - 1.0
        ) * 100.0

    result[
        "period_high_pct"
    ] = max(
        result["Day3_high_pct"],
        result["Day4_high_pct"],
        result["Day5_high_pct"],
    )

    result[
        "period_low_pct"
    ] = min(
        result["Day3_low_pct"],
        result["Day4_low_pct"],
        result["Day5_low_pct"],
    )

    result[
        "Day5_close_pct"
    ] = result[
        "Day5_close_pct"
    ]

    return result


# ============================================================
# BUILD OHLC TRADE PANEL
# ============================================================

trade_rows = []

missing_rows = []


for _, row in candidate.iterrows():

    trade = prepare_trade(
        row
    )

    if trade is None:

        missing_rows.append(
            {
                DATE_COL:
                    row[DATE_COL],

                CODE_COL:
                    row[CODE_COL],

                NAME_COL:
                    row.get(
                        NAME_COL,
                        "",
                    ),
            }
        )

        continue

    trade_rows.append(
        trade
    )


trades = pd.DataFrame(
    trade_rows
)


print("==============================")
print(" OHLC MATCH RESULT")
print("==============================")
print()

print(
    "段階条件通過 :",
    len(candidate),
)

print(
    "High/Low評価可能 :",
    len(trades),
)

print(
    "High/Low不足 :",
    len(missing_rows),
)

print()


if trades.empty:

    print(
        "ERROR : High/Low評価可能銘柄がありません"
    )

    raise SystemExit(1)


# ============================================================
# BASIC HIGH / LOW PROFILE
# ============================================================

print("==============================")
print(" HIGH / LOW PROFILE")
print("==============================")
print()

print(
    "期間内高値中央値 :",
    round(
        trades[
            "period_high_pct"
        ].median(),
        2,
    ),
    "%",
)

print(
    "期間内安値中央値 :",
    round(
        trades[
            "period_low_pct"
        ].median(),
        2,
    ),
    "%",
)

print(
    "Day5終値中央値 :",
    round(
        trades[
            "Day5_close_pct"
        ].median(),
        2,
    ),
    "%",
)

for target in [
    3,
    5,
    7,
    10,
]:

    rate = (
        trades[
            "period_high_pct"
        ]
        >= target
    ).mean() * 100

    print(
        f"+{target}% High到達率 :",
        round(
            rate,
            2,
        ),
        "%",
    )


for stop in [
    2,
    3,
    5,
]:

    rate = (
        trades[
            "period_low_pct"
        ]
        <= -stop
    ).mean() * 100

    print(
        f"-{stop}% Low到達率 :",
        round(
            rate,
            2,
        ),
        "%",
    )


# ============================================================
# SIMULATE TP / SL
#
# Daily OHLC cannot tell which came first
# when BOTH levels are touched on same day.
#
# Such cases are classified as AMBIGUOUS.
# ============================================================

def simulate_trade(
    row,
    take_profit,
    stop_loss,
):

    tp_level = float(
        take_profit
    )

    sl_level = -float(
        stop_loss
    )

    for day in [
        3,
        4,
        5,
    ]:

        high_pct = row[
            f"Day{day}_high_pct"
        ]

        low_pct = row[
            f"Day{day}_low_pct"
        ]

        tp_hit = (
            high_pct >= tp_level
        )

        sl_hit = (
            low_pct <= sl_level
        )

        if tp_hit and sl_hit:

            return {
                "exit_day":
                    f"Day{day}",

                "exit_type":
                    "同日両到達",

                "exit_return":
                    None,
            }

        if tp_hit:

            return {
                "exit_day":
                    f"Day{day}",

                "exit_type":
                    "利確",

                "exit_return":
                    tp_level,
            }

        if sl_hit:

            return {
                "exit_day":
                    f"Day{day}",

                "exit_type":
                    "損切り",

                "exit_return":
                    sl_level,
            }

    return {
        "exit_day":
            "Day5",

        "exit_type":
            "期限",

        "exit_return":
            float(
                row[
                    "Day5_close_pct"
                ]
            ),
    }


# ============================================================
# EXIT RULE SUMMARY
# ============================================================

print()
print("==============================")
print(" HIGH / LOW EXIT RULES")
print("==============================")
print()


summary_rows = []


for take_profit, stop_loss in EXIT_RULES:

    simulations = []

    for _, row in trades.iterrows():

        result = simulate_trade(
            row,
            take_profit,
            stop_loss,
        )

        simulations.append(
            result
        )

    sim_df = pd.DataFrame(
        simulations
    )

    ambiguous = (
        sim_df["exit_type"]
        == "同日両到達"
    )

    resolved = sim_df[
        ~ambiguous
    ].copy()

    returns = pd.to_numeric(
        resolved[
            "exit_return"
        ],
        errors="coerce",
    )

    summary_rows.append(
        {
            "ルール":
                (
                    f"+{take_profit}%"
                    f" / -{stop_loss}%"
                ),

            "件数":
                len(sim_df),

            "判定可能":
                len(resolved),

            "同日両到達":
                int(
                    ambiguous.sum()
                ),

            "同日両到達率":
                (
                    ambiguous.mean()
                    * 100
                ),

            "利確率":
                (
                    (
                        resolved[
                            "exit_type"
                        ]
                        == "利確"
                    ).mean()
                    * 100
                    if len(resolved) > 0
                    else float("nan")
                ),

            "損切り率":
                (
                    (
                        resolved[
                            "exit_type"
                        ]
                        == "損切り"
                    ).mean()
                    * 100
                    if len(resolved) > 0
                    else float("nan")
                ),

            "期限率":
                (
                    (
                        resolved[
                            "exit_type"
                        ]
                        == "期限"
                    ).mean()
                    * 100
                    if len(resolved) > 0
                    else float("nan")
                ),

            "平均収益":
                returns.mean(),

            "収益中央値":
                returns.median(),

            "勝率":
                (
                    (returns > 0)
                    .mean()
                    * 100
                    if len(returns) > 0
                    else float("nan")
                ),
        }
    )


summary = pd.DataFrame(
    summary_rows
)


numeric_cols = summary.select_dtypes(
    include="number"
).columns

summary[numeric_cols] = (
    summary[
        numeric_cols
    ]
    .round(2)
)


print(
    summary.to_string(
        index=False,
    )
)


# ============================================================
# AMBIGUOUS DETAILS
# ============================================================

print()
print("==============================")
print(" SAME-DAY BOTH-HIT DETAILS")
print("==============================")
print()


ambiguous_detail_rows = []


for take_profit, stop_loss in EXIT_RULES:

    for _, row in trades.iterrows():

        result = simulate_trade(
            row,
            take_profit,
            stop_loss,
        )

        if (
            result["exit_type"]
            != "同日両到達"
        ):
            continue

        day = result["exit_day"]

        ambiguous_detail_rows.append(
            {
                "ルール":
                    (
                        f"+{take_profit}%"
                        f" / -{stop_loss}%"
                    ),

                DATE_COL:
                    row[DATE_COL],

                CODE_COL:
                    row[CODE_COL],

                NAME_COL:
                    row[NAME_COL],

                "決済候補日":
                    day,

                "entry_price":
                    row["entry_price"],

                "High%":
                    row[
                        f"{day}_high_pct"
                    ],

                "Low%":
                    row[
                        f"{day}_low_pct"
                    ],
            }
        )


ambiguous_details = pd.DataFrame(
    ambiguous_detail_rows
)


if ambiguous_details.empty:

    print(
        "同日両到達なし"
    )

else:

    numeric_cols = (
        ambiguous_details
        .select_dtypes(
            include="number"
        )
        .columns
    )

    ambiguous_details[
        numeric_cols
    ] = (
        ambiguous_details[
            numeric_cols
        ]
        .round(2)
    )

    print(
        ambiguous_details
        .to_string(
            index=False,
        )
    )


# ============================================================
# MISSING DETAILS
# ============================================================

print()
print("==============================")
print(" HIGH / LOW MISSING")
print("==============================")
print()

if not missing_rows:

    print(
        "不足なし"
    )

else:

    missing_df = pd.DataFrame(
        missing_rows
    )

    print(
        missing_df.to_string(
            index=False,
        )
    )


# ============================================================
# SAMPLE TRADE DATA
# ============================================================

print()
print("==============================")
print(" TRADE SAMPLE")
print("==============================")
print()

display_columns = [
    DATE_COL,
    CODE_COL,
    NAME_COL,
    SCORE_COL,
    CHANGE5_COL,
    VOLUME_COL,
    "Drop",
    "entry_price",
    "Day3_high_pct",
    "Day3_low_pct",
    "Day4_high_pct",
    "Day4_low_pct",
    "Day5_high_pct",
    "Day5_low_pct",
    "Day5_close_pct",
    "period_high_pct",
    "period_low_pct",
]

display_columns = [
    column
    for column in display_columns
    if column in trades.columns
]

sample = trades[
    display_columns
].copy()

numeric_cols = sample.select_dtypes(
    include="number"
).columns

sample[numeric_cols] = (
    sample[
        numeric_cols
    ]
    .round(2)
)


print(
    sample
    .sort_values(
        "period_high_pct",
        ascending=False,
    )
    .to_string(
        index=False,
    )
)


print()
print("==============================")
print(" DONE")
print("==============================")