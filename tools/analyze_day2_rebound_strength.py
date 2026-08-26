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

OUTPUT_SUMMARY_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "day2_rebound_strength_summary.csv"
)

OUTPUT_DETAILS_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "day2_rebound_strength_details.csv"
)


# ============================================================
# 設定
# ============================================================

REBOUND_THRESHOLDS = [
    1.0,
    2.0,
    3.0,
    5.0,
]

DAY2_THRESHOLDS = [
    -5.0,
    -3.0,
    0.0,
]


# ============================================================
# 共通
# ============================================================

def print_separator(width=150):
    print("=" * width)


def safe_rate(series, condition):
    if len(series) == 0:
        return np.nan

    return round(
        (condition.sum() / len(series)) * 100,
        2,
    )


def make_summary(name, df):
    """
    Day2でエントリーしたと仮定し、
    Day3～Day5の3営業日を評価する。
    """

    work = df.copy()

    valid = work[
        [
            "Day2",
            "Day3",
            "Day4",
            "Day5",
        ]
    ].notna().all(axis=1)

    confirmed = work.loc[valid].copy()

    if confirmed.empty:
        return {
            "条件": name,
            "候補数": len(work),
            "3日評価有効件数": 0,
            "Max3平均": np.nan,
            "Max3中央値": np.nan,
            "Min3平均": np.nan,
            "Min3中央値": np.nan,
            "+3%到達率": np.nan,
            "+5%到達率": np.nan,
            "+10%到達率": np.nan,
            "+20%到達率": np.nan,
            "-3%逆行率": np.nan,
            "-5%逆行率": np.nan,
            "-10%逆行率": np.nan,
        }

    # --------------------------------------------------------
    # Day2終値で買った場合の
    # Day3～Day5リターンへ変換
    #
    # DayN は検出日終値を基準にした騰落率なので、
    #
    # (1 + DayN / 100)
    # ---------------- - 1
    # (1 + Day2 / 100)
    #
    # でDay2買い基準に変換する。
    # --------------------------------------------------------

    base = 1.0 + confirmed["Day2"] / 100.0

    for day in [3, 4, 5]:
        confirmed[f"Entry_Day{day}"] = (
            (
                (1.0 + confirmed[f"Day{day}"] / 100.0)
                / base
                - 1.0
            )
            * 100.0
        )

    entry_cols = [
        "Entry_Day3",
        "Entry_Day4",
        "Entry_Day5",
    ]

    confirmed["EntryMax3"] = (
        confirmed[entry_cols]
        .max(axis=1)
    )

    confirmed["EntryMin3"] = (
        confirmed[entry_cols]
        .min(axis=1)
    )

    max3 = confirmed["EntryMax3"]
    min3 = confirmed["EntryMin3"]

    return {
        "条件": name,
        "候補数": len(work),
        "3日評価有効件数": len(confirmed),

        "Max3平均": round(max3.mean(), 2),
        "Max3中央値": round(max3.median(), 2),

        "Min3平均": round(min3.mean(), 2),
        "Min3中央値": round(min3.median(), 2),

        "+3%到達率": safe_rate(
            max3,
            max3 >= 3,
        ),

        "+5%到達率": safe_rate(
            max3,
            max3 >= 5,
        ),

        "+10%到達率": safe_rate(
            max3,
            max3 >= 10,
        ),

        "+20%到達率": safe_rate(
            max3,
            max3 >= 20,
        ),

        "-3%逆行率": safe_rate(
            min3,
            min3 <= -3,
        ),

        "-5%逆行率": safe_rate(
            min3,
            min3 <= -5,
        ),

        "-10%逆行率": safe_rate(
            min3,
            min3 <= -10,
        ),
    }


