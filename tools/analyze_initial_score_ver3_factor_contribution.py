from pathlib import Path
import itertools
import numpy as np
import pandas as pd


# ============================================================
# 設定
# ============================================================

INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path(
    "data/tracking/initial_score_ver3_factor_contribution_analysis.csv"
)

MIN_SAMPLES = 10


# ============================================================
# A_高騰初動特化
#
# ※ ここは Ver3 候補比較で使用している A 案の配点を
#    そのまま合わせること。
#
# 条件名 / 配点 / 説明
# ============================================================

A_PLAN = {
    "ChangePercent_5": {
        "column": "ChangePercent",
        "weight": 5,
        "condition": ">=5%",
        "label": "前日比+5%以上",
    },
    "ChangePercent_3": {
        "column": "ChangePercent",
        "weight": 3,
        "condition": ">=3%",
        "label": "前日比+3%以上",
    },
    "ChangePercent_1": {
        "column": "ChangePercent",
        "weight": 1,
        "condition": ">=1%",
        "label": "前日比+1%以上",
    },
    "VolumeRatio_3": {
        "column": "VolumeRatio",
        "weight": 4,
        "condition": ">=3",
        "label": "出来高3倍以上",
    },
    "VolumeRatio_2": {
        "column": "VolumeRatio",
        "weight": 2,
        "condition": ">=2",
        "label": "出来高2倍以上",
    },
    "VolumeRatio_1.5": {
        "column": "VolumeRatio",
        "weight": 1,
        "condition": ">=1.5",
        "label": "出来高1.5倍以上",
    },
    "VolumeIncreaseDays_3": {
        "column": "VolumeIncreaseDays",
        "weight": 3,
        "condition": ">=3",
        "label": "出来高増加3日",
    },
    "VolumeIncreaseDays_2": {
        "column": "VolumeIncreaseDays",
        "weight": 2,
        "condition": ">=2",
        "label": "出来高増加2日",
    },
    "VolumeIncreaseDays_1": {
        "column": "VolumeIncreaseDays",
        "weight": 1,
        "condition": ">=1",
        "label": "出来高増加1日",
    },
    "BreakoutSignal": {
        "column": "BreakoutSignal",
        "weight": 2,
        "condition": "True",
        "label": "ブレイク",
    },
    "BreakoutFirstDay": {
        "column": "BreakoutFirstDay",
        "weight": 2,
        "condition": "True",
        "label": "ブレイク初日",
    },
    "New30High": {
        "column": "New30High",
        "weight": 2,
        "condition": "True",
        "label": "30日高値更新",
    },
    "AboveMA5": {
        "column": "AboveMA5",
        "weight": 1,
        "condition": "True",
        "label": "MA5上",
    },
    "AboveMA25": {
        "column": "AboveMA25",
        "weight": 1,
        "condition": "True",
        "label": "MA25上",
    },
    "AboveMA75": {
        "column": "AboveMA75",
        "weight": 1,
        "condition": "True",
        "label": "MA75上",
    },
    "MACD_GC": {
        "column": "MACD_GC",
        "weight": 2,
        "condition": "True",
        "label": "MACD GC",
    },
}


# ============================================================
# 共通関数
# ============================================================

def normalize_bool(series):
    """
    CSV内の True / False / 1 / 0 / Yes 等を安全にbool化。
    """

    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    values = series.astype(str).str.strip().str.lower()

    true_values = {
        "true",
        "1",
        "yes",
        "y",
        "t",
        "on",
    }

    return values.isin(true_values)


def make_condition_mask(df, key, spec):
    """
    条件マスクを作成。
    """

    col = spec["column"]

    if col not in df.columns:
        raise KeyError(
            f"必要な列がありません: {col} ({key})"
        )

    series = df[col]

    condition = spec["condition"]

    if condition == ">=5%":
        return pd.to_numeric(series, errors="coerce") >= 5

    if condition == ">=3%":
        return pd.to_numeric(series, errors="coerce") >= 3

    if condition == ">=1%":
        return pd.to_numeric(series, errors="coerce") >= 1

    if condition == ">=3":
        return pd.to_numeric(series, errors="coerce") >= 3

    if condition == ">=2":
        return pd.to_numeric(series, errors="coerce") >= 2

    if condition == ">=1.5":
        return pd.to_numeric(series, errors="coerce") >= 1.5

    if condition == ">=2":
        return pd.to_numeric(series, errors="coerce") >= 2

    if condition == ">=1":
        return pd.to_numeric(series, errors="coerce") >= 1

    if condition == "True":
        return normalize_bool(series)

    raise ValueError(
        f"未対応条件: {condition}"
    )


