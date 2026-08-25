from pathlib import Path
import itertools

import numpy as np
import pandas as pd


INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_increment_analysis.csv"
)

MIN_SAMPLES = 10


# ============================================================
# 共通処理
# ============================================================

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
    }

    return values.isin(true_values)


def calc_stats(df, mask):
    subset = df.loc[mask]

    n = len(subset)

    if n == 0:
        return {
            "n": 0,
            "+5%": np.nan,
            "+10%": np.nan,
            "+20%": np.nan,
            "平均最大": np.nan,
        }

    return {
        "n": n,
        "+5%": subset["Hit5"].mean() * 100,
        "+10%": subset["Hit10"].mean() * 100,
        "+20%": subset["Hit20"].mean() * 100,
        "平均最大": subset["5営業日以内最大騰落率"].mean(),
    }


def add_condition_columns(df):
    """
    初動スコアVer4で検討している条件を作成。
    """

    conditions = {}

    # --------------------------------------------------------
    # 前日比
    # --------------------------------------------------------

    conditions["前日比+1%以上"] = df["ChangePercent"] >= 1
    conditions["前日比+3%以上"] = df["ChangePercent"] >= 3
    conditions["前日比+5%以上"] = df["ChangePercent"] >= 5

    # --------------------------------------------------------
    # 出来高
    # --------------------------------------------------------

    conditions["出来高1.5倍以上"] = df["VolumeRatio"] >= 1.5
    conditions["出来高2倍以上"] = df["VolumeRatio"] >= 2
    conditions["出来高3倍以上"] = df["VolumeRatio"] >= 3

    # --------------------------------------------------------
    # ブレイク系
    # --------------------------------------------------------

    conditions["ブレイク"] = to_bool_series(
        df["BreakoutSignal"]
    )

    conditions["ブレイク初日"] = to_bool_series(
        df["BreakoutFirstDay"]
    )

    # --------------------------------------------------------
    # 高値更新
    # --------------------------------------------------------

    conditions["30日高値更新"] = to_bool_series(
        df["New30High"]
    )

    # --------------------------------------------------------
    # MA系
    # --------------------------------------------------------

    conditions["MA5上"] = to_bool_series(
        df["AboveMA5"]
    )

    conditions["MA25上"] = to_bool_series(
        df["AboveMA25"]
    )

    conditions["MA75上"] = to_bool_series(
        df["AboveMA75"]
    )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    conditions["MACD GC"] = to_bool_series(
        df["MACD_GC"]
    )

    for name, mask in conditions.items():
        df[name] = mask

    return df, list(conditions.keys())


# ============================================================
# 条件追加による増分分析
# ============================================================

def analyze_increment(df, base_name, add_name):
    """
    base条件を満たす集団に対して、
    add条件を追加したときに予測力がどう変化するかを分析。
    """

    base_mask = df[base_name]

    added_mask = df[base_name] & df[add_name]

    base_stats = calc_stats(df, base_mask)
    added_stats = calc_stats(df, added_mask)

    if (
        base_stats["n"] < MIN_SAMPLES
        or added_stats["n"] < MIN_SAMPLES
    ):
        return None

    return {
        "ベース条件": base_name,
        "追加条件": add_name,

        "ベースn": base_stats["n"],
        "追加後n": added_stats["n"],

        "ベース+10%": base_stats["+10%"],
        "追加後+10%": added_stats["+10%"],
        "+10%増分": (
            added_stats["+10%"]
            - base_stats["+10%"]
        ),

        "ベース+20%": base_stats["+20%"],
        "追加後+20%": added_stats["+20%"],
        "+20%増分": (
            added_stats["+20%"]
            - base_stats["+20%"]
        ),

        "ベース平均最大": base_stats["平均最大"],
        "追加後平均最大": added_stats["平均最大"],
        "平均最大増分": (
            added_stats["平均最大"]
            - base_stats["平均最大"]
        ),
    }