def add_entry_returns(df):
    """
    詳細保存用にDay2買い後のリターンを追加。
    """

    work = df.copy()

    base = 1.0 + work["Day2"] / 100.0

    for day in [3, 4, 5]:
        work[f"Entry_Day{day}"] = (
            (
                (1.0 + work[f"Day{day}"] / 100.0)
                / base
                - 1.0
            )
            * 100.0
        )

    entry_cols = [
        "Entry_Day3",
        "Entry_Day4",
        "Entry_Day5",
    ]

    complete = (
        work[entry_cols]
        .notna()
        .all(axis=1)
    )

    work["EntryMax3"] = np.nan
    work["EntryMin3"] = np.nan

    work.loc[
        complete,
        "EntryMax3"
    ] = (
        work.loc[
            complete,
            entry_cols
        ]
        .max(axis=1)
    )

    work.loc[
        complete,
        "EntryMin3"
    ] = (
        work.loc[
            complete,
            entry_cols
        ]
        .min(axis=1)
    )

    return work


# ============================================================
# P5基本条件
# ============================================================

def make_e_basic_mask(df):
    """
    P5基本

    初動スコア 3～4
    5日騰落率 > 0
    VolumeRatio20 > 1
    危険回避4条件なし

    H2は危険回避から除外。
    """

    danger = (
        df["A_STALL"].fillna(False).astype(bool)
        | df["C_SPIKE"].fillna(False).astype(bool)
        | df["D_OVERHEAT"].fillna(False).astype(bool)
        | df["F_DECEL"].fillna(False).astype(bool)
    )

    return (
        df["初動スコア"].between(
            3,
            4,
            inclusive="both",
        )
        & (df["5日騰落率"] > 0)
        & (df["VolumeRatio20"] > 1)
        & (~danger)
    )


# ============================================================
# メイン
# ============================================================

