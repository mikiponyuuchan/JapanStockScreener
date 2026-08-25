from pathlib import Path

import pandas as pd


INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_core4_3pattern_exact.csv"
)

MIN_SAMPLES = 5


def to_bool_series(series):
    if series.dtype == bool:
        return series.fillna(False)

    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0) != 0

    values = (
        series.astype(str)
        .str.strip()
        .str.lower()
    )

    return values.isin({
        "true",
        "1",
        "yes",
        "y",
        "on",
        "あり",
        "有",
        "○",
        "〇",
    })


def calc_stats(df, mask):
    subset = df.loc[mask]

    n = len(subset)

    if n == 0:
        return {
            "n": 0,
            "+5%": float("nan"),
            "+10%": float("nan"),
            "+20%": float("nan"),
            "平均最大": float("nan"),
        }

    return {
        "n": n,
        "+5%": subset["Hit5"].mean() * 100,
        "+10%": subset["Hit10"].mean() * 100,
        "+20%": subset["Hit20"].mean() * 100,
        "平均最大": subset["5営業日以内最大騰落率"].mean(),
    }


def main():

    print("=" * 60)
    print("=== 初動スコア Ver4 コア4条件 3本一致厳密分析 ===")
    print("=" * 60)

    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLES}")

    if not INPUT_FILE.exists():
        print()
        print(f"ERROR: 入力ファイルがありません: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)

    print(f"検証記録数 : {len(df):,}")

    required = [
        "ChangePercent",
        "VolumeRatio",
        "BreakoutSignal",
        "New30High",
        "Hit5",
        "Hit10",
        "Hit20",
        "5営業日以内最大騰落率",
    ]

    missing = [col for col in required if col not in df.columns]

    if missing:
        print()
        print("ERROR: 必要な列がありません")

        for col in missing:
            print(f"  {col}")

        return

    # ----------------------------------------------------------
    # データ型変換
    # ----------------------------------------------------------

    df["ChangePercent"] = pd.to_numeric(
        df["ChangePercent"],
        errors="coerce",
    )

    df["VolumeRatio"] = pd.to_numeric(
        df["VolumeRatio"],
        errors="coerce",
    )

    df["5営業日以内最大騰落率"] = pd.to_numeric(
        df["5営業日以内最大騰落率"],
        errors="coerce",
    )

    df["Hit5"] = to_bool_series(df["Hit5"])
    df["Hit10"] = to_bool_series(df["Hit10"])
    df["Hit20"] = to_bool_series(df["Hit20"])

    df["BreakoutSignal"] = to_bool_series(
        df["BreakoutSignal"]
    )

    df["New30High"] = to_bool_series(
        df["New30High"]
    )

    df = df.dropna(
        subset=[
            "ChangePercent",
            "VolumeRatio",
            "5営業日以内最大騰落率",
        ]
    ).copy()

    # ----------------------------------------------------------
    # コア4条件
    # ----------------------------------------------------------

    df["前日比+5%以上"] = (
        df["ChangePercent"] >= 5
    )

    df["出来高3倍以上"] = (
        df["VolumeRatio"] >= 3
    )

    df["ブレイク"] = (
        df["BreakoutSignal"]
    )

    df["30日高値更新"] = (
        df["New30High"]
    )

    condition_names = [
        "前日比+5%以上",
        "出来高3倍以上",
        "ブレイク",
        "30日高値更新",
    ]

    # ----------------------------------------------------------
    # 一致本数
    # ----------------------------------------------------------

    df["一致本数"] = df[
        condition_names
    ].sum(axis=1)

    # ----------------------------------------------------------
    # 全体基準
    # ----------------------------------------------------------

    baseline = calc_stats(
        df,
        pd.Series(True, index=df.index),
    )

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print(
        f"全体 / n={baseline['n']}"
        f" / +5%={baseline['+5%']:.1f}%"
        f" / +10%={baseline['+10%']:.1f}%"
        f" / +20%={baseline['+20%']:.1f}%"
        f" / 平均最大={baseline['平均最大']:+.2f}%"
    )

    # ----------------------------------------------------------
    # 一致本数確認
    # ----------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 一致本数確認 ===")
    print("=" * 60)

    count_results = []

    for count in range(5):

        mask = df["一致本数"] == count
        stats = calc_stats(df, mask)

        print(
            f"{count}本一致"
            f" / n={stats['n']:4d}"
            f" / +10%={stats['+10%']:5.1f}%"
            f" / +20%={stats['+20%']:5.1f}%"
        )

        count_results.append({
            "一致本数": count,
            "件数": stats["n"],
            "+5%率": stats["+5%"],
            "+10%率": stats["+10%"],
            "+20%率": stats["+20%"],
            "平均最大騰落率": stats["平均最大"],
        })

    # ----------------------------------------------------------
    # 3本一致の厳密分類
    # ----------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 3本一致 厳密分類 ===")
    print("=" * 60)

    patterns = [
        (
            "①前日比+5% + ②出来高3倍 + ③ブレイク",
            ["前日比+5%以上", "出来高3倍以上", "ブレイク"],
            "30日高値更新",
        ),
        (
            "①前日比+5% + ②出来高3倍 + ④30日高値",
            ["前日比+5%以上", "出来高3倍以上", "30日高値更新"],
            "ブレイク",
        ),
        (
            "①前日比+5% + ③ブレイク + ④30日高値",
            ["前日比+5%以上", "ブレイク", "30日高値更新"],
            "出来高3倍以上",
        ),
        (
            "②出来高3倍 + ③ブレイク + ④30日高値",
            ["出来高3倍以上", "ブレイク", "30日高値更新"],
            "前日比+5%以上",
        ),
    ]

    pattern_results = []

    total_three = 0

    for title, required_conditions, missing_condition in patterns:

        mask = (
            df["一致本数"] == 3
        )

        for condition in required_conditions:
            mask &= df[condition]

        # 重要：
        # 欠落条件がFalseであることを明示
        mask &= ~df[missing_condition]

        stats = calc_stats(df, mask)

        total_three += stats["n"]

        diff10 = stats["+10%"] - baseline["+10%"]
        diff20 = stats["+20%"] - baseline["+20%"]

        print()
        print(title)
        print(
            f"欠落条件 : {missing_condition}"
        )
        print(
            f"n={stats['n']:4d}"
            f" / +5%={stats['+5%']:5.1f}%"
            f" / +10%={stats['+10%']:5.1f}%"
            f" / +20%={stats['+20%']:5.1f}%"
            f" / +10%改善={diff10:+6.1f}pt"
            f" / +20%改善={diff20:+6.1f}pt"
            f" / 平均最大={stats['平均最大']:+.2f}%"
        )

        pattern_results.append({
            "パターン": title,
            "欠落条件": missing_condition,
            "件数": stats["n"],
            "+5%率": stats["+5%"],
            "+10%率": stats["+10%"],
            "+20%率": stats["+20%"],
            "+10%改善": diff10,
            "+20%改善": diff20,
            "平均最大騰落率": stats["平均最大"],
        })

    # ----------------------------------------------------------
    # 3本一致合計チェック
    # ----------------------------------------------------------

    actual_three = int(
        (df["一致本数"] == 3).sum()
    )

    print()
    print("=" * 60)
    print("=== 3本一致 件数整合性チェック ===")
    print("=" * 60)

    print(
        f"一致本数=3 の実件数 : {actual_three}"
    )

    print(
        f"4パターン合計       : {total_three}"
    )

    if actual_three == total_three:
        print()
        print("OK: 4パターンの合計と3本一致件数が一致")
    else:
        print()
        print("ERROR: 件数が一致していません")

    # ----------------------------------------------------------
    # 4本一致
    # ----------------------------------------------------------

    four_mask = df["一致本数"] == 4
    four = calc_stats(df, four_mask)

    print()
    print("=" * 60)
    print("=== 4本一致 ===")
    print("=" * 60)

    print(
        f"4本一致"
        f" / n={four['n']}"
        f" / +5%={four['+5%']:.1f}%"
        f" / +10%={four['+10%']:.1f}%"
        f" / +20%={four['+20%']:.1f}%"
        f" / +10%改善="
        f"{four['+10%'] - baseline['+10%']:+.1f}pt"
        f" / +20%改善="
        f"{four['+20%'] - baseline['+20%']:+.1f}pt"
        f" / 平均最大={four['平均最大']:+.2f}%"
    )

    # ----------------------------------------------------------
    # 3本以上
    # ----------------------------------------------------------

    three_plus = calc_stats(
        df,
        df["一致本数"] >= 3,
    )

    print()
    print("=" * 60)
    print("=== 3本以上 ===")
    print("=" * 60)

    print(
        f"3本以上"
        f" / n={three_plus['n']}"
        f" / +10%={three_plus['+10%']:.1f}%"
        f" / +20%={three_plus['+20%']:.1f}%"
        f" / +20%改善="
        f"{three_plus['+20%'] - baseline['+20%']:+.1f}pt"
    )

    # ----------------------------------------------------------
    # 保存
    # ----------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pattern_df = pd.DataFrame(
        pattern_results
    )

    pattern_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    count_file = OUTPUT_FILE.with_name(
        "initial_score_ver4_core4_count_analysis.csv"
    )

    pd.DataFrame(
        count_results
    ).to_csv(
        count_file,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 60)
    print("=== 分析結果保存 ===")
    print("=" * 60)

    print(
        f"3本パターン : {OUTPUT_FILE}"
    )

    print(
        f"一致本数分析 : {count_file}"
    )

    print()
    print("=" * 60)
    print("=== 分析完了 ===")
    print("=" * 60)


if __name__ == "__main__":
    main()