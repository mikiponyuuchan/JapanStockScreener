from pathlib import Path
import itertools
import pandas as pd


# ============================================================
# 初動スコア Ver4 条件組み合わせ分析
# ============================================================

INPUT_FILE = Path(
    "data/tracking/initial_score_factor_raw.csv"
)

OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver4_combination_analysis.csv"
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

    masks["ブレイク初日"] = (
        df["BreakoutFirstDay"]
        .fillna(False)
        .astype(bool)
    )

    masks["30日高値更新"] = (
        df["New30High"]
        .fillna(False)
        .astype(bool)
    )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    masks["MACD GC"] = (
        df["MACD_GC"]
        .fillna(False)
        .astype(bool)
    )

    # --------------------------------------------------------
    # トレンド
    # --------------------------------------------------------

    masks["MA5上"] = (
        df["AboveMA5"]
        .fillna(False)
        .astype(bool)
    )

    masks["MA25上"] = (
        df["AboveMA25"]
        .fillna(False)
        .astype(bool)
    )

    masks["MA75上"] = (
        df["AboveMA75"]
        .fillna(False)
        .astype(bool)
    )

    return masks


# ============================================================
# RSI減点
# ============================================================

def calc_rsi_penalty(df):

    rsi = pd.to_numeric(
        df["RSI"],
        errors="coerce"
    )

    penalty = pd.Series(
        0.0,
        index=df.index
    )

    penalty = penalty.where(
        ~((rsi >= 85) & (rsi < 90)),
        -1
    )

    penalty = penalty.where(
        ~((rsi >= 90) & (rsi < 95)),
        -2
    )

    penalty = penalty.where(
        ~(rsi >= 95),
        -3
    )

    return penalty


# ============================================================
# Ver4 C スコア
#
# 現時点で最も成績が良かった
# 「Ver4_C_超初動」を基準にする
# ============================================================

def calc_ver4_c_score(df, masks):

    score = pd.Series(
        0.0,
        index=df.index
    )

    # --------------------------------------------------------
    # 前日比
    #
    # +1% = 1
    # +3% = 2
    # +5% = 3
    #
    # 最高ランクのみ
    # --------------------------------------------------------

    price_score = pd.Series(
        0.0,
        index=df.index
    )

    price_score = price_score.where(
        ~masks["前日比+1%以上"],
        1
    )

    price_score = price_score.where(
        ~masks["前日比+3%以上"],
        2
    )

    price_score = price_score.where(
        ~masks["前日比+5%以上"],
        3
    )

    score += price_score

    # --------------------------------------------------------
    # 出来高
    #
    # 1.5倍 = 1
    # 2倍   = 2
    # 3倍   = 3
    # --------------------------------------------------------

    volume_score = pd.Series(
        0.0,
        index=df.index
    )

    volume_score = volume_score.where(
        ~masks["出来高1.5倍以上"],
        1
    )

    volume_score = volume_score.where(
        ~masks["出来高2倍以上"],
        2
    )

    volume_score = volume_score.where(
        ~masks["出来高3倍以上"],
        3
    )

    score += volume_score

    # --------------------------------------------------------
    # ブレイク
    # --------------------------------------------------------

    score += (
        masks["ブレイク"].astype(float) * 2
    )

    score += (
        masks["ブレイク初日"].astype(float) * 2
    )

    # --------------------------------------------------------
    # 30日高値
    # --------------------------------------------------------

    score += (
        masks["30日高値更新"].astype(float) * 2
    )

    # --------------------------------------------------------
    # MACD GC
    # --------------------------------------------------------

    score += (
        masks["MACD GC"].astype(float) * 1
    )

    # --------------------------------------------------------
    # MA
    # --------------------------------------------------------

    score += (
        masks["MA5上"].astype(float) * 1
    )

    score += (
        masks["MA25上"].astype(float) * 1
    )

    score += (
        masks["MA75上"].astype(float) * 1
    )

    return score


# ============================================================
# 条件組み合わせ分析
# ============================================================

