from pathlib import Path

import numpy as np
import pandas as pd


INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_core4_analysis.csv"
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


# ============================================================
# メイン
# ============================================================

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

    # --------------------------------------------------------
    # 必要列確認
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 数値変換
    # --------------------------------------------------------

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

    df = df.dropna(
        subset=[
            "ChangePercent",
            "VolumeRatio",
            "5営業日以内最大騰落率",
        ]
    ).copy()

    # --------------------------------------------------------
    # コア4条件
    # --------------------------------------------------------

    conditions = {
        "前日比+5%以上": df["ChangePercent"] >= 5,
        "出来高3倍以上": df["VolumeRatio"] >= 3,
        "ブレイク": to_bool_series(df["BreakoutSignal"]),
        "30日高値更新": to_bool_series(df["New30High"]),
    }

    for name, mask in conditions.items():
        df[name] = mask

    print()
    print("=" * 60)
    print("=== コア4条件マスク ===")
    print("=" * 60)

    for name in conditions:
        print(
            f"{name:20s} "
            f"n={int(df[name].sum()):5d}"
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

    print(f"全体件数       : {baseline['件数']:,}")
    print(f"+5%率          : {baseline['+5%率']:.1f}%")
    print(f"+10%率         : {baseline['+10%率']:.1f}%")
    print(f"+20%率         : {baseline['+20%率']:.1f}%")
    print(
        f"平均最大騰落率 : "
        f"{baseline['平均最大騰落率']:+.2f}%"
    )

    # --------------------------------------------------------
    # 一致本数を計算
    # --------------------------------------------------------

    condition_names = list(conditions.keys())

    df["一致本数"] = df[condition_names].sum(axis=1)

    results = []

    for count in range(5):

        mask = df["一致本数"] == count

        stats = calc_stats(df, mask)

        if stats["件数"] < MIN_SAMPLES:
            continue

        results.append({
            "一致本数": count,
            "件数": stats["件数"],
            "構成比": stats["件数"] / len(df) * 100,
            "+5%率": stats["+5%率"],
            "+10%率": stats["+10%率"],
            "+20%率": stats["+20%率"],
            "平均最大騰落率": stats["平均最大騰落率"],
            "+10%改善": stats["+10%率"] - baseline["+10%率"],
            "+20%改善": stats["+20%率"] - baseline["+20%率"],
        })

    result_df = pd.DataFrame(results)

    # --------------------------------------------------------
    # 一致本数別結果
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== コア4条件 一致本数別分析 ===")
    print("=" * 60)

    for _, row in result_df.iterrows():

        print(
            f"{int(row['一致本数'])}本一致"
            f" / n={int(row['件数']):5d}"
            f" / 構成比={row['構成比']:5.2f}%"
            f" / +5%={row['+5%率']:5.1f}%"
            f" / +10%={row['+10%率']:5.1f}%"
            f" / +20%={row['+20%率']:5.1f}%"
            f" / +10%改善={row['+10%改善']:+6.1f}pt"
            f" / +20%改善={row['+20%改善']:+6.1f}pt"
            f" / 平均最大={row['平均最大騰落率']:+.2f}%"
        )

    # --------------------------------------------------------
    # 3本一致の4パターン
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 3本一致パターン ===")
    print("=" * 60)

    triple_results = []

    for i in range(len(condition_names)):
        for j in range(i + 1, len(condition_names)):
            for k in range(j + 1, len(condition_names)):

                selected = [
                    condition_names[i],
                    condition_names[j],
                    condition_names[k],
                ]

                mask = df[selected].all(axis=1)

                stats = calc_stats(df, mask)

                if stats["件数"] < MIN_SAMPLES:
                    continue

                triple_results.append({
                    "条件": " + ".join(selected),
                    "件数": stats["件数"],
                    "+5%率": stats["+5%率"],
                    "+10%率": stats["+10%率"],
                    "+20%率": stats["+20%率"],
                    "+10%改善": (
                        stats["+10%率"] -
                        baseline["+10%率"]
                    ),
                    "+20%改善": (
                        stats["+20%率"] -
                        baseline["+20%率"]
                    ),
                    "平均最大騰落率": (
                        stats["平均最大騰落率"]
                    ),
                })

    triple_df = pd.DataFrame(triple_results)

    if not triple_df.empty:

        triple_df = triple_df.sort_values(
            "+20%改善",
            ascending=False,
        )

        for rank, (_, row) in enumerate(
            triple_df.iterrows(),
            start=1,
        ):

            print(
                f"{rank}. "
                f"{row['条件']}"
                f" / n={int(row['件数']):4d}"
                f" / +10%={row['+10%率']:5.1f}%"
                f" / +20%={row['+20%率']:5.1f}%"
                f" / +10%改善={row['+10%改善']:+6.1f}pt"
                f" / +20%改善={row['+20%改善']:+6.1f}pt"
            )

    # --------------------------------------------------------
    # 4本一致
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 4本一致 ===")
    print("=" * 60)

    all_four_mask = df[condition_names].all(axis=1)

    four_stats = calc_stats(
        df,
        all_four_mask,
    )

    print(
        f"4本一致"
        f" / n={four_stats['件数']}"
        f" / +5%={four_stats['+5%率']:.1f}%"
        f" / +10%={four_stats['+10%率']:.1f}%"
        f" / +20%={four_stats['+20%率']:.1f}%"
        f" / +10%改善="
        f"{four_stats['+10%率'] - baseline['+10%率']:+.1f}pt"
        f" / +20%改善="
        f"{four_stats['+20%率'] - baseline['+20%率']:+.1f}pt"
        f" / 平均最大="
        f"{four_stats['平均最大騰落率']:+.2f}%"
    )

    # --------------------------------------------------------
    # 3本以上
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 3本以上 ===")
    print("=" * 60)

    three_or_more_mask = df["一致本数"] >= 3

    three_or_more = calc_stats(
        df,
        three_or_more_mask,
    )

    print(
        f"3本以上"
        f" / n={three_or_more['件数']}"
        f" / +5%={three_or_more['+5%率']:.1f}%"
        f" / +10%={three_or_more['+10%率']:.1f}%"
        f" / +20%={three_or_more['+20%率']:.1f}%"
        f" / +10%改善="
        f"{three_or_more['+10%率'] - baseline['+10%率']:+.1f}pt"
        f" / +20%改善="
        f"{three_or_more['+20%率'] - baseline['+20%率']:+.1f}pt"
    )

    # --------------------------------------------------------
    # 最終判定
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== コア4条件 最終評価 ===")
    print("=" * 60)

    if four_stats["件数"] >= MIN_SAMPLES:

        print()
        print("【4本一致】")

        print(
            f"+10%率 : "
            f"{four_stats['+10%率']:.1f}%"
        )

        print(
            f"+20%率 : "
            f"{four_stats['+20%率']:.1f}%"
        )

        print(
            f"+20%改善 : "
            f"{four_stats['+20%率'] - baseline['+20%率']:+.1f}pt"
        )

    else:

        print()
        print(
            "4本一致はサンプル数が少ないため、"
            "単独では判断しません。"
        )

    if three_or_more["件数"] >= MIN_SAMPLES:

        print()
        print("【3本以上】")

        print(
            f"+10%率 : "
            f"{three_or_more['+10%率']:.1f}%"
        )

        print(
            f"+20%率 : "
            f"{three_or_more['+20%率']:.1f}%"
        )

        print(
            f"+20%改善 : "
            f"{three_or_more['+20%率'] - baseline['+20%率']:+.1f}pt"
        )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_frames = []

    result_save = result_df.copy()
    result_save["分析種別"] = "一致本数"
    save_frames.append(result_save)

    if not triple_df.empty:

        triple_save = triple_df.copy()
        triple_save["分析種別"] = "3本組み合わせ"
        save_frames.append(triple_save)

    four_save = pd.DataFrame([
        {
            "分析種別": "4本一致",
            "一致本数": 4,
            "件数": four_stats["件数"],
            "+5%率": four_stats["+5%率"],
            "+10%率": four_stats["+10%率"],
            "+20%率": four_stats["+20%率"],
            "+10%改善": (
                four_stats["+10%率"] -
                baseline["+10%率"]
            ),
            "+20%改善": (
                four_stats["+20%率"] -
                baseline["+20%率"]
            ),
            "平均最大騰落率": (
                four_stats["平均最大騰落率"]
            ),
        }
    ])

    save_frames.append(four_save)

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

    print()
    print("=" * 60)
    print("=== 分析結果保存 ===")
    print("=" * 60)

    print(f"保存先: {OUTPUT_FILE}")

    print()
    print("=" * 60)
    print("=== 初動スコア Ver4 コア4条件分析完了 ===")
    print("=" * 60)

    print(f"検証記録数 : {len(df):,}")
    print(f"保存先     : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()