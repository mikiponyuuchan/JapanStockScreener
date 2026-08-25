from pathlib import Path
import pandas as pd


# ============================================================
# 初動スコア Ver4 高スコア帯詳細分析
# Ver4_C_超初動を13～17点まで分解
# ============================================================

INPUT_FILE = Path(
    "data/tracking/initial_score_factor_raw.csv"
)

OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_highscore_analysis.csv"
)

MIN_SAMPLE = 10


# ============================================================
# 表示
# ============================================================

def print_header(title):
    print()
    print("=" * 60)
    print(f"=== {title} ===")
    print("=" * 60)


# ============================================================
# 条件マスク
# ============================================================

def build_masks(df):
    masks = {}

    masks["前日比+1%以上"] = df["ChangePercent"] >= 1
    masks["前日比+3%以上"] = df["ChangePercent"] >= 3
    masks["前日比+5%以上"] = df["ChangePercent"] >= 5

    masks["出来高1.5倍以上"] = df["VolumeRatio"] >= 1.5
    masks["出来高2倍以上"] = df["VolumeRatio"] >= 2
    masks["出来高3倍以上"] = df["VolumeRatio"] >= 3

    masks["ブレイク"] = (
        df["BreakoutSignal"]
        .fillna(False)
        .astype(bool)
    )

    masks["30日高値更新"] = (
        df["New30High"]
        .fillna(False)
        .astype(bool)
    )

    masks["MACD GC"] = (
        df["MACD_GC"]
        .fillna(False)
        .astype(bool)
    )

    return masks


# ============================================================
# Ver4_C スコア
# ============================================================

def calc_ver4_c_score(df, masks):
    score = pd.Series(
        0.0,
        index=df.index,
    )

    # --------------------------------------------------------
    # 前日比
    # 最高ランクのみ
    # +1% = 1
    # +3% = 3
    # +5% = 5
    # --------------------------------------------------------

    score += (
        masks["前日比+1%以上"].astype(float) * 1
    )

    score = score.where(
        ~masks["前日比+3%以上"],
        score - 1 + 3,
    )

    score = score.where(
        ~masks["前日比+5%以上"],
        score - 3 + 5,
    )

    # --------------------------------------------------------
    # 出来高倍率
    # 最高ランクのみ
    #
    # 1.5倍 = 1
    # 2倍   = 2
    # 3倍   = 5
    # --------------------------------------------------------

    volume_score = (
        masks["出来高1.5倍以上"].astype(float) * 1
    )

    volume_score = volume_score.where(
        ~masks["出来高2倍以上"],
        2,
    )

    volume_score = volume_score.where(
        ~masks["出来高3倍以上"],
        5,
    )

    score += volume_score

    # --------------------------------------------------------
    # ブレイク
    # --------------------------------------------------------

    score += (
        masks["ブレイク"].astype(float) * 3
    )

    # --------------------------------------------------------
    # 30日高値更新
    # --------------------------------------------------------

    score += (
        masks["30日高値更新"].astype(float) * 3
    )

    # --------------------------------------------------------
    # MACD GC
    # --------------------------------------------------------

    score += (
        masks["MACD GC"].astype(float) * 1
    )

    return score


# ============================================================
# RSI減点
# ============================================================

def calc_rsi_penalty(df):
    rsi = pd.to_numeric(
        df["RSI"],
        errors="coerce",
    )

    penalty = pd.Series(
        0.0,
        index=df.index,
    )

    penalty = penalty.where(
        ~((rsi >= 85) & (rsi < 90)),
        -1,
    )

    penalty = penalty.where(
        ~((rsi >= 90) & (rsi < 95)),
        -2,
    )

    penalty = penalty.where(
        ~(rsi >= 95),
        -3,
    )

    return penalty


# ============================================================
# 基本統計
# ============================================================

def calc_stats(subset):
    if subset.empty:
        return {
            "件数": 0,
            "構成比": 0,
            "+5%率": 0,
            "+10%率": 0,
            "+20%率": 0,
            "平均最大騰落率": 0,
        }

    return {
        "件数": len(subset),
        "構成比": len(subset),
        "+5%率": subset["Hit5"].mean() * 100,
        "+10%率": subset["Hit10"].mean() * 100,
        "+20%率": subset["Hit20"].mean() * 100,
        "平均最大騰落率": (
            subset["5営業日以内最大騰落率"].mean()
        ),
    }


