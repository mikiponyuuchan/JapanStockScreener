from pathlib import Path

import numpy as np
import pandas as pd


INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_core4_missing_analysis.csv"
)

MIN_SAMPLES = 5


CORE_CONDITIONS = {
    "前日比+5%以上": "ChangePercent",
    "出来高3倍以上": "VolumeRatio",
    "ブレイク": "BreakoutSignal",
    "30日高値更新": "New30High",
}


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
        "あり",
        "有",
        "○",
        "〇",
    }

    return values.isin(true_values)


def calc_stats(df):
    n = len(df)

    if n == 0:
        return {
            "n": 0,
            "+5%": np.nan,
            "+10%": np.nan,
            "+20%": np.nan,
            "平均最大騰落率": np.nan,
        }

    return {
        "n": n,
        "+5%": df["Hit5"].mean() * 100,
        "+10%": df["Hit10"].mean() * 100,
        "+20%": df["Hit20"].mean() * 100,
        "平均最大騰落率": pd.to_numeric(
            df["5営業日以内最大騰落率"],
            errors="coerce",
        ).mean(),
    }


def print_stats(label, stats):
    print(
        f"{label}"
        f" / n={stats['n']:4d}"
        f" / +5%={stats['+5%']:5.1f}%"
        f" / +10%={stats['+10%']:5.1f}%"
        f" / +20%={stats['+20%']:5.1f}%"
        f" / 平均最大={stats['平均最大騰落率']:+6.2f}%"
    )