def safe_rate(mask, target):
    """
    mask該当銘柄のtarget率。
    """

    n = int(mask.sum())

    if n == 0:
        return np.nan

    return float(target[mask].mean() * 100)


def safe_mean(mask, series):
    values = pd.to_numeric(
        series[mask],
        errors="coerce",
    ).dropna()

    if len(values) == 0:
        return np.nan

    return float(values.mean())


def pct(value):
    if pd.isna(value):
        return "-"

    return f"{value:.1f}%"


def pt(value):
    if pd.isna(value):
        return "-"

    sign = "+" if value >= 0 else ""

    return f"{sign}{value:.1f}pt"


def calculate_target_columns(df):
    """
    Hit5 / Hit10 / Hit20 が存在すれば利用。
    なければ最大騰落率から作成。
    """

    work = df.copy()

    if "Hit5" in work.columns:
        work["_hit5"] = (
            pd.to_numeric(
                work["Hit5"],
                errors="coerce",
            )
            .fillna(0)
            .astype(float)
            > 0
        )
    else:
        work["_hit5"] = (
            pd.to_numeric(
                work["5営業日以内最大騰落率"],
                errors="coerce",
            )
            >= 5
        )

    if "Hit10" in work.columns:
        work["_hit10"] = (
            pd.to_numeric(
                work["Hit10"],
                errors="coerce",
            )
            .fillna(0)
            .astype(float)
            > 0
        )
    else:
        work["_hit10"] = (
            pd.to_numeric(
                work["5営業日以内最大騰落率"],
                errors="coerce",
            )
            >= 10
        )

    if "Hit20" in work.columns:
        work["_hit20"] = (
            pd.to_numeric(
                work["Hit20"],
                errors="coerce",
            )
            .fillna(0)
            .astype(float)
            > 0
        )
    else:
        work["_hit20"] = (
            pd.to_numeric(
                work["5営業日以内最大騰落率"],
                errors="coerce",
            )
            >= 20
        )

    work["_max_move"] = pd.to_numeric(
        work["5営業日以内最大騰落率"],
        errors="coerce",
    )

    return work


# ============================================================
# 条件マスク作成
# ============================================================

def build_masks(df):
    masks = {}

    for key, spec in A_PLAN.items():
        masks[key] = make_condition_mask(
            df,
            key,
            spec,
        )

    return masks


# ============================================================
# A案スコア作成
# ============================================================

def calculate_score(df, masks):
    score = pd.Series(
        0,
        index=df.index,
        dtype=float,
    )

    for key, spec in A_PLAN.items():
        score += masks[key].astype(float) * spec["weight"]

    return score


# ============================================================
# RSI減点
# ============================================================

def calculate_rsi_penalty(rsi):
    rsi = pd.to_numeric(
        rsi,
        errors="coerce",
    )

    penalty = pd.Series(
        0,
        index=rsi.index,
        dtype=float,
    )

    penalty[(rsi >= 85) & (rsi < 90)] = -1
    penalty[(rsi >= 90) & (rsi < 95)] = -2
    penalty[rsi >= 95] = -3

    return penalty


# ============================================================
# 条件単独分析
# ============================================================

def analyze_single_conditions(
    df,
    masks,
    overall_10,
    overall_20,
):
    rows = []

    print()
    print("=" * 60)
    print("=== A案 条件別単独貢献度 ===")
    print("=" * 60)

    for key, spec in A_PLAN.items():

        mask = masks[key]

        n = int(mask.sum())

        if n < MIN_SAMPLES:
            continue

        rate5 = safe_rate(
            mask,
            df["_hit5"],
        )

        rate10 = safe_rate(
            mask,
            df["_hit10"],
        )

        rate20 = safe_rate(
            mask,
            df["_hit20"],
        )

        avg_move = safe_mean(
            mask,
            df["_max_move"],
        )

        diff10 = rate10 - overall_10
        diff20 = rate20 - overall_20

        row = {
            "分析": "単独条件",
            "条件": spec["label"],
            "キー": key,
            "配点": spec["weight"],
            "件数": n,
            "+5%率": rate5,
            "+10%率": rate10,
            "+20%率": rate20,
            "平均最大騰落率": avg_move,
            "+10%差": diff10,
            "+20%差": diff20,
        }

        rows.append(row)

        print(
            f"{spec['label']:<25}"
            f" 配点={spec['weight']:>2} "
            f"n={n:>5} "
            f"/ +10%={pct(rate10):>6} "
            f"/ 差={pt(diff10):>7} "
            f"/ +20%={pct(rate20):>6} "
            f"/ 最大={pct(avg_move):>7}"
        )

    return rows


