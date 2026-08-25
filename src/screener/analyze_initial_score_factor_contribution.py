from pathlib import Path
from itertools import combinations

import pandas as pd
import numpy as np


# ============================================================
# 設定
# ============================================================

INPUT_FILE = Path(
    "data/tracking/initial_score_factor_raw.csv"
)

OUTPUT_FILE = Path(
    "data/tracking/initial_score_factor_contribution_analysis.csv"
)

MIN_SAMPLE = 30

# 初動条件
CONDITIONS = {
    "出来高1.5倍以上": lambda df: df["VolumeRatio"] >= 1.5,
    "出来高2倍以上": lambda df: df["VolumeRatio"] >= 2.0,
    "出来高3倍以上": lambda df: df["VolumeRatio"] >= 3.0,

    "出来高増加1日": lambda df: df["VolumeIncreaseDays"] >= 1,
    "出来高増加2日": lambda df: df["VolumeIncreaseDays"] >= 2,
    "出来高増加3日": lambda df: df["VolumeIncreaseDays"] >= 3,

    "前日比+1%以上": lambda df: df["ChangePercent"] >= 1.0,
    "前日比+3%以上": lambda df: df["ChangePercent"] >= 3.0,
    "前日比+5%以上": lambda df: df["ChangePercent"] >= 5.0,

    "ブレイク": lambda df: df["BreakoutSignal"] == True,
    "ブレイク初日": lambda df: df["BreakoutFirstDay"] == True,

    "30日高値更新": lambda df: df["New30High"] == True,

    "MACD GC": lambda df: df["MACD_GC"] == True,

    "MA5上": lambda df: df["AboveMA5"] == True,
    "MA25上": lambda df: df["AboveMA25"] == True,
    "MA75上": lambda df: df["AboveMA75"] == True,

    "RSI70未満": lambda df: df["RSI"] < 70,
    "RSI80未満": lambda df: df["RSI"] < 80,
    "RSI90未満": lambda df: df["RSI"] < 90,
}


# ============================================================
# 補助関数
# ============================================================

def pct(value):
    """割合を%表示用に変換"""
    if pd.isna(value):
        return 0.0
    return float(value) * 100.0


def safe_bool_series(series):
    """
    True / False / 1 / 0 / NaN を安全にboolへ変換
    """
    if series.dtype == bool:
        return series.fillna(False)

    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float) != 0

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(
            [
                "true",
                "1",
                "yes",
                "y",
                "t",
                "○",
                "〇",
            ]
        )
    )


def calculate_stats(df, mask, total_10_rate, total_20_rate):
    """
    条件成立銘柄の成績を計算
    """

    subset = df.loc[mask]

    n = len(subset)

    if n == 0:
        return None

    hit5_rate = subset["Hit5"].mean()
    hit10_rate = subset["Hit10"].mean()
    hit20_rate = subset["Hit20"].mean()

    avg_max = subset["5営業日以内最大騰落率"].mean()
    median_max = subset["5営業日以内最大騰落率"].median()

    return {
        "n": n,

        "Hit5率": pct(hit5_rate),

        "+10%率": pct(hit10_rate),
        "+10%差": pct(hit10_rate) - total_10_rate,

        "+20%率": pct(hit20_rate),
        "+20%差": pct(hit20_rate) - total_20_rate,

        "平均最大騰落率": avg_max,
        "中央値最大騰落率": median_max,

        "Hit10件数": int(subset["Hit10"].sum()),
        "Hit20件数": int(subset["Hit20"].sum()),
    }


# ============================================================
# メイン
# ============================================================