def analyze_combinations(
    df,
    masks,
    condition_names,
    max_combination_size=4
):

    results = []

    baseline_5 = df["Hit5"].mean() * 100
    baseline_10 = df["Hit10"].mean() * 100
    baseline_20 = df["Hit20"].mean() * 100

    # --------------------------------------------------------
    # 2条件～最大4条件
    # --------------------------------------------------------

    for size in range(
        2,
        max_combination_size + 1
    ):

        for combination in itertools.combinations(
            condition_names,
            size
        ):

            mask = pd.Series(
                True,
                index=df.index
            )

            for condition in combination:
                mask &= masks[condition]

            subset = df[mask]

            count = len(subset)

            if count < MIN_SAMPLE:
                continue

            hit5 = subset["Hit5"].mean() * 100
            hit10 = subset["Hit10"].mean() * 100
            hit20 = subset["Hit20"].mean() * 100

            avg_max = subset[
                "5営業日以内最大騰落率"
            ].mean()

            results.append(
                {
                    "条件数": size,
                    "条件組み合わせ": " + ".join(
                        combination
                    ),
                    "件数": count,
                    "構成比": (
                        count / len(df) * 100
                    ),
                    "+5%率": hit5,
                    "+10%率": hit10,
                    "+20%率": hit20,
                    "+5%差": hit5 - baseline_5,
                    "+10%差": hit10 - baseline_10,
                    "+20%差": hit20 - baseline_20,
                    "平均最大騰落率": avg_max,
                }
            )

    return results


# ============================================================
# 高スコア帯限定の組み合わせ分析
# ============================================================

def analyze_high_score_combinations(
    df,
    masks,
    score,
    condition_names,
    threshold=13,
    max_combination_size=3
):

    high_score_mask = score >= threshold

    high_df = df[high_score_mask]

    results = []

    if len(high_df) == 0:
        return results

    baseline_10 = high_df["Hit10"].mean() * 100
    baseline_20 = high_df["Hit20"].mean() * 100

    for size in range(
        2,
        max_combination_size + 1
    ):

        for combination in itertools.combinations(
            condition_names,
            size
        ):

            mask = pd.Series(
                True,
                index=df.index
            )

            for condition in combination:
                mask &= masks[condition]

            mask &= high_score_mask

            subset = df[mask]

            count = len(subset)

            if count < MIN_SAMPLE:
                continue

            hit10 = subset["Hit10"].mean() * 100
            hit20 = subset["Hit20"].mean() * 100

            results.append(
                {
                    "スコア帯": f"{threshold}点以上",
                    "条件数": size,
                    "条件組み合わせ": " + ".join(
                        combination
                    ),
                    "件数": count,
                    "構成比": (
                        count / len(high_df) * 100
                    ),
                    "+10%率": hit10,
                    "+20%率": hit20,
                    "+10%差": hit10 - baseline_10,
                    "+20%差": hit20 - baseline_20,
                    "平均最大騰落率": subset[
                        "5営業日以内最大騰落率"
                    ].mean(),
                }
            )

    return results


# ============================================================
# メイン
# ============================================================

