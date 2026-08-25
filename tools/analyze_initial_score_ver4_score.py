from pathlib import Path
import pandas as pd


# ============================================================
# 初動スコア Ver4 実データ検証
# ============================================================

INPUT_FILE = Path("data/tracking/initial_score_factor_raw.csv")
OUTPUT_FILE = Path("data/tracking/initial_score_ver4_score_analysis.csv")

MIN_SAMPLE = 5


# ============================================================
# 表示
# ============================================================

def print_header(title: str):
    print()
    print("=" * 60)
    print(f"=== {title} ===")
    print("=" * 60)


def pct(series):
    if len(series) == 0:
        return 0.0
    return series.mean() * 100


# ============================================================
# データ読み込み
# ============================================================

print_header("初動スコア Ver4 実データ検証")

print(f"入力: {INPUT_FILE}")
print(f"最低サンプル数: {MIN_SAMPLE}")

if not INPUT_FILE.exists():
    print(f"\nERROR: 入力ファイルがありません: {INPUT_FILE}")
    raise SystemExit(1)

df = pd.read_csv(INPUT_FILE)

print(f"検証記録数 : {len(df):,}")


# ============================================================
# 必須列確認
# ============================================================

required_columns = [
    "VolumeRatio",
    "ChangePercent",
    "RSI",
    "BreakoutSignal",
    "New30High",
    "Hit5",
    "Hit10",
    "Hit20",
    "5営業日以内最大騰落率",
]

missing = [col for col in required_columns if col not in df.columns]

if missing:
    print("\nERROR: 必須列がありません")
    for col in missing:
        print(f"  {col}")

    raise SystemExit(1)


# ============================================================
# 数値変換
# ============================================================

numeric_columns = [
    "VolumeRatio",
    "ChangePercent",
    "RSI",
    "Hit5",
    "Hit10",
    "Hit20",
    "5営業日以内最大騰落率",
]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# ============================================================
# 条件マスク
# ============================================================

print_header("Ver4 コア4条件")

df["cond_change5"] = df["ChangePercent"] >= 5
df["cond_volume3"] = df["VolumeRatio"] >= 3
df["cond_breakout"] = df["BreakoutSignal"].astype(str).str.upper().isin(
    ["TRUE", "1", "YES", "Y", "○", "あり"]
)

# BreakoutSignal が数値型/booleanの場合にも対応
if pd.api.types.is_numeric_dtype(df["BreakoutSignal"]):
    df["cond_breakout"] = df["BreakoutSignal"] == 1

df["cond_new30"] = df["New30High"].astype(str).str.upper().isin(
    ["TRUE", "1", "YES", "Y", "○", "あり"]
)

if pd.api.types.is_numeric_dtype(df["New30High"]):
    df["cond_new30"] = df["New30High"] == 1


print(
    f"前日比+5%以上             n={df['cond_change5'].sum():5d}"
)
print(
    f"出来高3倍以上              n={df['cond_volume3'].sum():5d}"
)
print(
    f"ブレイク                  n={df['cond_breakout'].sum():5d}"
)
print(
    f"30日高値更新               n={df['cond_new30'].sum():5d}"
)


# ============================================================
# コアスコア
# ============================================================

df["core_score"] = (
    df["cond_change5"].astype(int) * 3
    + df["cond_volume3"].astype(int) * 2
    + df["cond_breakout"].astype(int) * 1
    + df["cond_new30"].astype(int) * 1
)


# ============================================================
# RSI減点
# ============================================================

def rsi_penalty(rsi):
    if pd.isna(rsi):
        return 0

    if rsi >= 95:
        return -3

    if rsi >= 90:
        return -2

    if rsi >= 85:
        return -1

    return 0


df["rsi_penalty"] = df["RSI"].apply(rsi_penalty)

df["initial_score_ver4"] = (
    df["core_score"] + df["rsi_penalty"]
)


# ============================================================
# RSI確認
# ============================================================

print_header("RSI減点確認")

print(
    f"RSI 85～89.99             n="
    f"{((df['RSI'] >= 85) & (df['RSI'] < 90)).sum():5d}"
)

print(
    f"RSI 90～94.99             n="
    f"{((df['RSI'] >= 90) & (df['RSI'] < 95)).sum():5d}"
)

print(
    f"RSI 95以上                n="
    f"{(df['RSI'] >= 95).sum():5d}"
)


# ============================================================
# 全体基準
# ============================================================

print_header("全体基準")

print(f"全体件数       : {len(df):,}")
print(f"+5%率          : {pct(df['Hit5']):5.1f}%")
print(f"+10%率         : {pct(df['Hit10']):5.1f}%")
print(f"+20%率         : {pct(df['Hit20']):5.1f}%")
print(
    f"平均最大騰落率 : "
    f"{df['5営業日以内最大騰落率'].mean():+.2f}%"
)


# ============================================================
# スコア別分析
# ============================================================

print_header("Ver4 最終スコア別分析")

score_results = []

