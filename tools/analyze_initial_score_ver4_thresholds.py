from pathlib import Path
import pandas as pd


# ============================================================
# 初動スコア Ver4 閾値分析
# ============================================================

INPUT_FILE = Path(
    "data/tracking/initial_score_factor_raw.csv"
)

OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_threshold_analysis.csv"
)

MIN_SAMPLE = 30


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

    # --------------------------------------------------------
    # 前日比
    # --------------------------------------------------------
    masks["前日比+1%以上"] = (
        df["ChangePercent"] >= 1
    )

    masks["前日比+3%以上"] = (
        df["ChangePercent"] >= 3
    )

    masks["前日比+5%以上"] = (
        df["ChangePercent"] >= 5
    )

    # --------------------------------------------------------
    # 出来高倍率
    # --------------------------------------------------------
    masks["出来高1.5倍以上"] = (
        df["VolumeRatio"] >= 1.5
    )

    masks["出来高2倍以上"] = (
        df["VolumeRatio"] >= 2
    )

    masks["出来高3倍以上"] = (
        df["VolumeRatio"] >= 3
    )

    # --------------------------------------------------------
    # ブレイク
    # --------------------------------------------------------
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
# Ver4スコア
# ============================================================

def calc_base_score(df, masks, scheme):
    score = pd.Series(
        0.0,
        index=df.index,
    )

    # --------------------------------------------------------
    # 前日比
    # 最高ランクのみ加点
    # --------------------------------------------------------

    price_points = scheme["price_points"]

    price_score = (
        masks["前日比+1%以上"].astype(float)
        * price_points[1]
    )

    price_score = price_score.where(
        ~masks["前日比+3%以上"],
        price_points[3],
    )

    price_score = price_score.where(
        ~masks["前日比+5%以上"],
        price_points[5],
    )

    score += price_score

    # --------------------------------------------------------
    # 出来高倍率
    # 最高ランクのみ加点
    # --------------------------------------------------------

    volume_points = scheme["volume_points"]

    volume_score = (
        masks["出来高1.5倍以上"].astype(float)
        * volume_points[1.5]
    )

    volume_score = volume_score.where(
        ~masks["出来高2倍以上"],
        volume_points[2.0],
    )

    volume_score = volume_score.where(
        ~masks["出来高3倍以上"],
        volume_points[3.0],
    )

    score += volume_score

    # --------------------------------------------------------
    # その他条件
    # --------------------------------------------------------

    for condition, points in scheme["other_points"].items():

        if points == 0:
            continue

        score += (
            masks[condition].astype(float)
            * points
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
# Ver4案
# ============================================================

def build_schemes():
    return {

        # ----------------------------------------------------
        # Ver4_A
        # 初動特化
        # ----------------------------------------------------
        "Ver4_A_初動特化": {

            "price_points": {
                1: 1,
                3: 2,
                5: 3,
            },

            "volume_points": {
                1.5: 1,
                2.0: 2,
                3.0: 3,
            },

            "other_points": {
                "ブレイク": 2,
                "30日高値更新": 2,
                "MACD GC": 1,
            },
        },

        # ----------------------------------------------------
        # Ver4_B
        # 高騰重視
        # ----------------------------------------------------
        "Ver4_B_高騰重視": {

            "price_points": {
                1: 1,
                3: 3,
                5: 4,
            },

            "volume_points": {
                1.5: 1,
                2.0: 3,
                3.0: 4,
            },

            "other_points": {
                "ブレイク": 2,
                "30日高値更新": 2,
                "MACD GC": 1,
            },
        },

        # ----------------------------------------------------
        # Ver4_C
        # 超初動
        # ----------------------------------------------------
        "Ver4_C_超初動": {

            "price_points": {
                1: 1,
                3: 3,
                5: 5,
            },

            "volume_points": {
                1.5: 1,
                2.0: 3,
                3.0: 5,
            },

            "other_points": {
                "ブレイク": 3,
                "30日高値更新": 3,
                "MACD GC": 1,
            },
        },
    }


# ============================================================
# スコア帯分析
# ============================================================

def analyze_score_bands(
    df,
    score_col,
    scheme_name,
):
    results = []

    score = df[score_col]

    max_score = int(
        score.max()
    )

    for s in range(
        max_score,
        -1,
        -1,
    ):

        subset = df[
            score == s
        ]

        if len(subset) < MIN_SAMPLE:
            continue

        results.append(
            {
                "案": scheme_name,
                "分析": "スコア別",
                "閾値": s,
                "スコア下限": s,
                "スコア上限": s,
                "件数": len(subset),
                "構成比": (
                    len(subset)
                    / len(df)
                    * 100
                ),
                "+5%率": (
                    subset["Hit5"].mean()
                    * 100
                ),
                "+10%率": (
                    subset["Hit10"].mean()
                    * 100
                ),
                "+20%率": (
                    subset["Hit20"].mean()
                    * 100
                ),
                "平均最大騰落率": subset[
                    "5営業日以内最大騰落率"
                ].mean(),
            }
        )

    return results


# ============================================================
# 累積閾値分析
# ============================================================

def analyze_thresholds(
    df,
    score_col,
    scheme_name,
):
    results = []

    score = df[score_col]

    max_score = int(
        score.max()
    )

    for threshold in range(
        max_score + 1
    ):

        subset = df[
            score >= threshold
        ]

        if len(subset) < MIN_SAMPLE:
            continue

        results.append(
            {
                "案": scheme_name,
                "分析": "以上",
                "閾値": threshold,
                "スコア下限": threshold,
                "スコア上限": max_score,
                "件数": len(subset),
                "構成比": (
                    len(subset)
                    / len(df)
                    * 100
                ),
                "+5%率": (
                    subset["Hit5"].mean()
                    * 100
                ),
                "+10%率": (
                    subset["Hit10"].mean()
                    * 100
                ),
                "+20%率": (
                    subset["Hit20"].mean()
                    * 100
                ),
                "平均最大騰落率": subset[
                    "5営業日以内最大騰落率"
                ].mean(),
            }
        )

    return results


# ============================================================
# RSI減点前後の閾値比較
# ============================================================

def analyze_rsi_effect(
    df,
    base_col,
    final_col,
    scheme_name,
):
    results = []

    base_score = df[base_col]
    final_score = df[final_col]

    max_base = int(
        base_score.max()
    )

    max_final = int(
        final_score.max()
    )

    max_score = max(
        max_base,
        max_final,
    )

    baseline10 = (
        df["Hit10"].mean()
        * 100
    )

    baseline20 = (
        df["Hit20"].mean()
        * 100
    )

    for threshold in range(
        max_score + 1
    ):

        base_subset = df[
            base_score >= threshold
        ]

        final_subset = df[
            final_score >= threshold
        ]

        if (
            len(base_subset) < MIN_SAMPLE
            and len(final_subset) < MIN_SAMPLE
        ):
            continue

        row = {
            "案": scheme_name,
            "分析": "RSI前後",
            "閾値": threshold,
            "基本件数": len(base_subset),
            "最終件数": len(final_subset),
            "基本構成比": (
                len(base_subset)
                / len(df)
                * 100
            ),
            "最終構成比": (
                len(final_subset)
                / len(df)
                * 100
            ),
        }

        if len(base_subset) >= MIN_SAMPLE:
            row["基本+10%率"] = (
                base_subset["Hit10"].mean()
                * 100
            )

            row["基本+20%率"] = (
                base_subset["Hit20"].mean()
                * 100
            )

            row["基本+10%差"] = (
                row["基本+10%率"]
                - baseline10
            )

            row["基本+20%差"] = (
                row["基本+20%率"]
                - baseline20
            )
        else:
            row["基本+10%率"] = None
            row["基本+20%率"] = None
            row["基本+10%差"] = None
            row["基本+20%差"] = None

        if len(final_subset) >= MIN_SAMPLE:
            row["最終+10%率"] = (
                final_subset["Hit10"].mean()
                * 100
            )

            row["最終+20%率"] = (
                final_subset["Hit20"].mean()
                * 100
            )

            row["最終+10%差"] = (
                row["最終+10%率"]
                - baseline10
            )

            row["最終+20%差"] = (
                row["最終+20%率"]
                - baseline20
            )
        else:
            row["最終+10%率"] = None
            row["最終+20%率"] = None
            row["最終+10%差"] = None
            row["最終+20%差"] = None

        results.append(row)

    return results


# ============================================================
# 最良閾値表示
# ============================================================

def print_best_thresholds(
    threshold_results,
    df,
):
    if not threshold_results:
        return

    result_df = pd.DataFrame(
        threshold_results
    )

    if result_df.empty:
        return

    baseline10 = (
        df["Hit10"].mean()
        * 100
    )

    baseline20 = (
        df["Hit20"].mean()
        * 100
    )

    result_df["+10%差"] = (
        result_df["+10%率"]
        - baseline10
    )

    result_df["+20%差"] = (
        result_df["+20%率"]
        - baseline20
    )

    # --------------------------------------------------------
    # +10%率
    # --------------------------------------------------------

    best10 = result_df.loc[
        result_df["+10%率"].idxmax()
    ]

    print()
    print(
        "--- +10%率が高いスコア閾値 ---"
    )

    print(
        f"スコア>={int(best10['閾値']):2d} "
        f"/ n={int(best10['件数']):4d} "
        f"/ 構成比={best10['構成比']:.2f}% "
        f"/ +10%率={best10['+10%率']:.1f}% "
        f"/ 差={best10['+10%差']:+.1f}pt "
        f"/ +20%率={best10['+20%率']:.1f}%"
    )

    # --------------------------------------------------------
    # +20%率
    # --------------------------------------------------------

    best20 = result_df.loc[
        result_df["+20%率"].idxmax()
    ]

    print()
    print(
        "--- +20%率が高いスコア閾値 ---"
    )

    print(
        f"スコア>={int(best20['閾値']):2d} "
        f"/ n={int(best20['件数']):4d} "
        f"/ 構成比={best20['構成比']:.2f}% "
        f"/ +10%率={best20['+10%率']:.1f}% "
        f"/ +20%率={best20['+20%率']:.1f}% "
        f"/ 差={best20['+20%差']:+.1f}pt"
    )


# ============================================================
# 主要閾値比較
# ============================================================

def print_key_thresholds(
    df,
    score_col,
    scheme_name,
):
    score = df[score_col]

    max_score = int(
        score.max()
    )

    # 高スコア帯を重点表示
    thresholds = [
        t
        for t in range(
            max_score + 1
        )
        if t >= max(10, max_score - 8)
    ]

    print()
    print(
        "--- 高スコア閾値一覧 ---"
    )

    print(
        "閾値   件数   構成比   "
        "+5%    +10%   +20%   平均最大"
    )

    for threshold in thresholds:

        subset = df[
            score >= threshold
        ]

        if len(subset) < MIN_SAMPLE:
            continue

        print(
            f"{threshold:4d} "
            f"{len(subset):6d} "
            f"{len(subset) / len(df) * 100:7.2f}% "
            f"{subset['Hit5'].mean() * 100:6.1f}% "
            f"{subset['Hit10'].mean() * 100:6.1f}% "
            f"{subset['Hit20'].mean() * 100:6.1f}% "
            f"{subset['5営業日以内最大騰落率'].mean():+8.2f}%"
        )


# ============================================================
# メイン
# ============================================================

def main():

    print_header(
        "初動スコア Ver4 閾値分析"
    )

    print(
        f"入力: {INPUT_FILE}"
    )

    print(
        f"最低サンプル数: {MIN_SAMPLE}"
    )

    if not INPUT_FILE.exists():

        print()

        print(
            f"入力ファイルがありません: "
            f"{INPUT_FILE}"
        )

        return

    # --------------------------------------------------------
    # 読み込み
    # --------------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE
    )

    print(
        f"検証記録数 : {len(df):,}"
    )

    # --------------------------------------------------------
    # 数値変換
    # --------------------------------------------------------

    numeric_columns = [
        "VolumeRatio",
        "VolumeIncreaseDays",
        "ChangePercent",
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

    print_header(
        "全体基準"
    )

    print(
        f"全体件数       : {len(df):,}"
    )

    print(
        f"+5%率          : "
        f"{df['Hit5'].mean() * 100:.1f}%"
    )

    print(
        f"+10%率         : "
        f"{df['Hit10'].mean() * 100:.1f}%"
    )

    print(
        f"+20%率         : "
        f"{df['Hit20'].mean() * 100:.1f}%"
    )

    print(
        f"平均最大騰落率 : "
        f"{df['5営業日以内最大騰落率'].mean():+.2f}%"
    )

    # --------------------------------------------------------
    # 条件マスク
    # --------------------------------------------------------

    print_header(
        "条件マスク作成"
    )

    masks = build_masks(df)

    for name, mask in masks.items():

        print(
            f"{name:<24} "
            f"n={int(mask.sum()):,}"
        )

    # --------------------------------------------------------
    # 案
    # --------------------------------------------------------

    schemes = build_schemes()

    all_results = []

    summary_results = []

    # --------------------------------------------------------
    # 各案
    # --------------------------------------------------------

    for scheme_name, scheme in schemes.items():

        print_header(
            scheme_name
        )

        # 基本スコア
        base_score = calc_base_score(
            df,
            masks,
            scheme,
        )

        # RSI減点
        rsi_penalty = calc_rsi_penalty(
            df
        )

        # 最終スコア
        final_score = (
            base_score
            + rsi_penalty
        )

        base_col = (
            f"{scheme_name}_基本"
        )

        final_col = (
            f"{scheme_name}_最終"
        )

        df[base_col] = (
            base_score
        )

        df[final_col] = (
            final_score
        )

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

        # ----------------------------------------------------
        # 閾値分析
        # ----------------------------------------------------

        threshold_results = (
            analyze_thresholds(
                df,
                base_col,
                scheme_name,
            )
        )

        all_results.extend(
            threshold_results
        )

        print_best_thresholds(
            threshold_results,
            df,
        )

        # ----------------------------------------------------
        # 高スコア閾値一覧
        # ----------------------------------------------------

        print_key_thresholds(
            df,
            base_col,
            scheme_name,
        )

        # ----------------------------------------------------
        # スコア別
        # ----------------------------------------------------

        score_band_results = (
            analyze_score_bands(
                df,
                base_col,
                scheme_name,
            )
        )

        all_results.extend(
            score_band_results
        )

        # ----------------------------------------------------
        # RSI前後
        # ----------------------------------------------------

        rsi_results = (
            analyze_rsi_effect(
                df,
                base_col,
                final_col,
                scheme_name,
            )
        )

        all_results.extend(
            rsi_results
        )

        # ----------------------------------------------------
        # 主要閾値
        # ----------------------------------------------------

        threshold_df = pd.DataFrame(
            threshold_results
        )

        if not threshold_df.empty:

            baseline10 = (
                df["Hit10"].mean()
                * 100
            )

            baseline20 = (
                df["Hit20"].mean()
                * 100
            )

            threshold_df["+10%差"] = (
                threshold_df["+10%率"]
                - baseline10
            )

            threshold_df["+20%差"] = (
                threshold_df["+20%率"]
                - baseline20
            )

            # +10%率上位
            best10 = threshold_df.loc[
                threshold_df["+10%率"].idxmax()
            ]

            # +20%率上位
            best20 = threshold_df.loc[
                threshold_df["+20%率"].idxmax()
            ]

            summary_results.append(
                {
                    "案": scheme_name,
                    "基本最大": int(
                        base_score.max()
                    ),
                    "最終最大": int(
                        final_score.max()
                    ),
                    "平均基本": base_score.mean(),
                    "平均最終": final_score.mean(),
                    "RSI減点件数": int(
                        (rsi_penalty < 0).sum()
                    ),
                    "最高+10%閾値": int(
                        best10["閾値"]
                    ),
                    "最高+10%率": best10[
                        "+10%率"
                    ],
                    "最高+10%件数": int(
                        best10["件数"]
                    ),
                    "最高+20%閾値": int(
                        best20["閾値"]
                    ),
                    "最高+20%率": best20[
                        "+20%率"
                    ],
                    "最高+20%件数": int(
                        best20["件数"]
                    ),
                }
            )

    # ========================================================
    # 案比較
    # ========================================================

    print_header(
        "Ver4 案比較"
    )

    summary_df = pd.DataFrame(
        summary_results
    )

    if not summary_df.empty:

        for _, row in summary_df.iterrows():

            print(
                f"{row['案']:<20} "
                f"/ 基本最大={int(row['基本最大']):2d} "
                f"/ +10%最高="
                f"{int(row['最高+10%閾値']):2d}点 "
                f"n={int(row['最高+10%件数']):4d} "
                f"率={row['最高+10%率']:.1f}% "
                f"/ +20%最高="
                f"{int(row['最高+20%閾値']):2d}点 "
                f"n={int(row['最高+20%件数']):4d} "
                f"率={row['最高+20%率']:.1f}%"
            )

    # ========================================================
    # 保存
    # ========================================================

    print_header(
        "分析結果保存"
    )

    result_df = pd.DataFrame(
        all_results
    )

    output_rows = []

    # 概要
    output_rows.append(
        {
            "案": "=== 概要 ==="
        }
    )

    output_rows.extend(
        summary_df.to_dict(
            "records"
        )
    )

    # 詳細
    output_rows.append(
        {
            "案": "=== 詳細 ==="
        }
    )

    output_rows.extend(
        result_df.to_dict(
            "records"
        )
    )

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

    # ========================================================
    # 完了
    # ========================================================

    print_header(
        "初動スコア Ver4 閾値分析完了"
    )

    print(
        f"検証記録数 : {len(df):,}"
    )

    print(
        f"比較案      : {len(schemes)}"
    )

    print(
        f"全体+10%率 : "
        f"{df['Hit10'].mean() * 100:.1f}%"
    )

    print(
        f"全体+20%率 : "
        f"{df['Hit20'].mean() * 100:.1f}%"
    )

    print(
        f"保存先      : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()