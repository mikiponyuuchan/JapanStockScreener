from pathlib import Path

import numpy as np
import pandas as pd


INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_contribution_analysis.csv"
)

MIN_SAMPLES = 10


def to_bool_series(series):
    """
    各種形式の値を True / False に変換する。
    """
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
    """
    指定条件の成績を計算。
    """
    subset = df.loc[mask].copy()
    n = len(subset)

    if n == 0:
        return {
            "件数": 0,
            "+5%率": np.nan,
            "+10%率": np.nan,
            "+20%率": np.nan,
            "平均最大騰落率": np.nan,
        }

    return {
        "件数": n,
        "+5%率": subset["Hit5"].mean() * 100,
        "+10%率": subset["Hit10"].mean() * 100,
        "+20%率": subset["Hit20"].mean() * 100,
        "平均最大騰落率": subset["5営業日以内最大騰落率"].mean(),
    }


def prepare_conditions(df):
    """
    初動スコアVer4候補条件を作成する。

    条件は現在の raw データに存在する実列から直接生成する。
    """
    conditions = {}

    # --------------------------------------------------
    # 前日比
    # --------------------------------------------------
    change = pd.to_numeric(
        df["ChangePercent"],
        errors="coerce",
    )

    conditions["前日比+1%以上"] = change >= 1
    conditions["前日比+3%以上"] = change >= 3
    conditions["前日比+5%以上"] = change >= 5

    # --------------------------------------------------
    # 出来高
    # --------------------------------------------------
    volume_ratio = pd.to_numeric(
        df["VolumeRatio"],
        errors="coerce",
    )

    conditions["出来高1.5倍以上"] = volume_ratio >= 1.5
    conditions["出来高2倍以上"] = volume_ratio >= 2
    conditions["出来高3倍以上"] = volume_ratio >= 3

    # --------------------------------------------------
    # ブレイク
    # --------------------------------------------------
    conditions["ブレイク"] = to_bool_series(
        df["BreakoutSignal"]
    )

    conditions["ブレイク初日"] = to_bool_series(
        df["BreakoutFirstDay"]
    )

    # --------------------------------------------------
    # 高値更新
    # --------------------------------------------------
    conditions["30日高値更新"] = to_bool_series(
        df["New30High"]
    )

    # --------------------------------------------------
    # MA
    # --------------------------------------------------
    conditions["MA5上"] = to_bool_series(
        df["AboveMA5"]
    )

    conditions["MA25上"] = to_bool_series(
        df["AboveMA25"]
    )

    conditions["MA75上"] = to_bool_series(
        df["AboveMA75"]
    )

    # --------------------------------------------------
    # MACD
    # --------------------------------------------------
    conditions["MACD GC"] = to_bool_series(
        df["MACD_GC"]
    )

    return conditions


def print_stats(
    name,
    stats,
    baseline,
):
    """
    条件の成績を表示。
    """
    print(
        f"{name:25s}"
        f" n={stats['件数']:5d}"
        f" / 構成比={stats['件数'] / baseline['件数'] * 100:6.2f}%"
        f" / +5%={stats['+5%率']:5.1f}%"
        f" / +10%={stats['+10%率']:5.1f}%"
        f" / +20%={stats['+20%率']:5.1f}%"
        f" / +10%差={stats['+10%率'] - baseline['+10%率']:+6.1f}pt"
        f" / +20%差={stats['+20%率'] - baseline['+20%率']:+6.1f}pt"
        f" / 平均最大={stats['平均最大騰落率']:+6.2f}%"
    )