for score in sorted(df["initial_score_ver4"].dropna().unique()):
    subset = df[df["initial_score_ver4"] == score]

    if len(subset) < MIN_SAMPLE:
        print(
            f"{score:2.0f}点 / n={len(subset):4d}"
            f" / サンプル不足"
        )
        continue

    hit5_rate = pct(subset["Hit5"])
    hit10_rate = pct(subset["Hit10"])
    hit20_rate = pct(subset["Hit20"])
    avg_max = subset["5営業日以内最大騰落率"].mean()

    score_results.append({
        "スコア": score,
        "件数": len(subset),
        "構成比": len(subset) / len(df) * 100,
        "+5%率": hit5_rate,
        "+10%率": hit10_rate,
        "+20%率": hit20_rate,
        "平均最大騰落率": avg_max,
    })

    print(
        f"{score:2.0f}点 / "
        f"n={len(subset):4d} / "
        f"構成比={len(subset)/len(df)*100:5.2f}% / "
        f"+5%={hit5_rate:5.1f}% / "
        f"+10%={hit10_rate:5.1f}% / "
        f"+20%={hit20_rate:5.1f}% / "
        f"平均最大={avg_max:+.2f}%"
    )


# ============================================================
# 閾値別分析
# ============================================================

print_header("Ver4 スコア閾値別分析")

threshold_results = []

for threshold in [7, 6, 5, 4, 3, 2, 1]:

    subset = df[df["initial_score_ver4"] >= threshold]

    if len(subset) < MIN_SAMPLE:
        print(
            f"{threshold}点以上 / n={len(subset):4d}"
            f" / サンプル不足"
        )
        continue

    hit5_rate = pct(subset["Hit5"])
    hit10_rate = pct(subset["Hit10"])
    hit20_rate = pct(subset["Hit20"])
    avg_max = subset["5営業日以内最大騰落率"].mean()

    threshold_results.append({
        "閾値": threshold,
        "件数": len(subset),
        "構成比": len(subset) / len(df) * 100,
        "+5%率": hit5_rate,
        "+10%率": hit10_rate,
        "+20%率": hit20_rate,
        "平均最大騰落率": avg_max,
    })

    print(
        f"{threshold}点以上 / "
        f"n={len(subset):4d} / "
        f"構成比={len(subset)/len(df)*100:5.2f}% / "
        f"+5%={hit5_rate:5.1f}% / "
        f"+10%={hit10_rate:5.1f}% / "
        f"+20%={hit20_rate:5.1f}% / "
        f"平均最大={avg_max:+.2f}%"
    )


# ============================================================
# コアスコア別分析
# ============================================================

print_header("コアスコア別分析（RSI減点前）")

core_results = []

for score in sorted(df["core_score"].dropna().unique()):

    subset = df[df["core_score"] == score]

    if len(subset) < MIN_SAMPLE:
        print(
            f"{score:2.0f}点 / n={len(subset):4d}"
            f" / サンプル不足"
        )
        continue

    hit5_rate = pct(subset["Hit5"])
    hit10_rate = pct(subset["Hit10"])
    hit20_rate = pct(subset["Hit20"])
    avg_max = subset["5営業日以内最大騰落率"].mean()

    core_results.append({
        "コアスコア": score,
        "件数": len(subset),
        "構成比": len(subset) / len(df) * 100,
        "+5%率": hit5_rate,
        "+10%率": hit10_rate,
        "+20%率": hit20_rate,
        "平均最大騰落率": avg_max,
    })

    print(
        f"{score:2.0f}点 / "
        f"n={len(subset):4d} / "
        f"+5%={hit5_rate:5.1f}% / "
        f"+10%={hit10_rate:5.1f}% / "
        f"+20%={hit20_rate:5.1f}% / "
        f"平均最大={avg_max:+.2f}%"
    )


# ============================================================
# 結果保存
# ============================================================

print_header("分析結果保存")

score_df = pd.DataFrame(score_results)
threshold_df = pd.DataFrame(threshold_results)
core_df = pd.DataFrame(core_results)

# 1つのCSVにまとめる
rows = []

for _, row in score_df.iterrows():
    rows.append({
        "分析区分": "最終スコア",
        "値": row["スコア"],
        "件数": row["件数"],
        "構成比": row["構成比"],
        "+5%率": row["+5%率"],
        "+10%率": row["+10%率"],
        "+20%率": row["+20%率"],
        "平均最大騰落率": row["平均最大騰落率"],
    })

for _, row in threshold_df.iterrows():
    rows.append({
        "分析区分": "閾値以上",
        "値": row["閾値"],
        "件数": row["件数"],
        "構成比": row["構成比"],
        "+5%率": row["+5%率"],
        "+10%率": row["+10%率"],
        "+20%率": row["+20%率"],
        "平均最大騰落率": row["平均最大騰落率"],
    })

for _, row in core_df.iterrows():
    rows.append({
        "分析区分": "コアスコア",
        "値": row["コアスコア"],
        "件数": row["件数"],
        "構成比": row["構成比"],
        "+5%率": row["+5%率"],
        "+10%率": row["+10%率"],
        "+20%率": row["+20%率"],
        "平均最大騰落率": row["平均最大騰落率"],
    })

result_df = pd.DataFrame(rows)

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
result_df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)

print(f"保存先: {OUTPUT_FILE}")


# ============================================================
# 完了
# ============================================================

print_header("初動スコア Ver4 実データ検証完了")

print(f"検証記録数 : {len(df):,}")
print(f"保存先     : {OUTPUT_FILE}")