from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd


# ============================================================
# 設定
# ============================================================

INPUT_PATH = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_PATH = Path(
    "data/tracking/initial_score_ver3_monotonicity_analysis.csv"
)

MIN_SAMPLE = 10


# ============================================================
# Ver3候補配点
#
# analyze_initial_score_ver3_candidates.py と同じ配点を使用
#
# A : 高騰初動特化
# B : バランス型
# C : 取りこぼし防止型
#
# ※ RSIは基本スコアに含めず、後段の減点補正
# ============================================================

SCORING_PLANS = {
    "A_高騰初動特化": {
        "ChangePercent_1": 1,
        "ChangePercent_3": 2,
        "ChangePercent_5": 4,

        "VolumeRatio_1.5": 1,
        "VolumeRatio_2": 3,
        "VolumeRatio_3": 5,

        "VolumeIncreaseDays_1": 1,
        "VolumeIncreaseDays_2": 2,
        "VolumeIncreaseDays_3": 3,

        "BreakoutSignal": 3,
        "BreakoutFirstDay": 2,
        "New30High": 3,

        "AboveMA5": 1,
        "AboveMA25": 1,
        "AboveMA75": 1,

        "MACD_GC": 2,
    },

    "B_バランス型": {
        "ChangePercent_1": 1,
        "ChangePercent_3": 2,
        "ChangePercent_5": 3,

        "VolumeRatio_1.5": 1,
        "VolumeRatio_2": 2,
        "VolumeRatio_3": 4,

        "VolumeIncreaseDays_1": 1,
        "VolumeIncreaseDays_2": 2,
        "VolumeIncreaseDays_3": 3,

        "BreakoutSignal": 2,
        "BreakoutFirstDay": 1,
        "New30High": 2,

        "AboveMA5": 1,
        "AboveMA25": 1,
        "AboveMA75": 1,

        "MACD_GC": 1,
    },

    "C_取りこぼし防止型": {
        "ChangePercent_1": 1,
        "ChangePercent_3": 2,
        "ChangePercent_5": 2,

        "VolumeRatio_1.5": 1,
        "VolumeRatio_2": 2,
        "VolumeRatio_3": 3,

        "VolumeIncreaseDays_1": 1,
        "VolumeIncreaseDays_2": 1,
        "VolumeIncreaseDays_3": 2,

        "BreakoutSignal": 2,
        "BreakoutFirstDay": 1,
        "New30High": 2,

        "AboveMA5": 1,
        "AboveMA25": 1,
        "AboveMA75": 1,

        "MACD_GC": 1,
    },
}


# ============================================================
# ユーティリティ
# ============================================================

def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def make_masks(df):
    """
    初動条件マスクを作成
    """

    masks = {}

    change = safe_numeric(df["ChangePercent"])
    volume_ratio = safe_numeric(df["VolumeRatio"])
    volume_days = safe_numeric(df["VolumeIncreaseDays"])
    breakout = safe_numeric(df["BreakoutSignal"])
    breakout_first = safe_numeric(df["BreakoutFirstDay"])
    new30 = safe_numeric(df["New30High"])
    ma5 = safe_numeric(df["AboveMA5"])
    ma25 = safe_numeric(df["AboveMA25"])
    ma75 = safe_numeric(df["AboveMA75"])
    macd = safe_numeric(df["MACD_GC"])

    masks["ChangePercent_1"] = change >= 1
    masks["ChangePercent_3"] = change >= 3
    masks["ChangePercent_5"] = change >= 5

    masks["VolumeRatio_1.5"] = volume_ratio >= 1.5
    masks["VolumeRatio_2"] = volume_ratio >= 2
    masks["VolumeRatio_3"] = volume_ratio >= 3

    masks["VolumeIncreaseDays_1"] = volume_days >= 1
    masks["VolumeIncreaseDays_2"] = volume_days >= 2
    masks["VolumeIncreaseDays_3"] = volume_days >= 3

    masks["BreakoutSignal"] = breakout == 1
    masks["BreakoutFirstDay"] = breakout_first == 1
    masks["New30High"] = new30 == 1

    masks["AboveMA5"] = ma5 == 1
    masks["AboveMA25"] = ma25 == 1
    masks["AboveMA75"] = ma75 == 1

    masks["MACD_GC"] = macd == 1

    return masks


