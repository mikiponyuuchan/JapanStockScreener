from pathlib import Path
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "high_score_buy_factor_analysis.csv"
)


def summarize(name, df):

    values = pd.to_numeric(
        df["Max3"],
        errors="coerce",
    ).dropna()

    if values.empty:
        return None

    return {
        "条件": name,
        "件数": len(values),
        "平均": round(values.mean(), 2),
        "中央値": round(values.median(), 2),
        "+5%": round(values.ge(5).mean() * 100, 1),
        "+10%": round(values.ge(10).mean() * 100, 1),
        "最小": round(values.min(), 2),
        "最大": round(values.max(), 2),
    }


def main():

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        dtype={"コード": str},
    )

    numeric_cols = [
        "初動スコア",
        "5日騰落率",
        "RSI",
        "MA25Deviation",
        "終値位置",
        "Max3",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=["Max3"]
    ).copy()

    core = (
        (df["MA25Deviation"] < 10)
        &
        (df["RSI"] < 80)
        &
        (df["5日騰落率"] < 10)
    )

    rows = []

    rows.append(
        summarize(
            "3条件",
            df[core],
        )
    )

    rows.append(
        summarize(
            "3条件 ANAP除外",
            df[
                core
                &
                (df["コード"] != "3189")
            ],
        )
    )

    rows.append(
        summarize(
            "RSI80未満",
            df[df["RSI"] < 80],
        )
    )

    rows.append(
        summarize(
            "RSI80以上",
            df[df["RSI"] >= 80],
        )
    )

    rows.append(
        summarize(
            "5日10%未満",
            df[df["5日騰落率"] < 10],
        )
    )

    rows.append(
        summarize(
            "5日10%以上",
            df[df["5日騰落率"] >= 10],
        )
    )

    rows.append(
        summarize(
            "MA25乖離10%未満",
            df[df["MA25Deviation"] < 10],
        )
    )

    rows.append(
        summarize(
            "MA25乖離10%以上",
            df[df["MA25Deviation"] >= 10],
        )
    )

    result = pd.DataFrame(
        [r for r in rows if r is not None]
    )

    print()
    print("=" * 90)
    print("買い判断条件 ロバスト性確認")
    print("=" * 90)
    print()

    print(
        result.to_string(
            index=False
        )
    )

    print()
    print("=== 3条件該当銘柄 ===")
    print()

    cols = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "5日騰落率",
        "RSI",
        "MA25Deviation",
        "足型",
        "終値位置",
        "Max3",
    ]

    print(
        df[core][cols]
        .sort_values(
            "Max3",
            ascending=False,
        )
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()