# ============================================================
# 条件成立時の「追加価値」
# ============================================================

def analyze_incremental_value(
    df,
    masks,
    overall_10,
    overall_20,
):
    """
    各条件について、

      条件あり
      条件なし

    を比較する。

    単独条件よりも、
    「その条件があることでどれだけ差が出るか」
    を見るための分析。
    """

    rows = []

    print()
    print("=" * 60)
    print("=== A案 条件あり / なし 比較 ===")
    print("=" * 60)

    for key, spec in A_PLAN.items():

        mask = masks[key]
        inverse = ~mask

        n_yes = int(mask.sum())
        n_no = int(inverse.sum())

        if n_yes < MIN_SAMPLES or n_no < MIN_SAMPLES:
            continue

        yes10 = safe_rate(
            mask,
            df["_hit10"],
        )

        no10 = safe_rate(
            inverse,
            df["_hit10"],
        )

        yes20 = safe_rate(
            mask,
            df["_hit20"],
        )

        no20 = safe_rate(
            inverse,
            df["_hit20"],
        )

        yes_move = safe_mean(
            mask,
            df["_max_move"],
        )

        no_move = safe_mean(
            inverse,
            df["_max_move"],
        )

        diff10 = yes10 - no10
        diff20 = yes20 - no20
        diff_move = yes_move - no_move

        rows.append({
            "分析": "ありなし比較",
            "条件": spec["label"],
            "キー": key,
            "配点": spec["weight"],
            "あり件数": n_yes,
            "なし件数": n_no,
            "あり+10%率": yes10,
            "なし+10%率": no10,
            "+10%差": diff10,
            "あり+20%率": yes20,
            "なし+20%率": no20,
            "+20%差": diff20,
            "あり平均最大": yes_move,
            "なし平均最大": no_move,
            "平均最大差": diff_move,
        })

        print(
            f"{spec['label']:<25}"
            f" 配点={spec['weight']:>2} "
            f"+10%差={pt(diff10):>7} "
            f"+20%差={pt(diff20):>7} "
            f"最大差={pt(diff_move):>7}"
        )

    return rows


# ============================================================
# 高スコア帯の条件構成
# ============================================================

def analyze_high_score_structure(
    df,
    masks,
    score,
):
    rows = []

    print()
    print("=" * 60)
    print("=== 高スコア帯・条件構成分析 ===")
    print("=" * 60)

    bands = [
        ("0-7", score < 8),
        ("8-11", (score >= 8) & (score <= 11)),
        ("12-15", (score >= 12) & (score <= 15)),
        ("16-19", (score >= 16) & (score <= 19)),
        ("20-23", (score >= 20) & (score <= 23)),
        ("24以上", score >= 24),
    ]

    for band_name, band_mask in bands:

        n = int(band_mask.sum())

        if n < MIN_SAMPLES:
            continue

        print()
        print(
            f"--- {band_name} / n={n} ---"
        )

        for key, spec in A_PLAN.items():

            count = int(
                (band_mask & masks[key]).sum()
            )

            rate = count / n * 100

            if count == 0:
                continue

            rows.append({
                "分析": "高スコア帯構成",
                "スコア帯": band_name,
                "条件": spec["label"],
                "キー": key,
                "配点": spec["weight"],
                "帯件数": n,
                "条件成立件数": count,
                "条件成立率": rate,
            })

            print(
                f"{spec['label']:<25}"
                f" {count:>5}件"
                f" ({rate:>5.1f}%)"
            )

    return rows


# ============================================================
# 高スコア帯の実績
# ============================================================

def analyze_score_bands(df, score):
    rows = []

    print()
    print("=" * 60)
    print("=== A案 スコア帯別実績 ===")
    print("=" * 60)

    bands = [
        ("0-7", score < 8),
        ("8-11", (score >= 8) & (score <= 11)),
        ("12-15", (score >= 12) & (score <= 15)),
        ("16-19", (score >= 16) & (score <= 19)),
        ("20-23", (score >= 20) & (score <= 23)),
        ("24以上", score >= 24),
    ]

    for name, mask in bands:

        n = int(mask.sum())

        if n < MIN_SAMPLES:
            continue

        rate5 = safe_rate(
            mask,
            df["_hit5"],
        )

        rate10 = safe_rate(
            mask,
            df["_hit10"],
        )

        rate20 = safe_rate(
            mask,
            df["_hit20"],
        )

        avg_move = safe_mean(
            mask,
            df["_max_move"],
        )

        rows.append({
            "分析": "スコア帯実績",
            "スコア帯": name,
            "件数": n,
            "+5%率": rate5,
            "+10%率": rate10,
            "+20%率": rate20,
            "平均最大騰落率": avg_move,
        })

        print(
            f"{name:>8}"
            f" n={n:>5}"
            f" / +5%={pct(rate5):>6}"
            f" / +10%={pct(rate10):>6}"
            f" / +20%={pct(rate20):>6}"
            f" / 平均最大={pct(avg_move):>7}"
        )

    return rows