def calculate_basic_score(df, masks, weights):
    """
    基本スコアを計算する。

    同一系列の条件は、
    例:
        +1%以上
        +3%以上
        +5%以上

    のように累積する。
    """

    score = pd.Series(0.0, index=df.index)

    for name, weight in weights.items():
        if name not in masks:
            raise KeyError(f"条件マスクがありません: {name}")

        score += masks[name].astype(float) * weight

    return score


def calculate_rsi_penalty(df):
    """
    RSI減点。

    以前決めたB案：
        84.99以下 : 0
        85～89.99 : -1
        90～94.99 : -2
        95以上    : -3
    """

    rsi = safe_numeric(df["RSI"])

    penalty = pd.Series(0.0, index=df.index)

    penalty[(rsi >= 85) & (rsi < 90)] = -1
    penalty[(rsi >= 90) & (rsi < 95)] = -2
    penalty[rsi >= 95] = -3

    return penalty


def calculate_score(df, masks, weights):
    basic = calculate_basic_score(df, masks, weights)
    penalty = calculate_rsi_penalty(df)

    final = basic + penalty

    return basic, penalty, final


def add_result_columns(df):
    """
    実績列を数値化。
    """

    result = df.copy()

    for col in [
        "5営業日以内最大騰落率",
        "Hit5",
        "Hit10",
        "Hit20",
    ]:
        if col in result.columns:
            result[col] = safe_numeric(result[col])

    return result


# ============================================================
# スコア別集計
# ============================================================

