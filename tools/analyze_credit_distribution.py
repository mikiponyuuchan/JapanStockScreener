from pathlib import Path

import pandas as pd


CREDIT_DIR = Path("data/yahoo_credit")


def calc_change_rate(current, previous):
    """前週比(%)を計算"""
    if previous == 0 or pd.isna(previous):
        return None

    return (current - previous) / previous * 100


def main():
    rows = []

    files = sorted(CREDIT_DIR.glob("*.csv"))

    print(f"信用CSV数 : {len(files)}")

    for file in files:
        try:
            df = pd.read_csv(file)

            if len(df) < 2:
                continue

            # 日付の新しい順になっている前提
            latest = df.iloc[0]
            previous = df.iloc[1]

            code = str(latest["コード"])

            credit_ratio = pd.to_numeric(
                latest["信用倍率"], errors="coerce"
            )

            sell_change_rate = calc_change_rate(
                pd.to_numeric(latest["売残"], errors="coerce"),
                pd.to_numeric(previous["売残"], errors="coerce"),
            )

            buy_change_rate = calc_change_rate(
                pd.to_numeric(latest["買残"], errors="coerce"),
                pd.to_numeric(previous["買残"], errors="coerce"),
            )

            rows.append(
                {
                    "コード": code,
                    "日付": latest["日付"],
                    "信用倍率": credit_ratio,
                    "売残前週比": sell_change_rate,
                    "買残前週比": buy_change_rate,
                }
            )

        except Exception as e:
            print(f"読み込みエラー : {file.name} / {e}")

    result = pd.DataFrame(rows)

    print()
    print("=" * 60)
    print("信用データ分布")
    print("=" * 60)

    print(f"分析銘柄数 : {len(result)}")

    for column in ["信用倍率", "売残前週比", "買残前週比"]:
        s = pd.to_numeric(result[column], errors="coerce").dropna()

        print()
        print("-" * 60)
        print(column)
        print("-" * 60)

        print(f"有効件数 : {len(s)}")
        print(f"平均     : {s.mean():.2f}")
        print(f"中央値   : {s.median():.2f}")
        print(f"25%      : {s.quantile(0.25):.2f}")
        print(f"75%      : {s.quantile(0.75):.2f}")
        print(f"最小     : {s.min():.2f}")
        print(f"最大     : {s.max():.2f}")

    # 信用倍率の分布
    print()
    print("=" * 60)
    print("信用倍率 分布")
    print("=" * 60)

    bins = [0, 1, 2, 3, 5, 10, float("inf")]
    labels = [
        "1倍未満",
        "1～2倍",
        "2～3倍",
        "3～5倍",
        "5～10倍",
        "10倍超",
    ]

    credit = pd.to_numeric(result["信用倍率"], errors="coerce")

    categories = pd.cut(
        credit,
        bins=bins,
        labels=labels,
        right=False,
    )

    counts = categories.value_counts().reindex(labels, fill_value=0)

    for label, count in counts.items():
        print(f"{label:10s} : {count:4d} ({count / len(result) * 100:5.1f}%)")

    # 売残前週比
    print()
    print("=" * 60)
    print("売残前週比 分布")
    print("=" * 60)

    sell = pd.to_numeric(result["売残前週比"], errors="coerce")

    sell_bins = [
        -float("inf"),
        -20,
        -10,
        -5,
        0,
        5,
        10,
        20,
        float("inf"),
    ]

    sell_labels = [
        "-20%未満",
        "-20～-10%",
        "-10～-5%",
        "-5～0%",
        "0～5%",
        "5～10%",
        "10～20%",
        "20%以上",
    ]

    sell_categories = pd.cut(
        sell,
        bins=sell_bins,
        labels=sell_labels,
        right=False,
    )

    sell_counts = (
        sell_categories.value_counts()
        .reindex(sell_labels, fill_value=0)
    )

    for label, count in sell_counts.items():
        print(f"{label:12s} : {count:4d} ({count / len(result) * 100:5.1f}%)")

    # 買残前週比
    print()
    print("=" * 60)
    print("買残前週比 分布")
    print("=" * 60)

    buy = pd.to_numeric(result["買残前週比"], errors="coerce")

    buy_categories = pd.cut(
        buy,
        bins=sell_bins,
        labels=sell_labels,
        right=False,
    )

    buy_counts = (
        buy_categories.value_counts()
        .reindex(sell_labels, fill_value=0)
    )

    for label, count in buy_counts.items():
        print(f"{label:12s} : {count:4d} ({count / len(result) * 100:5.1f}%)")


if __name__ == "__main__":
    main()