# ============================================================
# 条件重複分析
# ============================================================

def analyze_overlap(
    df,
    masks,
):
    rows = []

    print()
    print("=" * 60)
    print("=== 条件重複分析 ===")
    print("=" * 60)

    keys = list(A_PLAN.keys())

    for key1, key2 in itertools.combinations(keys, 2):

        mask = masks[key1] & masks[key2]

        n = int(mask.sum())

        if n < MIN_SAMPLES:
            continue

        rate10 = safe_rate(
            mask,
            df["_hit10"],
        )

        rate20 = safe_rate(
            mask,
            df["_hit20"],
        )

        rows.append({
            "分析": "条件重複",
            "条件1": A_PLAN[key1]["label"],
            "条件2": A_PLAN[key2]["label"],
            "配点1": A_PLAN[key1]["weight"],
            "配点2": A_PLAN[key2]["weight"],
            "件数": n,
            "+10%率": rate10,
            "+20%率": rate20,
        })

    overlap_df = pd.DataFrame(rows)

    if overlap_df.empty:
        return rows

    print()
    print("--- +10%率 上位20組 ---")

    top10 = overlap_df.sort_values(
        "+10%率",
        ascending=False,
    ).head(20)

    for _, row in top10.iterrows():
        print(
            f"{row['条件1']} × {row['条件2']}"
            f" / n={int(row['件数']):>4}"
            f" / +10%={pct(row['+10%率'])}"
            f" / +20%={pct(row['+20%率'])}"
        )

    print()
    print("--- +20%率 上位20組 ---")

    top20 = overlap_df.sort_values(
        "+20%率",
        ascending=False,
    ).head(20)

    for _, row in top20.iterrows():
        print(
            f"{row['条件1']} × {row['条件2']}"
            f" / n={int(row['件数']):>4}"
            f" / +10%={pct(row['+10%率'])}"
            f" / +20%={pct(row['+20%率'])}"
        )

    return rows


# ============================================================
# 1点あたり貢献度
# ============================================================

def analyze_point_efficiency(
    single_rows,
):
    rows = []

    print()
    print("=" * 60)
    print("=== 配点1点あたりの実績 ===")
    print("=" * 60)

    for row in single_rows:

        weight = row["配点"]

        if not weight or weight <= 0:
            continue

        diff10 = row["+10%差"]
        diff20 = row["+20%差"]

        efficiency10 = diff10 / weight
        efficiency20 = diff20 / weight

        new_row = row.copy()

        new_row["+10%差_1点あたり"] = efficiency10
        new_row["+20%差_1点あたり"] = efficiency20
        new_row["分析"] = "1点あたり"

        rows.append(new_row)

    sorted_rows = sorted(
        rows,
        key=lambda x: (
            x["+10%差_1点あたり"]
            if pd.notna(x["+10%差_1点あたり"])
            else -999
        ),
        reverse=True,
    )

    for row in sorted_rows:
        print(
            f"{row['条件']:<25}"
            f" 配点={row['配点']:>2}"
            f" / +10%差/1点={pt(row['+10%差_1点あたり'])}"
            f" / +20%差/1点={pt(row['+20%差_1点あたり'])}"
        )

    return rows


# ============================================================
# RSI減点影響
# ============================================================

def analyze_rsi_impact(
    df,
    base_score,
):
    rows = []

    if "RSI" not in df.columns:
        return rows

    rsi = pd.to_numeric(
        df["RSI"],
        errors="coerce",
    )

    penalty = calculate_rsi_penalty(rsi)

    final_score = base_score + penalty

    df["_rsi_penalty"] = penalty
    df["_final_score"] = final_score

    print()
    print("=" * 60)
    print("=== RSI減点影響 ===")
    print("=" * 60)

    for value, label in [
        (-3, "RSI95以上"),
        (-2, "RSI90-94.99"),
        (-1, "RSI85-89.99"),
        (0, "RSI85未満"),
    ]:

        mask = penalty == value

        n = int(mask.sum())

        if n == 0:
            continue

        print(
            f"{label:<18}"
            f" n={n:>5}"
            f" / 減点={value:>2}"
        )

        rows.append({
            "分析": "RSI減点",
            "区分": label,
            "件数": n,
            "減点": value,
        })

    changed = penalty != 0

    print(
        f"RSI減点発生件数 : {int(changed.sum())}"
    )

    return rows


