import pandas as pd
from pathlib import Path

RESULT_FILE = Path("results/2026-08-15_stock_result.csv")
CREDIT_DIR = Path("data/yahoo_credit")


# ============================================================
# 1. 買い候補を読み込み
# ============================================================

df = pd.read_csv(RESULT_FILE)

buy = df[df["総合判定"] == "買い候補"].copy()

print("=" * 70)
print("信用条件追加テスト")
print("=" * 70)
print()
print(f"買い候補銘柄数 : {len(buy)}")


# ============================================================
# 2. 信用データを読み込み
#    各銘柄の最新データを取得
# ============================================================

credit_list = []

for file in CREDIT_DIR.glob("*.csv"):
    try:
        c = pd.read_csv(file)

        if c.empty:
            continue

        c["日付"] = pd.to_datetime(c["日付"], errors="coerce")

        c = c.dropna(subset=["日付"])

        if c.empty:
            continue

        latest = c.sort_values("日付").iloc[-1].copy()

        credit_list.append({
            "コード": str(latest["コード"]).split(".")[0],
            "信用日付": latest["日付"].strftime("%Y-%m-%d"),
            "売残": latest["売残"],
            "買残": latest["買残"],
            "売残増減": latest["売残増減"],
            "買残増減": latest["買残増減"],
            "信用倍率": latest["信用倍率"],
        })

    except Exception:
        continue


credit = pd.DataFrame(credit_list)

if credit.empty:
    print("信用データがありません。")
    raise SystemExit


credit["コード"] = (
    credit["コード"]
    .astype(str)
    .str.replace(".0", "", regex=False)
    .str.zfill(4)
)

buy["コード"] = (
    buy["コード"]
    .astype(str)
    .str.replace(".0", "", regex=False)
    .str.zfill(4)
)


# ============================================================
# 3. 買い候補と信用データを結合
# ============================================================

merged = buy.merge(
    credit,
    on="コード",
    how="left",
    suffixes=("", "_credit")
)

print(f"信用データあり : {merged['信用倍率'].notna().sum()}")
print(f"信用データなし : {merged['信用倍率'].isna().sum()}")
print()


# ============================================================
# 4. 信用3条件
# ============================================================

cond_ratio = merged["信用倍率"] < 1
cond_sell = merged["売残増減"] > 0
cond_buy = merged["買残増減"] < 0


merged["信用倍率条件"] = cond_ratio
merged["売残増加条件"] = cond_sell
merged["買残減少条件"] = cond_buy

merged["信用条件数"] = (
    cond_ratio.astype(int)
    + cond_sell.astype(int)
    + cond_buy.astype(int)
)


# ============================================================
# 5. 各条件を順番に追加
# ============================================================

print("=" * 70)
print("条件を順番に追加")
print("=" * 70)

step1 = merged[cond_ratio]
step2 = step1[step1["売残増加条件"]]
step3 = step2[step2["買残減少条件"]]

print()
print(f"スタート             : {len(merged)} 銘柄")
print(f"① 信用倍率 < 1       : {len(step1)} 銘柄")
print(f"② ＋ 売残増加        : {len(step2)} 銘柄")
print(f"③ ＋ 買残減少        : {len(step3)} 銘柄")


# ============================================================
# 6. 3条件のうち何個満たすか
# ============================================================

print()
print("=" * 70)
print("信用3条件の充足数")
print("=" * 70)

for n in [3, 2, 1, 0]:
    count = (merged["信用条件数"] == n).sum()
    print(f"{n}条件達成 : {count:3d} 銘柄")


# ============================================================
# 7. 3条件すべて達成した銘柄
# ============================================================

all_three = merged[merged["信用条件数"] == 3].copy()

print()
print("=" * 70)
print("信用3条件すべて達成")
print("=" * 70)

if all_three.empty:
    print("該当銘柄なし")
else:
    cols = [
        "コード",
        "銘柄名",
        "終値",
        "強気度",
        "信用日付",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    print(
        all_three[cols]
        .sort_values("強気度", ascending=False)
        .to_string(index=False)
    )


# ============================================================
# 8. 2条件達成銘柄
# ============================================================

two = merged[merged["信用条件数"] == 2].copy()

print()
print("=" * 70)
print("信用3条件のうち2条件達成")
print("=" * 70)

if two.empty:
    print("該当銘柄なし")
else:
    cols = [
        "コード",
        "銘柄名",
        "終値",
        "強気度",
        "売残増減",
        "買残増減",
        "信用倍率",
        "信用倍率条件",
        "売残増加条件",
        "買残減少条件",
    ]

    print(
        two[cols]
        .sort_values("強気度", ascending=False)
        .to_string(index=False)
    )


# ============================================================
# 9. 結果保存
# ============================================================

output = Path("results/2026-08-15_credit_candidate_test.csv")

merged.to_csv(
    output,
    index=False,
    encoding="utf-8-sig"
)

print()
print("=" * 70)
print(f"詳細結果保存 : {output}")
print("=" * 70)