# ============================================================
# メイン
# ============================================================

def main():

    print("=" * 60)
    print("=== 初動スコア Ver4 条件追加効果分析 ===")
    print("=" * 60)

    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLES}")

    if not INPUT_FILE.exists():
        print()
        print(f"ERROR: 入力ファイルがありません: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)

    print(f"検証記録数 : {len(df):,}")

    # --------------------------------------------------------
    # 必須列確認
    # --------------------------------------------------------

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
        "5営業日以内最大騰落率",
        "Hit5",
        "Hit10",
        "Hit20",
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        print()
        print("ERROR: 必要な列がありません")
        print(missing)
        return

    # --------------------------------------------------------
    # 結果列を整形
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 条件作成
    # --------------------------------------------------------

    df, condition_names = add_condition_columns(df)

    print()
    print("=" * 60)
    print("=== 条件マスク作成 ===")
    print("=" * 60)

    for name in condition_names:
        print(
            f"{name:25s}"
            f" n={int(df[name].sum()):5d}"
        )

    # --------------------------------------------------------
    # 全体基準
    # --------------------------------------------------------

    baseline = calc_stats(
        df,
        pd.Series(True, index=df.index),
    )

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print(
        f"全体件数       : {baseline['n']:,}"
    )
    print(
        f"+5%率          : {baseline['+5%']:.1f}%"
    )
    print(
        f"+10%率         : {baseline['+10%']:.1f}%"
    )
    print(
        f"+20%率         : {baseline['+20%']:.1f}%"
    )
    print(
        f"平均最大騰落率 : "
        f"{baseline['平均最大']:+.2f}%"
    )

    # ========================================================
    # 1条件 → 他条件を追加
    # ========================================================

    print()
    print("=" * 60)
    print("=== 条件追加による増分分析 ===")
    print("=" * 60)

    results = []

    for base_name in condition_names:

        for add_name in condition_names:

            if base_name == add_name:
                continue

            result = analyze_increment(
                df,
                base_name,
                add_name,
            )

            if result is not None:
                results.append(result)

    result_df = pd.DataFrame(results)

    if result_df.empty:
        print("分析可能な組み合わせがありません。")
        return

    # ========================================================
    # +20%増分ランキング
    # ========================================================

    print()
    print("=" * 60)
    print("=== +20%率 増分ランキング ===")
    print("=" * 60)

    ranking20 = result_df.sort_values(
        "+20%増分",
        ascending=False,
    )

    for rank, (_, row) in enumerate(
        ranking20.head(30).iterrows(),
        start=1,
    ):

        print(
            f"{rank:2d}. "
            f"{row['ベース条件']:20s}"
            f" + {row['追加条件']:20s}"
            f" / n={int(row['追加後n']):4d}"
            f" / +20% "
            f"{row['ベース+20%']:.1f}%"
            f" → {row['追加後+20%']:.1f}%"
            f" / 増分="
            f"{row['+20%増分']:+5.1f}pt"
        )

    # ========================================================
    # +10%増分ランキング
    # ========================================================

    print()
    print("=" * 60)
    print("=== +10%率 増分ランキング ===")
    print("=" * 60)

    ranking10 = result_df.sort_values(
        "+10%増分",
        ascending=False,
    )

    for rank, (_, row) in enumerate(
        ranking10.head(30).iterrows(),
        start=1,
    ):

        print(
            f"{rank:2d}. "
            f"{row['ベース条件']:20s}"
            f" + {row['追加条件']:20s}"
            f" / n={int(row['追加後n']):4d}"
            f" / +10% "
            f"{row['ベース+10%']:.1f}%"
            f" → {row['追加後+10%']:.1f}%"
            f" / 増分="
            f"{row['+10%増分']:+5.1f}pt"
        )

    # ========================================================
    # 重要条件の追加効果
    # ========================================================

    important_conditions = [
        "前日比+5%以上",
        "出来高3倍以上",
        "ブレイク",
        "30日高値更新",
        "ブレイク初日",
        "MA5上",
        "MA25上",
        "MA75上",
        "MACD GC",
    ]

    print()
    print("=" * 60)
    print("=== 重要条件の追加効果 ===")
    print("=" * 60)

    for add_name in important_conditions:

        subset = result_df[
            result_df["追加条件"] == add_name
        ].copy()

        if subset.empty:
            continue

        best20 = subset.sort_values(
            "+20%増分",
            ascending=False,
        ).iloc[0]

        best10 = subset.sort_values(
            "+10%増分",
            ascending=False,
        ).iloc[0]

        print()
        print(f"[{add_name}]")

        print(
            f"  +20%最大増分 : "
            f"{best20['ベース条件']} → "
            f"{best20['+20%増分']:+.1f}pt"
        )

        print(
            f"  +10%最大増分 : "
            f"{best10['ベース条件']} → "
            f"{best10['+10%増分']:+.1f}pt"
        )

    # ========================================================
    # MACD GC 特別確認
    # ========================================================

    print()
    print("=" * 60)
    print("=== MACD GC 追加効果確認 ===")
    print("=" * 60)

    macd_results = result_df[
        result_df["追加条件"] == "MACD GC"
    ].sort_values(
        "+20%増分",
        ascending=False,
    )

    if not macd_results.empty:

        for _, row in macd_results.head(10).iterrows():

            print(
                f"{row['ベース条件']:20s}"
                f" + MACD GC"
                f" / n={int(row['追加後n']):4d}"
                f" / +10%増分="
                f"{row['+10%増分']:+.1f}pt"
                f" / +20%増分="
                f"{row['+20%増分']:+.1f}pt"
            )

    # ========================================================
    # 前日比+5% × 出来高3倍など重点組み合わせ
    # ========================================================

    print()
    print("=" * 60)
    print("=== 重点組み合わせの追加効果 ===")
    print("=" * 60)

    focus_pairs = [
        ("前日比+5%以上", "出来高3倍以上"),
        ("前日比+5%以上", "ブレイク"),
        ("前日比+5%以上", "30日高値更新"),
        ("出来高3倍以上", "ブレイク"),
        ("出来高3倍以上", "30日高値更新"),
        ("出来高3倍以上", "前日比+5%以上"),
        ("ブレイク", "30日高値更新"),
        ("30日高値更新", "ブレイク"),
        ("ブレイク", "ブレイク初日"),
    ]

    for base_name, add_name in focus_pairs:

        row = result_df[
            (result_df["ベース条件"] == base_name)
            & (result_df["追加条件"] == add_name)
        ]

        if row.empty:
            continue

        row = row.iloc[0]

        print(
            f"{base_name} + {add_name}"
            f" / n={int(row['追加後n']):4d}"
            f" / +10% "
            f"{row['ベース+10%']:.1f}%"
            f" → {row['追加後+10%']:.1f}%"
            f" ({row['+10%増分']:+.1f}pt)"
            f" / +20% "
            f"{row['ベース+20%']:.1f}%"
            f" → {row['追加後+20%']:.1f}%"
            f" ({row['+20%増分']:+.1f}pt)"
        )

    # ========================================================
    # 保存
    # ========================================================

    print()
    print("=" * 60)
    print("=== 分析結果保存 ===")
    print("=" * 60)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_df = result_df.sort_values(
        "+20%増分",
        ascending=False,
    )

    save_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"保存先: {OUTPUT_FILE}"
    )

    print()
    print("=" * 60)
    print("=== 初動スコア Ver4 条件追加効果分析完了 ===")
    print("=" * 60)

    print(
        f"検証記録数 : {len(df):,}"
    )
    print(
        f"分析組み合わせ数 : {len(result_df)}"
    )
    print(
        f"保存先     : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()