def main():

    print()
    print_separator()
    print("早期買い候補 Day2反発強度クロステスト")
    print_separator()
    print()

    # --------------------------------------------------------
    # 読込
    # --------------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        low_memory=False,
    )

    print("読込 :", INPUT_FILE)
    print("行数 :", len(df))

    # --------------------------------------------------------
    # 数値化
    # --------------------------------------------------------

    numeric_columns = [
        "初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    # --------------------------------------------------------
    # P5基本
    # --------------------------------------------------------

    e_mask = make_e_basic_mask(df)

    e = df.loc[e_mask].copy()

    print()
    print_separator()
    print("P5基本")
    print_separator()

    print("P5基本件数       :", len(e))

    # --------------------------------------------------------
    # Day1 < 0
    # --------------------------------------------------------

    base = e[
        e["Day1"].notna()
        & e["Day2"].notna()
        & (e["Day1"] < 0)
    ].copy()

    base["反発幅"] = (
        base["Day2"]
        - base["Day1"]
    )

    print("Day1 < 0 件数  :", len(base))

    if not base.empty:
        print(
            "反発幅平均      :",
            round(
                base["反発幅"].mean(),
                2,
            ),
        )

        print(
            "反発幅中央値    :",
            round(
                base["反発幅"].median(),
                2,
            ),
        )

    # --------------------------------------------------------
    # クロステスト
    # --------------------------------------------------------

    summaries = []
    detail_frames = []

    for rebound_threshold in REBOUND_THRESHOLDS:

        for day2_threshold in DAY2_THRESHOLDS:

            mask = (
                (base["反発幅"] >= rebound_threshold)
                & (base["Day2"] >= day2_threshold)
            )

            part = base.loc[mask].copy()

            condition_name = (
                f"反発幅>={rebound_threshold:g}%"
                f" × Day2>={day2_threshold:g}%"
            )

            summary = make_summary(
                condition_name,
                part,
            )

            summary["反発幅閾値"] = rebound_threshold
            summary["Day2閾値"] = day2_threshold

            summaries.append(summary)

            if not part.empty:

                detail = add_entry_returns(part)

                detail["条件"] = condition_name
                detail["反発幅閾値"] = rebound_threshold
                detail["Day2閾値"] = day2_threshold

                detail_frames.append(detail)

    summary_df = pd.DataFrame(summaries)

    column_order = [
        "条件",
        "反発幅閾値",
        "Day2閾値",
        "候補数",
        "3日評価有効件数",
        "Max3平均",
        "Max3中央値",
        "Min3平均",
        "Min3中央値",
        "+3%到達率",
        "+5%到達率",
        "+10%到達率",
        "+20%到達率",
        "-3%逆行率",
        "-5%逆行率",
        "-10%逆行率",
    ]

    summary_df = summary_df[column_order]

    # --------------------------------------------------------
    # 表示
    # --------------------------------------------------------

    print()
    print_separator(180)
    print("Day2反発強度 クロス結果")
    print_separator(180)

    print(
        summary_df.to_string(
            index=False,
        )
    )

    # --------------------------------------------------------
    # 実用候補
    #
    # 少なすぎる条件を上位にしないため
    # 3日評価有効件数 >= 5 を暫定基準とする。
    # --------------------------------------------------------

    practical = summary_df[
        summary_df[
            "3日評価有効件数"
        ] >= 5
    ].copy()

    practical = practical.sort_values(
        [
            "+10%到達率",
            "+5%到達率",
            "-5%逆行率",
            "3日評価有効件数",
        ],
        ascending=[
            False,
            False,
            True,
            False,
        ],
    )

    print()
    print_separator(180)
    print("実用候補")
    print_separator(180)

    if practical.empty:
        print("該当なし")
    else:
        print(
            practical.to_string(
                index=False,
            )
        )

    # --------------------------------------------------------
    # 詳細結合
    # --------------------------------------------------------

    if detail_frames:
        details_df = pd.concat(
            detail_frames,
            ignore_index=True,
        )
    else:
        details_df = pd.DataFrame()

    # --------------------------------------------------------
    # +10%以上成功
    # --------------------------------------------------------

    print()
    print_separator()
    print(
        "Day2反発確認後に買い、"
        "その後3営業日で+10%以上となった候補"
    )
    print_separator()

    if not details_df.empty:

        success = details_df[
            details_df["EntryMax3"] >= 10
        ].copy()

        show_columns = [
            "条件",
            "検出日",
            "コード",
            "銘柄名",
            "初動スコア",
            "前日比",
            "5日騰落率",
            "VolumeRatio20",
            "Day1",
            "Day2",
            "反発幅",
            "Day3",
            "Day4",
            "Day5",
            "EntryMax3",
            "EntryMin3",
        ]

        if success.empty:
            print("該当なし")
        else:
            print(
                success[
                    show_columns
                ]
                .sort_values(
                    "EntryMax3",
                    ascending=False,
                )
                .to_string(
                    index=False,
                )
            )

    else:
        print("該当なし")

    # --------------------------------------------------------
    # -5%以上逆行
    # --------------------------------------------------------

    print()
    print_separator()
    print(
        "Day2反発確認後に買ったが、"
        "その後-5%以上逆行した候補"
    )
    print_separator()

    if not details_df.empty:

        failure = details_df[
            details_df["EntryMin3"] <= -5
        ].copy()

        show_columns = [
            "条件",
            "検出日",
            "コード",
            "銘柄名",
            "初動スコア",
            "前日比",
            "5日騰落率",
            "VolumeRatio20",
            "Day1",
            "Day2",
            "反発幅",
            "Day3",
            "Day4",
            "Day5",
            "EntryMax3",
            "EntryMin3",
        ]

        if failure.empty:
            print("該当なし")
        else:
            print(
                failure[
                    show_columns
                ]
                .sort_values(
                    "EntryMin3",
                    ascending=True,
                )
                .to_string(
                    index=False,
                )
            )

    else:
        print("該当なし")

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    summary_df.to_csv(
        OUTPUT_SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    details_df.to_csv(
        OUTPUT_DETAILS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print_separator()
    print("集計保存 :", OUTPUT_SUMMARY_FILE)
    print("詳細保存 :", OUTPUT_DETAILS_FILE)
    print_separator()


if __name__ == "__main__":
    main()