def main():
    print("=" * 60)
    print("=== 初動スコア Ver4 コア4条件 欠落条件分析 ===")
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
        print(missing)
        print()
        print("実際の列名:")
        for col in df.columns:
            print(f"  {col}")
        return

    # ==========================================================
    # 条件マスク作成
    # ==========================================================

    df["前日比+5%以上"] = (
        pd.to_numeric(
            df["ChangePercent"],
            errors="coerce",
        ).fillna(0) >= 5
    )

    df["出来高3倍以上"] = (
        pd.to_numeric(
            df["VolumeRatio"],
            errors="coerce",
        ).fillna(0) >= 3
    )

    df["ブレイク"] = to_bool_series(
        df["BreakoutSignal"]
    )

    df["30日高値更新"] = to_bool_series(
        df["New30High"]
    )

    df["Hit5"] = to_bool_series(df["Hit5"])
    df["Hit10"] = to_bool_series(df["Hit10"])
    df["Hit20"] = to_bool_series(df["Hit20"])

    df["5営業日以内最大騰落率"] = pd.to_numeric(
        df["5営業日以内最大騰落率"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["5営業日以内最大騰落率"]
    ).copy()

    print()
    print("=" * 60)
    print("=== コア4条件件数 ===")
    print("=" * 60)

    for name in CORE_CONDITIONS:
        print(
            f"{name:20s}"
            f" n={int(df[name].sum()):5d}"
        )

    # ==========================================================
    # 全体基準
    # ==========================================================

    baseline = calc_stats(df)

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print_stats("全体", baseline)

    # ==========================================================
    # 3本一致だけを抽出
    # ==========================================================

    condition_names = list(CORE_CONDITIONS.keys())

    df["一致本数"] = df[condition_names].sum(axis=1)

    three_df = df[df["一致本数"] == 3].copy()

    print()
    print("=" * 60)
    print("=== 3本一致 ===")
    print("=" * 60)

    print_stats("3本一致", calc_stats(three_df))

    # ==========================================================
    # 欠落条件別分析
    # ==========================================================

    print()
    print("=" * 60)
    print("=== 欠落条件別分析 ===")
    print("=" * 60)

    results = []

    for missing_condition in condition_names:

        present_conditions = [
            name
            for name in condition_names
            if name != missing_condition
        ]

        mask = pd.Series(
            True,
            index=df.index,
        )

        for condition in present_conditions:
            mask &= df[condition]

        # 欠落条件がFalseであることを明示
        mask &= ~df[missing_condition]

        subset = df.loc[mask].copy()

        stats = calc_stats(subset)

        print()
        print(
            f"【{missing_condition}が欠落】"
        )

        print(
            "成立条件 : "
            + " + ".join(present_conditions)
        )

        print_stats(
            "3本一致",
            stats,
        )

        if stats["n"] < MIN_SAMPLES:
            print(
                f"  ※ サンプル不足 n={stats['n']}"
            )

        results.append(
            {
                "欠落条件": missing_condition,
                "成立条件": " + ".join(
                    present_conditions
                ),
                "n": stats["n"],
                "+5%率": stats["+5%"],
                "+10%率": stats["+10%"],
                "+20%率": stats["+20%"],
                "平均最大騰落率": stats[
                    "平均最大騰落率"
                ],
                "+10%全体差": (
                    stats["+10%"]
                    - baseline["+10%"]
                ),
                "+20%全体差": (
                    stats["+20%"]
                    - baseline["+20%"]
                ),
            }
        )

    result_df = pd.DataFrame(results)

    # ==========================================================
    # 欠落条件ランキング
    # ==========================================================

    valid_df = result_df[
        result_df["n"] >= MIN_SAMPLES
    ].copy()

    print()
    print("=" * 60)
    print("=== 欠落条件 +20%率ランキング ===")
    print("=" * 60)

    ranking_20 = valid_df.sort_values(
        "+20%率",
        ascending=False,
    )

    for rank, (_, row) in enumerate(
        ranking_20.iterrows(),
        start=1,
    ):
        print(
            f"{rank}. "
            f"{row['欠落条件']:20s}"
            f" / n={int(row['n']):4d}"
            f" / +10%={row['+10%率']:5.1f}%"
            f" / +20%={row['+20%率']:5.1f}%"
            f" / +20%差={row['+20%全体差']:+5.1f}pt"
        )

    print()
    print("=" * 60)
    print("=== 欠落条件 +10%率ランキング ===")
    print("=" * 60)

    ranking_10 = valid_df.sort_values(
        "+10%率",
        ascending=False,
    )

    for rank, (_, row) in enumerate(
        ranking_10.iterrows(),
        start=1,
    ):
        print(
            f"{rank}. "
            f"{row['欠落条件']:20s}"
            f" / n={int(row['n']):4d}"
            f" / +10%={row['+10%率']:5.1f}%"
            f" / +20%={row['+20%率']:5.1f}%"
            f" / +10%差={row['+10%全体差']:+5.1f}pt"
        )

    # ==========================================================
    # 条件ごとの重要度評価
    # ==========================================================

    print()
    print("=" * 60)
    print("=== コア4条件 重要度評価 ===")
    print("=" * 60)

    for _, row in ranking_20.iterrows():
        print(
            f"{row['欠落条件']:20s}"
            f" / 3本一致時 +20%={row['+20%率']:5.1f}%"
            f" / 全体差={row['+20%全体差']:+5.1f}pt"
            f" / n={int(row['n']):4d}"
        )

    # ==========================================================
    # 参考：各3本パターン
    # ==========================================================

    print()
    print("=" * 60)
    print("=== 3本一致パターン詳細 ===")
    print("=" * 60)

    pattern_results = []

    for missing_condition in condition_names:

        present_conditions = [
            name
            for name in condition_names
            if name != missing_condition
        ]

        mask = pd.Series(
            True,
            index=df.index,
        )

        for condition in present_conditions:
            mask &= df[condition]

        mask &= ~df[missing_condition]

        subset = df.loc[mask].copy()

        stats = calc_stats(subset)

        pattern_results.append(
            {
                "欠落条件": missing_condition,
                "成立条件": " + ".join(
                    present_conditions
                ),
                "n": stats["n"],
                "+5%率": stats["+5%"],
                "+10%率": stats["+10%"],
                "+20%率": stats["+20%"],
                "平均最大騰落率": stats[
                    "平均最大騰落率"
                ],
            }
        )

        print(
            f"{missing_condition}欠落"
            f" / n={stats['n']:4d}"
            f" / +5%={stats['+5%']:5.1f}%"
            f" / +10%={stats['+10%']:5.1f}%"
            f" / +20%={stats['+20%']:5.1f}%"
            f" / 平均最大={stats['平均最大騰落率']:+6.2f}%"
        )

    # ==========================================================
    # 保存
    # ==========================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_df = result_df.sort_values(
        "+20%率",
        ascending=False,
    )

    save_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 60)
    print("=== 分析結果保存 ===")
    print("=" * 60)

    print(
        f"保存先: {OUTPUT_FILE}"
    )

    print()
    print("=" * 60)
    print("=== 初動スコア Ver4 コア4条件 欠落分析完了 ===")
    print("=" * 60)

    print(
        f"検証記録数 : {len(df):,}"
    )
    print(
        f"3本一致件数 : {len(three_df):,}"
    )
    print(
        f"分析条件数 : {len(result_df)}"
    )
    print(
        f"保存先     : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()