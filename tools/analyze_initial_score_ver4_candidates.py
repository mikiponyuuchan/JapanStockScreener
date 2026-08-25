from pathlib import Path
import pandas as pd


# ============================================================
# 初動スコア Ver3 候補配点比較
# ============================================================

INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
     "data/tracking/initial_score_ver4_candidate_analysis.csv"
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
# 段階式スコア
# ============================================================

def calc_base_score(df, masks, scheme):
    score = pd.Series(0.0, index=df.index)

    # --------------------------------------------------------
    # 前日比
    # 「最高ランクのみ」加点
    # --------------------------------------------------------
    price_points = scheme["price_points"]

    score += masks["前日比+1%以上"].astype(float) * price_points[1]
    score = score.where(
        ~masks["前日比+3%以上"],
        score - price_points[1] + price_points[3]
    )
    score = score.where(
        ~masks["前日比+5%以上"],
        score - price_points[3] + price_points[5]
    )

    # --------------------------------------------------------
    # 出来高倍率
    # 「最高ランクのみ」加点
    # --------------------------------------------------------
    volume_points = scheme["volume_points"]

    volume_score = (
        masks["出来高1.5倍以上"].astype(float) * volume_points[1.5]
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
        score += masks[condition].astype(float) * points

    return score


# ============================================================
# RSI減点
# ============================================================

def calc_rsi_penalty(df):
    rsi = pd.to_numeric(df["RSI"], errors="coerce")

    penalty = pd.Series(0.0, index=df.index)

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
# 案定義
# ============================================================

def build_schemes():

    return {

        "Ver4_A_初動特化": {

            "price_points": {
                1: 1,
                3: 4,
                5: 8,
            },

            "volume_points": {
                1.5: 0,
                2.0: 2,
                3.0: 6,
            },

            "other_points": {
                "ブレイク": 2,
                "30日高値更新": 2,
                "MACD GC": 0,
            },
        },

        "Ver4_B_高騰重視": {

            "price_points": {
                1: 1,
                3: 3,
                5: 6,
            },

            "volume_points": {
                1.5: 1,
                2.0: 3,
                3.0: 6,
            },

            "other_points": {
                "ブレイク": 2,
                "30日高値更新": 2,
                "MACD GC": 0,
            },
        },

        "Ver4_C_超初動": {

            "price_points": {
                1: 0,
                3: 4,
                5: 8,
            },

            "volume_points": {
                1.5: 0,
                2.0: 3,
                3.0: 8,
            },

            "other_points": {
                "ブレイク": 3,
                "30日高値更新": 3,
                "MACD GC": 0,
            },
        },
    }


# ============================================================
# スコア帯分析
# ============================================================

def analyze_score_bands(df, score_col, scheme_name):
    result = []

    score = df[score_col]

    max_score = int(score.max())

    # 1点刻み
    for s in range(max_score, -1, -1):
        subset = df[score == s]

        if len(subset) < MIN_SAMPLE:
            continue

        result.append(
            {
                "案": scheme_name,
                "分析": "スコア別",
                "スコア下限": s,
                "スコア上限": s,
                "件数": len(subset),
                "+5%率": subset["Hit5"].mean() * 100,
                "+10%率": subset["Hit10"].mean() * 100,
                "+20%率": subset["Hit20"].mean() * 100,
                "平均最大騰落率": subset["5営業日以内最大騰落率"].mean(),
            }
        )

    return result


# ============================================================
# 累積スコア分析
# ============================================================

def analyze_thresholds(df, score_col, scheme_name):
    result = []

    score = df[score_col]
    max_score = int(score.max())

    for threshold in range(max_score + 1):
        subset = df[score >= threshold]

        if len(subset) < MIN_SAMPLE:
            continue

        result.append(
            {
                "案": scheme_name,
                "分析": "以上",
                "スコア下限": threshold,
                "スコア上限": max_score,
                "件数": len(subset),
                "構成比": len(subset) / len(df) * 100,
                "+5%率": subset["Hit5"].mean() * 100,
                "+10%率": subset["Hit10"].mean() * 100,
                "+20%率": subset["Hit20"].mean() * 100,
                "平均最大騰落率": subset["5営業日以内最大騰落率"].mean(),
            }
        )

    return result


# ============================================================
# メイン
# ============================================================

def main():
    print_header("初動スコア Ver3 候補配点比較")

    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLE}")

    if not INPUT_FILE.exists():
        print()
        print(f"入力ファイルがありません: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)

    print(f"検証記録数 : {len(df):,}")

    # 数値変換
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
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 全体基準
    print_header("全体基準")

    print(f"全体件数       : {len(df):,}")
    print(f"+5%率          : {df['Hit5'].mean() * 100:.1f}%")
    print(f"+10%率         : {df['Hit10'].mean() * 100:.1f}%")
    print(f"+20%率         : {df['Hit20'].mean() * 100:.1f}%")
    print(
        f"平均最大騰落率 : "
        f"{df['5営業日以内最大騰落率'].mean():+.2f}%"
    )

    # 条件マスク
    print_header("条件マスク作成")

    masks = build_masks(df)

    for name, mask in masks.items():
        print(f"{name:<24} n={int(mask.sum()):,}")

    # 案
    schemes = build_schemes()

    all_results = []
    summary_results = []

    # 各案を評価
    for scheme_name, scheme in schemes.items():

        print_header(f"{scheme_name}")

        base_score = calc_base_score(df, masks, scheme)
        rsi_penalty = calc_rsi_penalty(df)

        final_score = base_score + rsi_penalty

        base_col = f"{scheme_name}_基本"
        final_col = f"{scheme_name}_最終"

        df[base_col] = base_score
        df[final_col] = final_score

        print(f"基本スコア最大 : {base_score.max():.0f}")
        print(f"最終スコア最大 : {final_score.max():.0f}")
        print(f"RSI減点件数    : {(rsi_penalty < 0).sum():,}")

        # スコア別
        all_results.extend(
            analyze_score_bands(
                df,
                base_col,
                scheme_name,
            )
        )

        # 閾値別
        threshold_results = analyze_thresholds(
            df,
            base_col,
            scheme_name,
        )

        all_results.extend(threshold_results)

        # 主要閾値候補
        threshold_results_df = pd.DataFrame(threshold_results)

        if not threshold_results_df.empty:
            baseline_10 = df["Hit10"].mean() * 100
            baseline_20 = df["Hit20"].mean() * 100

            threshold_results_df["+10%差"] = (
                threshold_results_df["+10%率"] - baseline_10
            )

            threshold_results_df["+20%差"] = (
                threshold_results_df["+20%率"] - baseline_20
            )

            best10 = threshold_results_df.sort_values(
                "+10%率",
                ascending=False,
            ).iloc[0]

            best20 = threshold_results_df.sort_values(
                "+20%率",
                ascending=False,
            ).iloc[0]

            print()
            print("--- +10%率が高いスコア閾値 ---")
            print(
                f"スコア>={int(best10['スコア下限']):2d} "
                f"/ n={int(best10['件数']):4d} "
                f"/ +10%率={best10['+10%率']:.1f}% "
                f"/ 差={best10['+10%差']:+.1f}pt "
                f"/ +20%率={best10['+20%率']:.1f}%"
            )

            print()
            print("--- +20%率が高いスコア閾値 ---")
            print(
                f"スコア>={int(best20['スコア下限']):2d} "
                f"/ n={int(best20['件数']):4d} "
                f"/ +10%率={best20['+10%率']:.1f}% "
                f"/ +20%率={best20['+20%率']:.1f}% "
                f"/ 差={best20['+20%差']:+.1f}pt"
            )

        # スコア上位
        top = df.sort_values(
            base_col,
            ascending=False,
        ).head(10)

        print()
        print("--- 基本スコア上位10件 ---")

        for _, row in top.iterrows():
            print(
                f"{row['検出日']} "
                f"{str(row['コード']) if pd.notna(row['コード']) else row['コード']} "
                f"{row['銘柄名']} "
                f"/ 基本={row[base_col]:.0f} "
                f"/ RSI={row['RSI']:.1f} "
                f"/ 最終={row[final_col]:.0f} "
                f"/ +10={int(row['Hit10'])} "
                f"/ +20={int(row['Hit20'])}"
            )

        summary_results.append(
            {
                "案": scheme_name,
                "基本スコア最大": base_score.max(),
                "最終スコア最大": final_score.max(),
                "平均基本スコア": base_score.mean(),
                "平均最終スコア": final_score.mean(),
                "RSI減点件数": int((rsi_penalty < 0).sum()),
            }
        )

    # 保存
    print_header("分析結果保存")

    result_df = pd.DataFrame(all_results)
    summary_df = pd.DataFrame(summary_results)

    # 分析結果と概要を同一CSVにまとめる
    output_rows = []

    output_rows.append(
        {
            "案": "=== 概要 ===",
        }
    )

    output_rows.extend(summary_df.to_dict("records"))

    output_rows.append(
        {
            "案": "=== 詳細 ===",
        }
    )

    output_rows.extend(result_df.to_dict("records"))

    final_output = pd.DataFrame(output_rows)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_output.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"保存先: {OUTPUT_FILE}")

    print_header("初動スコア Ver3 候補比較完了")
    print(f"検証記録数 : {len(df):,}")
    print(f"比較案      : {len(schemes)}")
    print(f"全体+10%率 : {df['Hit10'].mean() * 100:.1f}%")
    print(f"全体+20%率 : {df['Hit20'].mean() * 100:.1f}%")
    print(f"保存先      : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()