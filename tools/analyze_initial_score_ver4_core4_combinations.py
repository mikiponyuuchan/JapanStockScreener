from pathlib import Path

import pandas as pd


INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_core4_analysis.csv"
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

    true_values = {
        "true",
        "1",
        "yes",
        "y",
        "on",
        "あり",
        "有",
        "○",
        "〇",
    }

    return values.isin(true_values)


def calc_stats(df, mask):
    subset = df.loc[mask].copy()
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
    print("=== 初動スコア Ver4 コア4条件 組み合わせ分析 ===")
    print("=" * 60)
    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLES}")

    if not INPUT_FILE.exists():
        print()
        print(f"ERROR: 入力ファイルがありません: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)

    print(f"検証記録数 : {len(df):,}")

    required_columns = [
        "ChangePercent",
        "VolumeRatio",
        "BreakoutSignal",
        "New30High",
        "Hit5",
        "Hit10",
        "Hit20",
        "5営業日以内最大騰落率",
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        print()
        print("ERROR: 必要な列がありません")
        for col in missing:
            print(f"  {col}")
        return

    # 数値化
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

    # ==========================================================
    # コア4条件
    # ==========================================================

    conditions = {
        "前日比+5%以上": df["ChangePercent"] >= 5,
        "出来高3倍以上": df["VolumeRatio"] >= 3,
        "ブレイク": df["BreakoutSignal"],
        "30日高値更新": df["New30High"],
    }

    print()
    print("=" * 60)
    print("=== コア4条件マスク ===")
    print("=" * 60)

    for name, mask in conditions.items():
        print(
            f"{name:25s} n={int(mask.sum()):5d}"
        )

    # 条件一致本数
    condition_df = pd.DataFrame(
        conditions,
        index=df.index,
    )

    df["コア4一致本数"] = condition_df.sum(axis=1)

    # ==========================================================
    # 全体基準
    # ==========================================================

    baseline = calc_stats(
        df,
        pd.Series(True, index=df.index),
    )

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print(f"全体件数       : {baseline['n']:,}")
    print(f"+5%率          : {baseline['+5%']:.1f}%")
    print(f"+10%率         : {baseline['+10%']:.1f}%")
    print(f"+20%率         : {baseline['+20%']:.1f}%")
    print(f"平均最大騰落率 : {baseline['平均最大']:+.2f}%")

    # ==========================================================
    # 一致本数別
    # ==========================================================

    print()
    print("=" * 60)
    print("=== コア4条件 一致本数別分析 ===")
    print("=" * 60)

    results = []

    for count in range(5):
        mask = df["コア4一致本数"] == count
        stats = calc_stats(df, mask)

        if stats["n"] < MIN_SAMPLES:
            continue

        composition = stats["n"] / len(df) * 100

        diff10 = stats["+10%"] - baseline["+10%"]
        diff20 = stats["+20%"] - baseline["+20%"]

        print(
            f"{count}本一致"
            f" / n={stats['n']:4d}"
            f" / 構成比={composition:5.2f}%"
            f" / +5%={stats['+5%']:5.1f}%"
            f" / +10%={stats['+10%']:5.1f}%"
            f" / +20%={stats['+20%']:5.1f}%"
            f" / +10%改善={diff10:+6.1f}pt"
            f" / +20%改善={diff20:+6.1f}pt"
            f" / 平均最大={stats['平均最大']:+.2f}%"
        )

        results.append({
            "一致本数": count,
            "件数": stats["n"],
            "構成比": composition,
            "+5%率": stats["+5%"],
            "+10%率": stats["+10%"],
            "+20%率": stats["+20%"],
            "+10%改善": diff10,
            "+20%改善": diff20,
            "平均最大騰落率": stats["平均最大"],
        })

    # ==========================================================
    # 3本一致の4パターン
    # ==========================================================

    print()
    print("=" * 60)
    print("=== 3本一致パターン ===")
    print("=" * 60)

    pattern_results = []

    condition_names = list(conditions.keys())

    for missing_condition in condition_names:
        selected_conditions = [
            name
            for name in condition_names
            if name != missing_condition
        ]

        mask = pd.Series(True, index=df.index)

        for name in selected_conditions:
            mask &= conditions[name]

        # 欠落条件は False
        mask &= ~conditions[missing_condition]

        stats = calc_stats(df, mask)

        if stats["n"] < MIN_SAMPLES:
            print(
                f"{' + '.join(selected_conditions):50s}"
                f" / n={stats['n']:3d}"
                f" / サンプル不足"
            )
            continue

        diff10 = stats["+10%"] - baseline["+10%"]
        diff20 = stats["+20%"] - baseline["+20%"]

        print(
            f"{' + '.join(selected_conditions):50s}"
            f" / n={stats['n']:3d}"
            f" / +10%={stats['+10%']:5.1f}%"
            f" / +20%={stats['+20%']:5.1f}%"
            f" / +10%改善={diff10:+6.1f}pt"
            f" / +20%改善={diff20:+6.1f}pt"
        )

        pattern_results.append({
            "パターン": " + ".join(selected_conditions),
            "欠落条件": missing_condition,
            "件数": stats["n"],
            "+5%率": stats["+5%"],
            "+10%率": stats["+10%"],
            "+20%率": stats["+20%"],
            "+10%改善": diff10,
            "+20%改善": diff20,
            "平均最大騰落率": stats["平均最大"],
        })

    # ==========================================================
    # 4本一致
    # ==========================================================

    four_mask = df["コア4一致本数"] == 4
    four = calc_stats(df, four_mask)

    print()
    print("=" * 60)
    print("=== 4本一致 ===")
    print("=" * 60)

    if four["n"] >= MIN_SAMPLES:
        print(
            f"4本一致"
            f" / n={four['n']}"
            f" / +5%={four['+5%']:.1f}%"
            f" / +10%={four['+10%']:.1f}%"
            f" / +20%={four['+20%']:.1f}%"
            f" / +10%改善={four['+10%'] - baseline['+10%']:+.1f}pt"
            f" / +20%改善={four['+20%'] - baseline['+20%']:+.1f}pt"
            f" / 平均最大={four['平均最大']:+.2f}%"
        )
    else:
        print(
            f"4本一致 / n={four['n']} / サンプル不足"
        )

    # ==========================================================
    # 3本以上
    # ==========================================================

    three_plus_mask = df["コア4一致本数"] >= 3
    three_plus = calc_stats(df, three_plus_mask)

    print()
    print("=" * 60)
    print("=== 3本以上 ===")
    print("=" * 60)

    if three_plus["n"] >= MIN_SAMPLES:
        print(
            f"3本以上"
            f" / n={three_plus['n']}"
            f" / +5%={three_plus['+5%']:.1f}%"
            f" / +10%={three_plus['+10%']:.1f}%"
            f" / +20%={three_plus['+20%']:.1f}%"
            f" / +10%改善={three_plus['+10%'] - baseline['+10%']:+.1f}pt"
            f" / +20%改善={three_plus['+20%'] - baseline['+20%']:+.1f}pt"
            f" / 平均最大={three_plus['平均最大']:+.2f}%"
        )

    # ==========================================================
    # 最終評価
    # ==========================================================

    print()
    print("=" * 60)
    print("=== コア4条件 最終評価 ===")
    print("=" * 60)

    if three_plus["n"] >= MIN_SAMPLES:
        print()
        print("【3本以上】")
        print(f"+10%率 : {three_plus['+10%']:.1f}%")
        print(f"+20%率 : {three_plus['+20%']:.1f}%")
        print(
            f"+20%改善 : "
            f"{three_plus['+20%'] - baseline['+20%']:+.1f}pt"
        )

    if four["n"] >= MIN_SAMPLES:
        print()
        print("【4本一致】")
        print(f"+10%率 : {four['+10%']:.1f}%")
        print(f"+20%率 : {four['+20%']:.1f}%")
        print(
            f"+20%改善 : "
            f"{four['+20%'] - baseline['+20%']:+.1f}pt"
        )

    # ==========================================================
    # 保存
    # ==========================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_df = pd.DataFrame(results)

    pattern_df = pd.DataFrame(pattern_results)

    if not pattern_df.empty:
        pattern_df.to_csv(
            OUTPUT_FILE.with_name(
                "initial_score_ver4_core4_3pattern_analysis.csv"
            ),
            index=False,
            encoding="utf-8-sig",
        )

    summary_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 60)
    print("=== 分析結果保存 ===")
    print("=" * 60)
    print(f"一致本数分析 : {OUTPUT_FILE}")
    print(
        "3本パターン分析 : "
        f"{OUTPUT_FILE.with_name('initial_score_ver4_core4_3pattern_analysis.csv')}"
    )

    print()
    print("=" * 60)
    print("=== 初動スコア Ver4 コア4条件分析完了 ===")
    print("=" * 60)
    print(f"検証記録数 : {len(df):,}")


if __name__ == "__main__":
    main()