def analyze_by_exact_score(df, score_col, plan_name):
    rows = []

    grouped = df.groupby(score_col, dropna=False)

    for score, group in grouped:
        if pd.isna(score):
            continue

        n = len(group)

        if n < MIN_SAMPLE:
            continue

        hit5 = group["Hit5"].mean() * 100
        hit10 = group["Hit10"].mean() * 100
        hit20 = group["Hit20"].mean() * 100

        avg_max = group["5営業日以内最大騰落率"].mean()

        rows.append(
            {
                "分析種別": "スコア別",
                "案": plan_name,
                "スコア": float(score),
                "n": n,
                "+5%率": hit5,
                "+10%率": hit10,
                "+20%率": hit20,
                "平均最大騰落率": avg_max,
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# スコア帯集計
# ============================================================

def make_score_bins(max_score):
    """
    スコア帯。

    低スコア側は広く、高スコア側は細かく確認できるよう、
    4点刻みを基本とする。

    例:
        0-3
        4-7
        8-11
        12-15
        16-19
        20-23
    """

    bins = list(range(0, max_score + 5, 4))

    if bins[-1] <= max_score:
        bins.append(bins[-1] + 4)

    return bins


def analyze_score_bands(df, score_col, plan_name):
    max_score = int(df[score_col].max())

    bins = make_score_bins(max_score)

    labels = []

    for i in range(len(bins) - 1):
        low = bins[i]
        high = bins[i + 1] - 1
        labels.append(f"{low}-{high}")

    temp = df.copy()

    temp["_score_band"] = pd.cut(
        temp[score_col],
        bins=bins,
        labels=labels,
        right=False,
        include_lowest=True,
    )

    rows = []

    grouped = temp.groupby(
        "_score_band",
        observed=False,
    )

    previous = None

    for band, group in grouped:

        if len(group) == 0:
            continue

        n = len(group)

        if n < MIN_SAMPLE:
            continue

        hit5 = group["Hit5"].mean() * 100
        hit10 = group["Hit10"].mean() * 100
        hit20 = group["Hit20"].mean() * 100
        avg_max = group["5営業日以内最大騰落率"].mean()

        delta10 = None
        delta20 = None

        if previous is not None:
            delta10 = hit10 - previous["+10%率"]
            delta20 = hit20 - previous["+20%率"]

        row = {
            "分析種別": "スコア帯",
            "案": plan_name,
            "スコア": str(band),
            "n": n,
            "+5%率": hit5,
            "+10%率": hit10,
            "+20%率": hit20,
            "平均最大騰落率": avg_max,
            "前帯との差(+10%)": delta10,
            "前帯との差(+20%)": delta20,
        }

        rows.append(row)

        previous = {
            "+10%率": hit10,
            "+20%率": hit20,
        }

    return pd.DataFrame(rows)


# ============================================================
# 単調性評価
# ============================================================

def calculate_monotonicity(df, score_col, plan_name):
    """
    スコア別実績から単調性を評価。

    Spearman相関:
        スコアが上がるほど実績が上がるか

    単調増加率:
        隣接スコア間で+10%率が上昇した割合
    """

    exact = analyze_by_exact_score(
        df,
        score_col,
        plan_name,
    )

    if exact.empty:
        return None

    exact = exact.sort_values("スコア")

    scores = exact["スコア"].to_numpy()

    result = {
        "分析種別": "単調性",
        "案": plan_name,
        "スコア": "",
        "n": len(df),
    }

    for target in ["+5%率", "+10%率", "+20%率"]:
        values = exact[target].to_numpy()

        if len(values) >= 2:
            score_rank = pd.Series(scores).rank(method="average")
            value_rank = pd.Series(values).rank(method="average")

            spearman = score_rank.corr(value_rank, method="pearson")

            diffs = np.diff(values)

            increasing_ratio = (
                np.mean(diffs >= 0) * 100
                if len(diffs) > 0
                else np.nan
            )

            strict_ratio = (
                np.mean(diffs > 0) * 100
                if len(diffs) > 0
                else np.nan
            )

            result[f"{target}_Spearman"] = spearman
            result[f"{target}_非減少率"] = increasing_ratio
            result[f"{target}_厳密増加率"] = strict_ratio

    return result


# ============================================================
# 表示
# ============================================================

def print_score_band_table(bands, plan_name):
    print()
    print("=" * 60)
    print(f"=== {plan_name} : スコア帯別実績 ===")
    print("=" * 60)

    if bands.empty:
        print("有効なスコア帯なし")
        return

    print(
        f"{'スコア帯':>10} "
        f"{'n':>6} "
        f"{'+5%率':>9} "
        f"{'+10%率':>10} "
        f"{'+20%率':>10} "
        f"{'平均最大':>11} "
        f"{'10%差':>9} "
        f"{'20%差':>9}"
    )

    print("-" * 85)

    for _, row in bands.iterrows():

        d10 = row["前帯との差(+10%)"]
        d20 = row["前帯との差(+20%)"]

        d10_text = (
            f"{d10:+.1f}pt"
            if pd.notna(d10)
            else "-"
        )

        d20_text = (
            f"{d20:+.1f}pt"
            if pd.notna(d20)
            else "-"
        )

        print(
            f"{str(row['スコア']):>10} "
            f"{int(row['n']):>6} "
            f"{row['+5%率']:>8.1f}% "
            f"{row['+10%率']:>9.1f}% "
            f"{row['+20%率']:>9.1f}% "
            f"{row['平均最大騰落率']:>10.2f}% "
            f"{d10_text:>9} "
            f"{d20_text:>9}"
        )


def print_monotonicity(result):
    print()
    print("------------------------------------------------------------")
    print("=== 単調性評価 ===")
    print("------------------------------------------------------------")

    if result is None:
        print("評価不能")
        return

    print(
        f"{'+5%':<6} "
        f"Spearman={result.get('+5%率_Spearman', np.nan):+.3f} / "
        f"非減少率={result.get('+5%率_非減少率', np.nan):.1f}% / "
        f"厳密増加率={result.get('+5%率_厳密増加率', np.nan):.1f}%"
    )

    print(
        f"{'+10%':<6} "
        f"Spearman={result.get('+10%率_Spearman', np.nan):+.3f} / "
        f"非減少率={result.get('+10%率_非減少率', np.nan):.1f}% / "
        f"厳密増加率={result.get('+10%率_厳密増加率', np.nan):.1f}%"
    )

    print(
        f"{'+20%':<6} "
        f"Spearman={result.get('+20%率_Spearman', np.nan):+.3f} / "
        f"非減少率={result.get('+20%率_非減少率', np.nan):.1f}% / "
        f"厳密増加率={result.get('+20%率_厳密増加率', np.nan):.1f}%"
    )


# ============================================================
# メイン
# ============================================================

def main():

    print("=" * 60)
    print("=== 初動スコア Ver3 スコア帯別・単調性検証 ===")
    print("=" * 60)

    print(f"入力: {INPUT_PATH}")
    print(f"最低サンプル数: {MIN_SAMPLE}")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"入力ファイルがありません: {INPUT_PATH}"
        )

    df = pd.read_csv(INPUT_PATH)

    print()
    print(f"検証記録数 : {len(df):,}")

    df = add_result_columns(df)

    # --------------------------------------------------------
    # 全体基準
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print(f"全体件数       : {len(df):,}")
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

    print()
    print("=" * 60)
    print("=== 条件マスク作成 ===")
    print("=" * 60)

    masks = make_masks(df)

    for name, mask in masks.items():
        print(
            f"{name:<24} n={int(mask.sum()):,}"
        )

    # --------------------------------------------------------
    # 各案
    # --------------------------------------------------------

    all_rows = []
    monotonicity_rows = []

    for plan_name, weights in SCORING_PLANS.items():

        print()
        print("=" * 60)
        print(f"=== {plan_name} ===")
        print("=" * 60)

        basic, penalty, final = calculate_score(
            df,
            masks,
            weights,
        )

        work = df.copy()

        work["_basic_score"] = basic
        work["_rsi_penalty"] = penalty
        work["_final_score"] = final

        print(
            f"基本スコア最大 : "
            f"{int(basic.max())}"
        )

        print(
            f"最終スコア最大 : "
            f"{int(final.max())}"
        )

        print(
            f"RSI減点件数    : "
            f"{int((penalty < 0).sum())}"
        )

        # ----------------------------------------------------
        # スコア帯
        # ----------------------------------------------------

        bands = analyze_score_bands(
            work,
            "_final_score",
            plan_name,
        )

        print_score_band_table(
            bands,
            plan_name,
        )

        # ----------------------------------------------------
        # 単調性
        # ----------------------------------------------------

        mono = calculate_monotonicity(
            work,
            "_final_score",
            plan_name,
        )

        print_monotonicity(mono)

        if mono is not None:
            monotonicity_rows.append(mono)

        # ----------------------------------------------------
        # スコア別詳細
        # ----------------------------------------------------

        exact = analyze_by_exact_score(
            work,
            "_final_score",
            plan_name,
        )

        if not exact.empty:
            exact["基本スコア最大"] = int(basic.max())
            exact["最終スコア最大"] = int(final.max())

            all_rows.extend(
                exact.to_dict("records")
            )

        if not bands.empty:
            all_rows.extend(
                bands.to_dict("records")
            )

    # ========================================================
    # 単調性比較
    # ========================================================

    mono_df = pd.DataFrame(monotonicity_rows)

    print()
    print("=" * 60)
    print("=== 3案 単調性比較 ===")
    print("=" * 60)

    if not mono_df.empty:

        print(
            f"{'案':<20} "
            f"{'+10% Spearman':>15} "
            f"{'+10%非減少率':>15} "
            f"{'+20% Spearman':>15} "
            f"{'+20%非減少率':>15}"
        )

        print("-" * 85)

        for _, row in mono_df.iterrows():

            print(
                f"{row['案']:<20} "
                f"{row.get('+10%率_Spearman', np.nan):>15.3f} "
                f"{row.get('+10%率_非減少率', np.nan):>14.1f}% "
                f"{row.get('+20%率_Spearman', np.nan):>15.3f} "
                f"{row.get('+20%率_非減少率', np.nan):>14.1f}%"
            )

    # ========================================================
    # 保存
    # ========================================================

    output_df = pd.DataFrame(all_rows)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 60)
    print("=== 分析結果保存 ===")
    print("=" * 60)

    print(f"保存先: {OUTPUT_PATH}")

    print()
    print("=" * 60)
    print("=== 初動スコア Ver3 単調性検証完了 ===")
    print("=" * 60)

    print(f"検証記録数 : {len(df):,}")
    print("比較案      : 3")
    print(f"保存先      : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()