def main():

    print("=" * 60)
    print("=== 初動スコア・条件別貢献度分析 ===")
    print("=" * 60)

    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLE}")

    # --------------------------------------------------------
    # CSV読込
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        print()
        print("ERROR:")
        print(f"入力ファイルがありません: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)

    print()
    print(f"検証記録数 : {len(df):,}")

    # --------------------------------------------------------
    # 必須列確認
    # --------------------------------------------------------

    required_columns = [
        "VolumeRatio",
        "VolumeIncreaseDays",
        "ChangePercent",
        "RSI",
        "BreakoutSignal",
        "BreakoutFirstDay",
        "New30High",
        "MACD_GC",
        "AboveMA5",
        "AboveMA25",
        "AboveMA75",
        "5営業日以内最大騰落率",
        "Hit5",
        "Hit10",
        "Hit20",
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        print()
        print("ERROR: 必須列がありません")
        for col in missing:
            print(f"  - {col}")
        return

    # --------------------------------------------------------
    # 数値列
    # --------------------------------------------------------

    numeric_columns = [
        "VolumeRatio",
        "VolumeIncreaseDays",
        "ChangePercent",
        "Change5Days",
        "Change20Days",
        "RSI",
        "5営業日以内最大騰落率",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    # --------------------------------------------------------
    # Bool列
    # --------------------------------------------------------

    bool_columns = [
        "BreakoutSignal",
        "BreakoutFirstDay",
        "New30High",
        "NewYearHigh",
        "MACD_GC",
        "AboveMA5",
        "AboveMA25",
        "AboveMA75",
        "Hit5",
        "Hit10",
        "Hit20",
    ]

    for col in bool_columns:
        if col in df.columns:
            df[col] = safe_bool_series(df[col])

    # --------------------------------------------------------
    # 全体基準
    # --------------------------------------------------------

    total_n = len(df)

    total_hit5 = df["Hit5"].mean()
    total_hit10 = df["Hit10"].mean()
    total_hit20 = df["Hit20"].mean()

    total_10_rate = pct(total_hit10)
    total_20_rate = pct(total_hit20)

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print(f"全体件数       : {total_n:,}")
    print(f"+5%率          : {pct(total_hit5):.1f}%")
    print(f"+10%率         : {total_10_rate:.1f}%")
    print(f"+20%率         : {total_20_rate:.1f}%")
    print(
        f"平均最大騰落率 : "
        f"{df['5営業日以内最大騰落率'].mean():+.2f}%"
    )

    # --------------------------------------------------------
    # 条件マスク作成
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 条件マスク作成 ===")
    print("=" * 60)

    masks = {}

    for name, func in CONDITIONS.items():

        try:
            mask = func(df)
            mask = mask.fillna(False)

            masks[name] = mask

            print(
                f"{name:<24} "
                f"n={int(mask.sum()):,}"
            )

        except Exception as e:

            print(
                f"{name:<24} "
                f"ERROR: {e}"
            )

    # --------------------------------------------------------
    # 単独条件分析
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 単独条件分析 ===")
    print("=" * 60)

    results = []

    for name, mask in masks.items():

        stats = calculate_stats(
            df,
            mask,
            total_10_rate,
            total_20_rate,
        )

        if stats is None:
            continue

        if stats["n"] < MIN_SAMPLE:
            continue

        stats["条件数"] = 1
        stats["条件"] = name

        results.append(stats)

    # --------------------------------------------------------
    # 単独条件ランキング
    # --------------------------------------------------------

    single_df = pd.DataFrame(results)

    if not single_df.empty:

        single_df = single_df.sort_values(
            [
                "+10%差",
                "+20%差",
                "n",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        )

        print()
        print("=== 単独条件 +10%率ランキング ===")

        for _, row in single_df.head(30).iterrows():

            print(
                f"n={int(row['n']):4d} / "
                f"+10%率={row['+10%率']:.1f}% / "
                f"差={row['+10%差']:+.1f}pt / "
                f"+20%率={row['+20%率']:.1f}% / "
                f"平均最大={row['平均最大騰落率']:+.2f}% / "
                f"{row['条件']}"
            )

    # --------------------------------------------------------
    # 条件を含むケース分析
    #
    # 「その条件が入った組み合わせ」が
    # 全体としてどれだけ強いかを見る
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 条件の組み合わせ貢献度分析 ===")
    print("=" * 60)

    combination_results = []

    condition_names = list(masks.keys())

    # 最大4条件
    for r in range(2, 5):

        print()
        print(
            f"--- {r}条件組み合わせ ---"
        )

        count = 0

        for combo in combinations(
            condition_names,
            r,
        ):

            mask = masks[combo[0]].copy()

            for name in combo[1:]:
                mask &= masks[name]

            n = int(mask.sum())

            if n < MIN_SAMPLE:
                continue

            stats = calculate_stats(
                df,
                mask,
                total_10_rate,
                total_20_rate,
            )

            if stats is None:
                continue

            stats["条件数"] = r
            stats["条件"] = " + ".join(combo)

            # 各条件を含む組み合わせであることを記録
            for name in condition_names:
                stats[f"含む_{name}"] = (
                    name in combo
                )

            combination_results.append(stats)

            count += 1

        print(
            f"{r}条件 有効組み合わせ : "
            f"{count:,}"
        )

    # --------------------------------------------------------
    # DataFrame化
    # --------------------------------------------------------

    combo_df = pd.DataFrame(
        combination_results
    )

    if combo_df.empty:

        print()
        print("有効な組み合わせがありません。")
        return

    # --------------------------------------------------------
    # 条件ごとの「含まれる組み合わせ」の平均成績
    # --------------------------------------------------------

    contribution_results = []

    for name in condition_names:

        column = f"含む_{name}"

        if column not in combo_df.columns:
            continue

        subset = combo_df[
            combo_df[column] == True
        ].copy()

        if subset.empty:
            continue

        # 条件を含まない同条件数の組み合わせ
        without = combo_df[
            (
                combo_df["条件数"]
                == subset["条件数"].mode().iloc[0]
            )
            &
            (
                combo_df[column] == False
            )
        ].copy()

        contribution_results.append(
            {
                "条件": name,

                "組み合わせ数":
                    len(subset),

                "平均n":
                    subset["n"].mean(),

                "平均+10%率":
                    subset["+10%率"].mean(),

                "平均+10%差":
                    subset["+10%差"].mean(),

                "最高+10%率":
                    subset["+10%率"].max(),

                "平均+20%率":
                    subset["+20%率"].mean(),

                "平均+20%差":
                    subset["+20%差"].mean(),

                "最高+20%率":
                    subset["+20%率"].max(),

                "平均最大騰落率":
                    subset["平均最大騰落率"].mean(),

                "中央値最大騰落率":
                    subset["中央値最大騰落率"].mean(),
            }
        )

    contribution_df = pd.DataFrame(
        contribution_results
    )

    # --------------------------------------------------------
    # 貢献度ランキング
    # --------------------------------------------------------

    contribution_df = contribution_df.sort_values(
        [
            "平均+10%差",
            "平均+20%差",
            "平均最大騰落率",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    )

    print()
    print("=" * 60)
    print("=== 条件別・組み合わせ貢献度ランキング ===")
    print("=" * 60)

    for _, row in contribution_df.head(30).iterrows():

        print(
            f"{row['条件']:<24} "
            f"組合せ={int(row['組み合わせ数']):4d} / "
            f"平均+10%差={row['平均+10%差']:+.2f}pt / "
            f"平均+20%差={row['平均+20%差']:+.2f}pt / "
            f"平均最大={row['平均最大騰落率']:+.2f}%"
        )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 単独条件
    single_save = single_df.copy()

    if not single_save.empty:
        single_save["分析種別"] = "単独条件"

    # 貢献度
    contribution_save = contribution_df.copy()

    if not contribution_save.empty:
        contribution_save["分析種別"] = "組み合わせ貢献度"

    # 結合
    save_frames = []

    if not single_save.empty:
        save_frames.append(single_save)

    if not contribution_save.empty:
        save_frames.append(contribution_save)

    if save_frames:

        final_df = pd.concat(
            save_frames,
            ignore_index=True,
            sort=False,
        )

        final_df.to_csv(
            OUTPUT_FILE,
            index=False,
            encoding="utf-8-sig",
        )

    # --------------------------------------------------------
    # 最終表示
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 初動条件・貢献度分析完了 ===")
    print("=" * 60)

    print(
        f"検証記録数 : {len(df):,}"
    )

    print(
        f"全体+10%率 : {total_10_rate:.1f}%"
    )

    print(
        f"全体+20%率 : {total_20_rate:.1f}%"
    )

    print(
        f"有効単独条件 : {len(single_df):,}"
    )

    print(
        f"有効組み合わせ : {len(combo_df):,}"
    )

    print(
        f"保存先 : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()