# ============================================================
# 条件構成
# ============================================================

def analyze_condition_composition(
    subset,
    masks,
):
    results = []

    if subset.empty:
        return results

    for condition, mask in masks.items():
        count = int(mask.loc[subset.index].sum())

        results.append(
            {
                "条件": condition,
                "件数": count,
                "成立率": count / len(subset) * 100,
            }
        )

    return results


# ============================================================
# 高騰成功例の条件構成
# ============================================================

def analyze_success_cases(
    subset,
    masks,
):
    results = []

    success = subset[
        subset["Hit10"] == 1
    ].copy()

    success = success.sort_values(
        "5営業日以内最大騰落率",
        ascending=False,
    )

    for _, row in success.iterrows():

        conditions = []

        for condition, mask in masks.items():
            if bool(mask.loc[row.name]):
                conditions.append(condition)

        results.append(
            {
                "検出日": row.get("検出日"),
                "コード": row.get("コード"),
                "銘柄名": row.get("銘柄名"),
                "基本スコア": row["Ver4C基本"],
                "RSI": row["RSI"],
                "RSI減点": row["RSI減点"],
                "最終スコア": row["Ver4C最終"],
                "+5%": int(row["Hit5"]),
                "+10%": int(row["Hit10"]),
                "+20%": int(row["Hit20"]),
                "最大騰落率": row[
                    "5営業日以内最大騰落率"
                ],
                "成立条件": " / ".join(conditions),
            }
        )

    return results


# ============================================================
# メイン
# ============================================================