def main():

    print_header(
        "初動スコア Ver4 条件組み合わせ分析"
    )

    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLE}")

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
            errors="coerce"
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
    # Ver4 C スコア
    # --------------------------------------------------------

    print_header(
        "Ver4_C_超初動 スコア計算"
    )

    score = calc_ver4_c_score(
        df,
        masks
    )

    rsi_penalty = calc_rsi_penalty(
        df
    )

    final_score = (
        score + rsi_penalty
    )

    df["Ver4基本スコア"] = score
    df["Ver4最終スコア"] = final_score

    print(
        f"基本スコア最大 : "
        f"{score.max():.0f}"
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
    # 今回重点的に見る条件
    # --------------------------------------------------------

    key_conditions = [
        "前日比+3%以上",
        "前日比+5%以上",
        "出来高2倍以上",
        "出来高3倍以上",
        "ブレイク",
        "30日高値更新",
        "MACD GC",
    ]

    # --------------------------------------------------------
    # 2～4条件組み合わせ
    # --------------------------------------------------------

    print_header(
        "主要条件 2～4条件 組み合わせ分析"
    )

    combination_results = (
        analyze_combinations(
            df,
            masks,
            key_conditions,
            max_combination_size=4,
        )
    )

    combination_df = pd.DataFrame(
        combination_results
    )

    if not combination_df.empty:

        print()
        print(
            "--- +20%率 上位20組み合わせ ---"
        )

        top20 = (
            combination_df
            .sort_values(
                [
                    "+20%率",
                    "+10%率",
                    "件数",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
            )
            .head(20)
        )

        for _, row in top20.iterrows():

            print(
                f"{row['条件数']}条件 "
                f"/ n={int(row['件数']):4d} "
                f"/ +10%="
                f"{row['+10%率']:5.1f}% "
                f"/ +20%="
                f"{row['+20%率']:5.1f}% "
                f"/ +20%差="
                f"{row['+20%差']:+5.1f}pt "
                f"/ 平均最大="
                f"{row['平均最大騰落率']:+6.2f}% "
                f"/ {row['条件組み合わせ']}"
            )

        print()
        print(
            "--- +10%率 上位20組み合わせ ---"
        )

        top20_10 = (
            combination_df
            .sort_values(
                [
                    "+10%率",
                    "+20%率",
                    "件数",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
            )
            .head(20)
        )

        for _, row in top20_10.iterrows():

            print(
                f"{row['条件数']}条件 "
                f"/ n={int(row['件数']):4d} "
                f"/ +10%="
                f"{row['+10%率']:5.1f}% "
                f"/ +20%="
                f"{row['+20%率']:5.1f}% "
                f"/ +10%差="
                f"{row['+10%差']:+5.1f}pt "
                f"/ 平均最大="
                f"{row['平均最大騰落率']:+6.2f}% "
                f"/ {row['条件組み合わせ']}"
            )

    # --------------------------------------------------------
    # 13点以上
    # --------------------------------------------------------

    high13_results = (
        analyze_high_score_combinations(
            df,
            masks,
            score,
            key_conditions,
            threshold=13,
            max_combination_size=3,
        )
    )

    high13_df = pd.DataFrame(
        high13_results
    )

    print_header(
        "Ver4 13点以上 条件組み合わせ"
    )

    if not high13_df.empty:

        top13 = (
            high13_df
            .sort_values(
                [
                    "+20%率",
                    "+10%率",
                    "件数",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
            )
            .head(20)
        )

        for _, row in top13.iterrows():

            print(
                f"{row['条件数']}条件 "
                f"/ n={int(row['件数']):3d} "
                f"/ +10%="
                f"{row['+10%率']:5.1f}% "
                f"/ +20%="
                f"{row['+20%率']:5.1f}% "
                f"/ +20%差="
                f"{row['+20%差']:+5.1f}pt "
                f"/ {row['条件組み合わせ']}"
            )

    # --------------------------------------------------------
    # 14点以上
    # --------------------------------------------------------

    high14_results = (
        analyze_high_score_combinations(
            df,
            masks,
            score,
            key_conditions,
            threshold=14,
            max_combination_size=3,
        )
    )

    high14_df = pd.DataFrame(
        high14_results
    )

    print_header(
        "Ver4 14点以上 条件組み合わせ"
    )

    if not high14_df.empty:

        top14 = (
            high14_df
            .sort_values(
                [
                    "+20%率",
                    "+10%率",
                    "件数",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
            )
            .head(20)
        )

        for _, row in top14.iterrows():

            print(
                f"{row['条件数']}条件 "
                f"/ n={int(row['件数']):3d} "
                f"/ +10%="
                f"{row['+10%率']:5.1f}% "
                f"/ +20%="
                f"{row['+20%率']:5.1f}% "
                f"/ +20%差="
                f"{row['+20%差']:+5.1f}pt "
                f"/ {row['条件組み合わせ']}"
            )

    # --------------------------------------------------------
    # 出来高3倍 + MACD GC
    # --------------------------------------------------------

    print_header(
        "重点組み合わせ確認"
    )

    focus_combinations = [
        (
            "出来高3倍以上",
            "MACD GC",
        ),
        (
            "出来高3倍以上",
            "ブレイク",
        ),
        (
            "出来高3倍以上",
            "30日高値更新",
        ),
        (
            "出来高3倍以上",
            "前日比+5%以上",
        ),
        (
            "出来高2倍以上",
            "MACD GC",
        ),
        (
            "出来高2倍以上",
            "ブレイク",
        ),
        (
            "出来高2倍以上",
            "30日高値更新",
        ),
        (
            "前日比+5%以上",
            "出来高3倍以上",
        ),
        (
            "前日比+5%以上",
            "ブレイク",
        ),
        (
            "前日比+5%以上",
            "30日高値更新",
        ),
    ]

    focus_results = []

    for combination in focus_combinations:

        mask = pd.Series(
            True,
            index=df.index
        )

        for condition in combination:

            mask &= masks[condition]

        subset = df[mask]

        count = len(subset)

        if count < MIN_SAMPLE:
            print(
                f"{' + '.join(combination)} "
                f"/ n={count} "
                f"→ サンプル不足"
            )
            continue

        hit5 = subset["Hit5"].mean() * 100
        hit10 = subset["Hit10"].mean() * 100
        hit20 = subset["Hit20"].mean() * 100

        avg_max = subset[
            "5営業日以内最大騰落率"
        ].mean()

        focus_results.append(
            {
                "条件数": len(combination),
                "条件組み合わせ": " + ".join(
                    combination
                ),
                "件数": count,
                "+5%率": hit5,
                "+10%率": hit10,
                "+20%率": hit20,
                "平均最大騰落率": avg_max,
            }
        )

        print(
            f"{' + '.join(combination)} "
            f"/ n={count:4d} "
            f"/ +5%={hit5:5.1f}% "
            f"/ +10%={hit10:5.1f}% "
            f"/ +20%={hit20:5.1f}% "
            f"/ 平均最大={avg_max:+6.2f}%"
        )

    focus_df = pd.DataFrame(
        focus_results
    )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    print_header(
        "分析結果保存"
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with pd.ExcelWriter(
        OUTPUT_FILE.with_suffix(".xlsx"),
        engine="openpyxl"
    ) as writer:

        if not combination_df.empty:

            combination_df.to_excel(
                writer,
                sheet_name="全組み合わせ",
                index=False
            )

        if not high13_df.empty:

            high13_df.to_excel(
                writer,
                sheet_name="13点以上",
                index=False
            )

        if not high14_df.empty:

            high14_df.to_excel(
                writer,
                sheet_name="14点以上",
                index=False
            )

        if not focus_df.empty:

            focus_df.to_excel(
                writer,
                sheet_name="重点組み合わせ",
                index=False
            )

    # CSVも保存
    if not combination_df.empty:

        combination_df.to_csv(
            OUTPUT_FILE,
            index=False,
            encoding="utf-8-sig"
        )

    print(
        f"CSV保存先: {OUTPUT_FILE}"
    )

    print(
        f"Excel保存先: "
        f"{OUTPUT_FILE.with_suffix('.xlsx')}"
    )

    # --------------------------------------------------------
    # 完了
    # --------------------------------------------------------

    print_header(
        "初動スコア Ver4 条件組み合わせ分析完了"
    )

    print(
        f"検証記録数 : {len(df):,}"
    )

    print(
        f"組み合わせ件数 : "
        f"{len(combination_df):,}"
    )

    print(
        f"13点以上 : "
        f"{int((score >= 13).sum()):,}件"
    )

    print(
        f"14点以上 : "
        f"{int((score >= 14).sum()):,}件"
    )

    print(
        f"CSV保存先 : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()