def main():
    print("=" * 60)
    print("=== 初動スコア Ver4 条件貢献度分析 ===")
    print("=" * 60)
    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLES}")

    if not INPUT_FILE.exists():
        print()
        print(f"ERROR: 入力ファイルがありません: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)

    print(f"検証記録数 : {len(df):,}")

    # --------------------------------------------------
    # 必須列確認
    # --------------------------------------------------
    required_columns = [
        "ChangePercent",
        "VolumeRatio",
        "BreakoutSignal",
        "BreakoutFirstDay",
        "New30High",
        "MACD_GC",
        "AboveMA5",
        "AboveMA25",
        "AboveMA75",
        "Hit5",
        "Hit10",
        "Hit20",
        "5営業日以内最大騰落率",
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        print()
        print("ERROR: 必要な列がありません")
        print(missing_columns)
        print()
        print("実際の列名:")
        for col in df.columns:
            print(f"  {col}")
        return

    # --------------------------------------------------
    # 結果列を正規化
    # --------------------------------------------------
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

    # --------------------------------------------------
    # 条件作成
    # --------------------------------------------------
    conditions = prepare_conditions(df)

    print()
    print("=" * 60)
    print("=== 条件マスク作成 ===")
    print("=" * 60)

    for name, mask in conditions.items():
        df[name] = mask.fillna(False)

        print(
            f"{name:25s}"
            f" n={int(df[name].sum()):5d}"
        )

    # --------------------------------------------------
    # 全体基準
    # --------------------------------------------------
    baseline_mask = pd.Series(
        True,
        index=df.index,
    )

    baseline = calc_stats(
        df,
        baseline_mask,
    )

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print(f"全体件数       : {baseline['件数']:,}")
    print(f"+5%率          : {baseline['+5%率']:.1f}%")
    print(f"+10%率         : {baseline['+10%率']:.1f}%")
    print(f"+20%率         : {baseline['+20%率']:.1f}%")
    print(
        f"平均最大騰落率 : "
        f"{baseline['平均最大騰落率']:+.2f}%"
    )

    # --------------------------------------------------
    # 条件別貢献度
    # --------------------------------------------------
    print()
    print("=" * 60)
    print("=== 各条件の貢献度 ===")
    print("=" * 60)

    results = []

    for name, mask in conditions.items():
        mask = mask.fillna(False)

        stats_true = calc_stats(
            df,
            mask,
        )

        stats_false = calc_stats(
            df,
            ~mask,
        )

        if stats_true["件数"] < MIN_SAMPLES:
            print(
                f"{name:25s}"
                f" → サンプル不足 "
                f"(n={stats_true['件数']})"
            )
            continue

        diff_10 = (
            stats_true["+10%率"]
            - stats_false["+10%率"]
        )

        diff_20 = (
            stats_true["+20%率"]
            - stats_false["+20%率"]
        )

        result = {
            "条件": name,
            "条件あり件数": stats_true["件数"],
            "条件なし件数": stats_false["件数"],
            "条件あり構成比": (
                stats_true["件数"]
                / baseline["件数"]
                * 100
            ),
            "条件あり+5%率": stats_true["+5%率"],
            "条件なし+5%率": stats_false["+5%率"],
            "条件あり+10%率": stats_true["+10%率"],
            "条件なし+10%率": stats_false["+10%率"],
            "条件あり+20%率": stats_true["+20%率"],
            "条件なし+20%率": stats_false["+20%率"],
            "+10%改善幅": diff_10,
            "+20%改善幅": diff_20,
            "条件あり平均最大騰落率": (
                stats_true["平均最大騰落率"]
            ),
            "条件なし平均最大騰落率": (
                stats_false["平均最大騰落率"]
            ),
            "平均最大騰落率差": (
                stats_true["平均最大騰落率"]
                - stats_false["平均最大騰落率"]
            ),
        }

        results.append(result)

        print_stats(
            name,
            stats_true,
            baseline,
        )

    result_df = pd.DataFrame(results)

    if result_df.empty:
        print()
        print("分析可能な条件がありません。")
        return

    # --------------------------------------------------
    # +20%予測力ランキング
    # --------------------------------------------------
    print()
    print("=" * 60)
    print("=== +20%予測力ランキング ===")
    print("=" * 60)

    ranking_20 = result_df.sort_values(
        "+20%改善幅",
        ascending=False,
    )

    for rank, (_, row) in enumerate(
        ranking_20.iterrows(),
        start=1,
    ):
        print(
            f"{rank:2d}. "
            f"{row['条件']:25s}"
            f" / +20%改善={row['+20%改善幅']:+6.1f}pt"
            f" / あり={row['条件あり+20%率']:5.1f}%"
            f" / なし={row['条件なし+20%率']:5.1f}%"
            f" / n={int(row['条件あり件数']):4d}"
        )

    # --------------------------------------------------
    # +10%予測力ランキング
    # --------------------------------------------------
    print()
    print("=" * 60)
    print("=== +10%予測力ランキング ===")
    print("=" * 60)

    ranking_10 = result_df.sort_values(
        "+10%改善幅",
        ascending=False,
    )

    for rank, (_, row) in enumerate(
        ranking_10.iterrows(),
        start=1,
    ):
        print(
            f"{rank:2d}. "
            f"{row['条件']:25s}"
            f" / +10%改善={row['+10%改善幅']:+6.1f}pt"
            f" / あり={row['条件あり+10%率']:5.1f}%"
            f" / なし={row['条件なし+10%率']:5.1f}%"
            f" / n={int(row['条件あり件数']):4d}"
        )

    # --------------------------------------------------
    # 重点条件
    # --------------------------------------------------
    print()
    print("=" * 60)
    print("=== 重点条件確認 ===")
    print("=" * 60)

    focus_conditions = [
        "前日比+5%以上",
        "出来高3倍以上",
        "ブレイク",
        "ブレイク初日",
        "30日高値更新",
        "MA5上",
        "MA25上",
        "MA75上",
        "MACD GC",
    ]

    for name in focus_conditions:
        row_df = result_df[
            result_df["条件"] == name
        ]

        if row_df.empty:
            continue

        row = row_df.iloc[0]

        print()
        print(name)
        print(
            f"  条件あり : n={int(row['条件あり件数'])}"
            f" / +10%={row['条件あり+10%率']:.1f}%"
            f" / +20%={row['条件あり+20%率']:.1f}%"
        )
        print(
            f"  条件なし : n={int(row['条件なし件数'])}"
            f" / +10%={row['条件なし+10%率']:.1f}%"
            f" / +20%={row['条件なし+20%率']:.1f}%"
        )
        print(
            f"  改善幅   : "
            f"+10% {row['+10%改善幅']:+.1f}pt"
            f" / +20% {row['+20%改善幅']:+.1f}pt"
        )

    # --------------------------------------------------
    # MACD GC判定
    # --------------------------------------------------
    print()
    print("=" * 60)
    print("=== MACD GC 判定 ===")
    print("=" * 60)

    macd_df = result_df[
        result_df["条件"] == "MACD GC"
    ]

    if not macd_df.empty:
        macd = macd_df.iloc[0]

        print(
            f"MACD GC"
            f" / n={int(macd['条件あり件数'])}"
            f" / +10%={macd['条件あり+10%率']:.1f}%"
            f" / +10%改善={macd['+10%改善幅']:+.1f}pt"
            f" / +20%={macd['条件あり+20%率']:.1f}%"
            f" / +20%改善={macd['+20%改善幅']:+.1f}pt"
        )

        if (
            macd["+10%改善幅"] <= 0
            and macd["+20%改善幅"] <= 0
        ):
            print()
            print(
                "判定: MACD GCは条件なしより予測力が高くない。"
            )
            print(
                "      初動スコアへの加点は削除候補。"
            )
        elif (
            macd["+10%改善幅"] < 2
            and macd["+20%改善幅"] < 2
        ):
            print()
            print(
                "判定: MACD GCの改善幅は小さい。"
            )
            print(
                "      初動スコアでは重要度を下げる候補。"
            )
        else:
            print()
            print(
                "判定: MACD GCには一定の予測力がある。"
            )

    # --------------------------------------------------
    # 総合評価
    # --------------------------------------------------
    result_df["総合改善"] = (
        result_df["+10%改善幅"]
        + result_df["+20%改善幅"]
    )

    print()
    print("=" * 60)
    print("=== 総合評価ランキング ===")
    print("=" * 60)

    overall = result_df.sort_values(
        "総合改善",
        ascending=False,
    )

    for rank, (_, row) in enumerate(
        overall.iterrows(),
        start=1,
    ):
        print(
            f"{rank:2d}. "
            f"{row['条件']:25s}"
            f" / 総合改善={row['総合改善']:+6.1f}pt"
            f" / +10%={row['+10%改善幅']:+6.1f}pt"
            f" / +20%={row['+20%改善幅']:+6.1f}pt"
        )

    # --------------------------------------------------
    # 保存
    # --------------------------------------------------
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_df = result_df.sort_values(
        "総合改善",
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
    print(f"保存先: {OUTPUT_FILE}")

    print()
    print("=" * 60)
    print("=== 初動スコア Ver4 条件貢献度分析完了 ===")
    print("=" * 60)
    print(f"検証記録数 : {len(df):,}")
    print(f"分析条件数 : {len(result_df)}")
    print(f"保存先     : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()