# ============================================================
# メイン
# ============================================================

def main():

    print("=" * 60)
    print("=== 初動スコア Ver3 条件別配点・貢献度分析 ===")
    print("=" * 60)

    print(f"入力: {INPUT_FILE}")
    print(f"最低サンプル数: {MIN_SAMPLES}")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"入力ファイルがありません: {INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"検証記録数 : {len(df):,}"
    )

    # --------------------------------------------------------
    # 実績列
    # --------------------------------------------------------

    df = calculate_target_columns(df)

    overall_5 = float(
        df["_hit5"].mean() * 100
    )

    overall_10 = float(
        df["_hit10"].mean() * 100
    )

    overall_20 = float(
        df["_hit20"].mean() * 100
    )

    overall_move = float(
        df["_max_move"].mean()
    )

    print()
    print("=" * 60)
    print("=== 全体基準 ===")
    print("=" * 60)

    print(
        f"全体件数       : {len(df):,}"
    )
    print(
        f"+5%率          : {overall_5:.1f}%"
    )
    print(
        f"+10%率         : {overall_10:.1f}%"
    )
    print(
        f"+20%率         : {overall_20:.1f}%"
    )
    print(
        f"平均最大騰落率 : {overall_move:+.2f}%"
    )

    # --------------------------------------------------------
    # 条件マスク
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== A案 条件マスク作成 ===")
    print("=" * 60)

    masks = build_masks(df)

    for key, spec in A_PLAN.items():
        print(
            f"{spec['label']:<25}"
            f" n={int(masks[key].sum()):,}"
        )

    # --------------------------------------------------------
    # スコア
    # --------------------------------------------------------

    base_score = calculate_score(
        df,
        masks,
    )

    df["_base_score"] = base_score

    print()
    print("=" * 60)
    print("=== A案 スコア ===")
    print("=" * 60)

    print(
        f"基本スコア最大 : {int(base_score.max())}"
    )

    # --------------------------------------------------------
    # 各分析
    # --------------------------------------------------------

    all_rows = []

    single_rows = analyze_single_conditions(
        df,
        masks,
        overall_10,
        overall_20,
    )

    all_rows.extend(single_rows)

    incremental_rows = analyze_incremental_value(
        df,
        masks,
        overall_10,
        overall_20,
    )

    all_rows.extend(incremental_rows)

    band_rows = analyze_score_bands(
        df,
        base_score,
    )

    all_rows.extend(band_rows)

    structure_rows = analyze_high_score_structure(
        df,
        masks,
        base_score,
    )

    all_rows.extend(structure_rows)

    overlap_rows = analyze_overlap(
        df,
        masks,
    )

    all_rows.extend(overlap_rows)

    efficiency_rows = analyze_point_efficiency(
        single_rows,
    )

    all_rows.extend(efficiency_rows)

    rsi_rows = analyze_rsi_impact(
        df,
        base_score,
    )

    all_rows.extend(rsi_rows)

    # --------------------------------------------------------
    # 高スコア帯の実績を最後に再表示
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 重要スコア帯比較 ===")
    print("=" * 60)

    for low, high in [
        (12, 15),
        (16, 19),
        (20, 23),
        (24, 999),
    ]:

        mask = (
            (base_score >= low)
            & (base_score <= high)
        )

        n = int(mask.sum())

        if n < MIN_SAMPLES:
            continue

        rate10 = safe_rate(
            mask,
            df["_hit10"],
        )

        rate20 = safe_rate(
            mask,
            df["_hit20"],
        )

        avg_move = safe_mean(
            mask,
            df["_max_move"],
        )

        print(
            f"{low:>2}-{high if high < 999 else '以上':<2}"
            f" n={n:>5}"
            f" / +10%={pct(rate10):>6}"
            f" / +20%={pct(rate20):>6}"
            f" / 平均最大={pct(avg_move):>7}"
        )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("=== 分析結果保存 ===")
    print("=" * 60)

    output_df = pd.DataFrame(all_rows)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"保存先: {OUTPUT_FILE}"
    )

    print()
    print("=" * 60)
    print("=== 初動スコア Ver3 条件別配点・貢献度分析完了 ===")
    print("=" * 60)

    print(
        f"検証記録数 : {len(df):,}"
    )
    print(
        f"A案基本スコア最大 : {int(base_score.max())}"
    )
    print(
        f"分析結果行数 : {len(output_df):,}"
    )
    print(
        f"保存先 : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()