def main():

    print_header(
        "初動スコア Ver4 高スコア帯詳細分析"
    )

    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLE}")

    if not INPUT_FILE.exists():
        print()
        print(
            f"入力ファイルがありません: {INPUT_FILE}"
        )
        return

    df = pd.read_csv(INPUT_FILE)

    print(
        f"検証記録数 : {len(df):,}"
    )

    # --------------------------------------------------------
    # 数値変換
    # --------------------------------------------------------

    numeric_columns = [
        "ChangePercent",
        "VolumeRatio",
        "RSI",
        "5営業日以内最大騰落率",
        "Hit5",
        "Hit10",
        "Hit20",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    # --------------------------------------------------------
    # 全体基準
    # --------------------------------------------------------

    print_header("全体基準")

    baseline_5 = (
        df["Hit5"].mean() * 100
    )

    baseline_10 = (
        df["Hit10"].mean() * 100
    )

    baseline_20 = (
        df["Hit20"].mean() * 100
    )

    print(
        f"全体件数       : {len(df):,}"
    )

    print(
        f"+5%率          : {baseline_5:.1f}%"
    )

    print(
        f"+10%率         : {baseline_10:.1f}%"
    )

    print(
        f"+20%率         : {baseline_20:.1f}%"
    )

    print(
        f"平均最大騰落率 : "
        f"{df['5営業日以内最大騰落率'].mean():+.2f}%"
    )

    # --------------------------------------------------------
    # マスク
    # --------------------------------------------------------

    print_header("条件マスク作成")

    masks = build_masks(df)

    for name, mask in masks.items():
        print(
            f"{name:<24} "
            f"n={int(mask.sum()):,}"
        )

    # --------------------------------------------------------
    # Ver4_C
    # --------------------------------------------------------

    print_header(
        "Ver4_C_超初動 スコア計算"
    )

    base_score = calc_ver4_c_score(
        df,
        masks,
    )

    rsi_penalty = calc_rsi_penalty(df)

    final_score = (
        base_score + rsi_penalty
    )

    df["Ver4C基本"] = base_score
    df["RSI減点"] = rsi_penalty
    df["Ver4C最終"] = final_score

    print(
        f"基本スコア最大 : "
        f"{base_score.max():.0f}"
    )

    print(
        f"最終スコア最大 : "
        f"{final_score.max():.0f}"
    )

    print(
        f"RSI減点件数    : "
        f"{int((rsi_penalty < 0).sum()):,}"
    )

    # --------------------------------------------------------
    # 13～17点
    # --------------------------------------------------------

    print_header(
        "13～17点 スコア別実績"
    )

    score_results = []

    for score in range(13, 18):

        subset = df[
            df["Ver4C基本"] == score
        ]

        if len(subset) < MIN_SAMPLE:
            print(
                f"{score:2d}点 "
                f"n={len(subset):3d} "
                f"→ サンプル不足"
            )
            continue

        stats = calc_stats(subset)

        print(
            f"{score:2d}点 "
            f"n={stats['件数']:3d} "
            f"/ +5%={stats['+5%率']:5.1f}% "
            f"/ +10%={stats['+10%率']:5.1f}% "
            f"/ +20%={stats['+20%率']:5.1f}% "
            f"/ 平均最大="
            f"{stats['平均最大騰落率']:+6.2f}%"
        )

        score_results.append(
            {
                "分析": "スコア別",
                "スコア": score,
                **stats,
            }
        )

    # --------------------------------------------------------
    # 14点以上
    # --------------------------------------------------------

    print_header(
        "14点以上 vs 13点"
    )

    subset_13 = df[
        df["Ver4C基本"] == 13
    ]

    subset_14 = df[
        df["Ver4C基本"] >= 14
    ]

    stats_13 = calc_stats(
        subset_13
    )

    stats_14 = calc_stats(
        subset_14
    )

    print(
        f"13点      "
        f"n={stats_13['件数']:3d} "
        f"/ +10%={stats_13['+10%率']:.1f}% "
        f"/ +20%={stats_13['+20%率']:.1f}% "
        f"/ 平均最大="
        f"{stats_13['平均最大騰落率']:+.2f}%"
    )

    print(
        f"14点以上  "
        f"n={stats_14['件数']:3d} "
        f"/ +10%={stats_14['+10%率']:.1f}% "
        f"/ +20%={stats_14['+20%率']:.1f}% "
        f"/ 平均最大="
        f"{stats_14['平均最大騰落率']:+.2f}%"
    )

    print(
        f"+10%率差 : "
        f"{stats_14['+10%率'] - stats_13['+10%率']:+.1f}pt"
    )

    print(
        f"+20%率差 : "
        f"{stats_14['+20%率'] - stats_13['+20%率']:+.1f}pt"
    )

    # --------------------------------------------------------
    # 14点以上の条件構成
    # --------------------------------------------------------

    print_header(
        "14点以上 条件構成"
    )

    composition = (
        analyze_condition_composition(
            subset_14,
            masks,
        )
    )

    composition_df = pd.DataFrame(
        composition
    )

    if not composition_df.empty:
        composition_df = composition_df.sort_values(
            "成立率",
            ascending=False,
        )

        for _, row in composition_df.iterrows():
            print(
                f"{row['条件']:<24} "
                f"{int(row['件数']):3d}件 "
                f"({row['成立率']:5.1f}%)"
            )

    # --------------------------------------------------------
    # 13点と14点以上の差
    # --------------------------------------------------------

    print_header(
        "13点 → 14点以上 条件成立率比較"
    )

    comparison_rows = []

    for condition, mask in masks.items():

        rate13 = (
            mask.loc[subset_13.index].mean()
            * 100
            if len(subset_13) > 0
            else 0
        )

        rate14 = (
            mask.loc[subset_14.index].mean()
            * 100
            if len(subset_14) > 0
            else 0
        )

        diff = rate14 - rate13

        comparison_rows.append(
            {
                "条件": condition,
                "13点成立率": rate13,
                "14点以上成立率": rate14,
                "差": diff,
            }
        )

    comparison_df = pd.DataFrame(
        comparison_rows
    )

    comparison_df = comparison_df.sort_values(
        "差",
        ascending=False,
    )

    for _, row in comparison_df.iterrows():
        print(
            f"{row['条件']:<24} "
            f"13点={row['13点成立率']:5.1f}% "
            f"/ 14点以上={row['14点以上成立率']:5.1f}% "
            f"/ 差={row['差']:+5.1f}pt"
        )

    # --------------------------------------------------------
    # 14点以上の高騰成功例
    # --------------------------------------------------------

    print_header(
        "14点以上 +10%達成銘柄"
    )

    success_cases = (
        analyze_success_cases(
            subset_14,
            masks,
        )
    )

    for row in success_cases:
        print(
            f"{row['検出日']} "
            f"{row['コード']} "
            f"{row['銘柄名']} "
            f"/ 基本={row['基本スコア']:.0f} "
            f"/ RSI={row['RSI']:.1f} "
            f"/ 減点={row['RSI減点']:.0f} "
            f"/ 最終={row['最終スコア']:.0f} "
            f"/ +20={row['+20%']} "
            f"/ 最大={row['最大騰落率']:+.2f}%"
        )

        print(
            f"    条件: {row['成立条件']}"
        )

    # --------------------------------------------------------
    # RSI減点による順位変動
    # --------------------------------------------------------

    print_header(
        "14点以上 RSI減点影響"
    )

    high = subset_14.copy()

    high = high.sort_values(
        [
            "Ver4C最終",
            "Ver4C基本",
        ],
        ascending=False,
    ).copy()

    high["最終順位"] = range(
        1,
        len(high) + 1,
    )

    high = high.sort_values(
        [
            "Ver4C基本",
            "RSI",
        ],
        ascending=[
            False,
            True,
        ],
    ).copy()

    high["基本順位"] = range(
        1,
        len(high) + 1,
    )

    high["順位変動"] = (
        high["基本順位"]
        - high["最終順位"]
    )

    rank_changed = high[
        high["順位変動"] != 0
    ].sort_values(
        "順位変動",
        key=lambda x: x.abs(),
        ascending=False,
    )

    print(
        f"14点以上件数 : {len(high)}"
    )

    print(
        f"RSI減点あり  : "
        f"{int((high['RSI減点'] < 0).sum())}"
    )

    print(
        f"順位変動あり  : "
        f"{len(rank_changed)}"
    )

    for _, row in rank_changed.head(20).iterrows():
        print(
            f"{row['検出日']} "
            f"{row['コード']} "
            f"{row['銘柄名']} "
            f"/ 基本={row['Ver4C基本']:.0f} "
            f"/ RSI={row['RSI']:.1f} "
            f"/ 減点={row['RSI減点']:.0f} "
            f"/ 最終={row['Ver4C最終']:.0f} "
            f"/ 基本順位={int(row['基本順位'])} "
            f"/ 最終順位={int(row['最終順位'])} "
            f"/ 変動={int(row['順位変動']):+d}"
        )

    # --------------------------------------------------------
    # +20%達成例
    # --------------------------------------------------------

    print_header(
        "14点以上 +20%達成銘柄"
    )

    success20 = subset_14[
        subset_14["Hit20"] == 1
    ].copy()

    success20 = success20.sort_values(
        "5営業日以内最大騰落率",
        ascending=False,
    )

    print(
        f"+20%達成件数 : {len(success20)}"
    )

    for _, row in success20.iterrows():

        conditions = []

        for condition, mask in masks.items():
            if bool(mask.loc[row.name]):
                conditions.append(condition)

        print(
            f"{row['検出日']} "
            f"{row['コード']} "
            f"{row['銘柄名']} "
            f"/ 基本={row['Ver4C基本']:.0f} "
            f"/ RSI={row['RSI']:.1f} "
            f"/ 最終={row['Ver4C最終']:.0f} "
            f"/ 最大={row['5営業日以内最大騰落率']:+.2f}%"
        )

        print(
            f"    条件: {' / '.join(conditions)}"
        )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    print_header(
        "分析結果保存"
    )

    output_rows = []

    for row in score_results:
        output_rows.append(row)

    for _, row in composition_df.iterrows():
        output_rows.append(
            {
                "分析": "14点以上条件構成",
                "条件": row["条件"],
                "件数": row["件数"],
                "成立率": row["成立率"],
            }
        )

    for _, row in comparison_df.iterrows():
        output_rows.append(
            {
                "分析": "13点→14点以上比較",
                "条件": row["条件"],
                "13点成立率": row["13点成立率"],
                "14点以上成立率": row[
                    "14点以上成立率"
                ],
                "差": row["差"],
            }
        )

    for row in success_cases:
        row_copy = row.copy()
        row_copy["分析"] = (
            "14点以上+10%達成"
        )
        output_rows.append(row_copy)

    final_output = pd.DataFrame(
        output_rows
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_output.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"保存先: {OUTPUT_FILE}"
    )

    print_header(
        "初動スコア Ver4 高スコア帯分析完了"
    )

    print(
        f"検証記録数 : {len(df):,}"
    )

    print(
        f"14点以上   : {len(subset_14)}件"
    )

    print(
        f"14点以上 +10% : "
        f"{stats_14['+10%率']:.1f}%"
    )

    print(
        f"14点以上 +20% : "
        f"{stats_14['+20%率']:.1f}%"
    )

    print(
        f"保存先 : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()