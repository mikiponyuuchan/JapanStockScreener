from pathlib import Path
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "high_score_buy_factor_analysis.csv"
)


def print_summary(df, group_column, title):

    print()
    print("=" * 90)
    print(f"=== {title} ===")
    print("=" * 90)

    rows = []

    for group_name, group_df in df.groupby(
        group_column,
        observed=True,
    ):

        values = pd.to_numeric(
            group_df["Max3"],
            errors="coerce",
        ).dropna()

        if values.empty:
            continue

        rows.append({
            "区分": str(group_name),
            "件数": len(values),
            "Max3平均": round(
                values.mean(),
                2,
            ),
            "Max3中央値": round(
                values.median(),
                2,
            ),
            "+5%到達率": round(
                values.ge(5).mean()
                * 100,
                1,
            ),
            "+10%到達率": round(
                values.ge(10).mean()
                * 100,
                1,
            ),
            "+20%到達率": round(
                values.ge(20).mean()
                * 100,
                1,
            ),
        })

    if not rows:
        print("対象なし")
        return

    result = pd.DataFrame(rows)

    print(
        result.to_string(
            index=False
        )
    )


def print_condition(
    df,
    condition,
    name,
):

    work = df[
        condition
    ].copy()

    values = pd.to_numeric(
        work["Max3"],
        errors="coerce",
    ).dropna()

    if values.empty:
        return None

    return {
        "条件": name,
        "件数": len(values),
        "Max3平均": round(
            values.mean(),
            2,
        ),
        "Max3中央値": round(
            values.median(),
            2,
        ),
        "+5%到達率": round(
            values.ge(5).mean()
            * 100,
            1,
        ),
        "+10%到達率": round(
            values.ge(10).mean()
            * 100,
            1,
        ),
        "+20%到達率": round(
            values.ge(20).mean()
            * 100,
            1,
        ),
    }


def main():

    if not INPUT_FILE.exists():

        print(
            "入力ファイルがありません :",
            INPUT_FILE,
        )

        return

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
    )

    numeric_columns = [
        "初動スコア",
        "ChangePercent",
        "VolumeRatio",
        "VolumeRatio20",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "MA25Deviation",
        "終値位置",
        "上ヒゲ率",
        "Max3",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    # --------------------------------------------------------
    # Max3確定銘柄のみ
    # --------------------------------------------------------

    df = df.dropna(
        subset=["Max3"]
    ).copy()

    print()
    print("=" * 90)
    print(
        "初動スコア6・7点 "
        "買い判断条件別検証"
    )
    print("=" * 90)

    print(
        "Max3確定件数 :",
        len(df),
    )

    # ========================================================
    # 1. 当日上昇率
    # ========================================================

    df["当日上昇率区分"] = pd.cut(
        df["ChangePercent"],
        bins=[
            -float("inf"),
            10,
            20,
            float("inf"),
        ],
        labels=[
            "10%未満",
            "10-20%",
            "20%以上",
        ],
        right=False,
    )

    print_summary(
        df,
        "当日上昇率区分",
        "当日上昇率",
    )

    # ========================================================
    # 2. 5日騰落率
    # ========================================================

    df["5日騰落率区分"] = pd.cut(
        df["5日騰落率"],
        bins=[
            -float("inf"),
            10,
            20,
            float("inf"),
        ],
        labels=[
            "10%未満",
            "10-20%",
            "20%以上",
        ],
        right=False,
    )

    print_summary(
        df,
        "5日騰落率区分",
        "5日騰落率",
    )

    # ========================================================
    # 3. MA25乖離
    # ========================================================

    df["MA25乖離区分"] = pd.cut(
        df["MA25Deviation"],
        bins=[
            -float("inf"),
            10,
            20,
            float("inf"),
        ],
        labels=[
            "10%未満",
            "10-20%",
            "20%以上",
        ],
        right=False,
    )

    print_summary(
        df,
        "MA25乖離区分",
        "MA25乖離率",
    )

    # ========================================================
    # 4. RSI
    # ========================================================

    df["RSI区分"] = pd.cut(
        df["RSI"],
        bins=[
            -float("inf"),
            70,
            80,
            float("inf"),
        ],
        labels=[
            "70未満",
            "70-80",
            "80以上",
        ],
        right=False,
    )

    print_summary(
        df,
        "RSI区分",
        "RSI",
    )

    # ========================================================
    # 組み合わせ条件
    # ========================================================

    conditions = []

    conditions.append(
        print_condition(
            df,
            (
                df["MA25Deviation"] < 10
            ),
            "MA25乖離10%未満",
        )
    )

    conditions.append(
        print_condition(
            df,
            (
                df["RSI"] < 80
            ),
            "RSI80未満",
        )
    )

    conditions.append(
        print_condition(
            df,
            (
                df["5日騰落率"] < 10
            ),
            "5日上昇10%未満",
        )
    )

    conditions.append(
        print_condition(
            df,
            (
                (df["MA25Deviation"] < 10)
                &
                (df["RSI"] < 80)
            ),
            "MA25乖離10%未満 × RSI80未満",
        )
    )

    conditions.append(
        print_condition(
            df,
            (
                (df["MA25Deviation"] < 10)
                &
                (df["5日騰落率"] < 10)
            ),
            "MA25乖離10%未満 × 5日上昇10%未満",
        )
    )

    conditions.append(
        print_condition(
            df,
            (
                (df["RSI"] < 80)
                &
                (df["5日騰落率"] < 10)
            ),
            "RSI80未満 × 5日上昇10%未満",
        )
    )

    conditions.append(
        print_condition(
            df,
            (
                (df["MA25Deviation"] < 10)
                &
                (df["RSI"] < 80)
                &
                (df["5日騰落率"] < 10)
            ),
            (
                "MA25乖離10%未満 × "
                "RSI80未満 × "
                "5日上昇10%未満"
            ),
        )
    )

    # --------------------------------------------------------
    # ローソク足も追加
    # --------------------------------------------------------

    conditions.append(
        print_condition(
            df,
            (
                (df["MA25Deviation"] < 10)
                &
                (df["RSI"] < 80)
                &
                (df["終値位置"] >= 0.75)
            ),
            (
                "MA25乖離10%未満 × "
                "RSI80未満 × "
                "終値位置0.75以上"
            ),
        )
    )

    conditions.append(
        print_condition(
            df,
            (
                (df["MA25Deviation"] < 10)
                &
                (df["RSI"] < 80)
                &
                (df["上ヒゲ率"] < 0.20)
            ),
            (
                "MA25乖離10%未満 × "
                "RSI80未満 × "
                "上ヒゲ20%未満"
            ),
        )
    )

    conditions = [
        x
        for x in conditions
        if x is not None
    ]

    print()
    print("=" * 90)
    print(
        "=== 組み合わせ条件 ==="
    )
    print("=" * 90)

    result = pd.DataFrame(
        conditions
    )

    print(
        result.to_string(
            index=False
        )
    )

    # ========================================================
    # Max3上位・下位
    # ========================================================

    display_columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "ChangePercent",
        "5日騰落率",
        "RSI",
        "MA25Deviation",
        "足型",
        "終値位置",
        "上ヒゲ率",
        "Max3",
    ]

    print()
    print("=" * 90)
    print(
        "=== Max3 上位10銘柄 ==="
    )
    print("=" * 90)

    print(
        df
        .sort_values(
            "Max3",
            ascending=False,
        )[
            display_columns
        ]
        .head(10)
        .to_string(
            index=False
        )
    )

    print()
    print("=" * 90)
    print(
        "=== Max3 下位10銘柄 ==="
    )
    print("=" * 90)

    print(
        df
        .sort_values(
            "Max3",
            ascending=True,
        )[
            display_columns
        ]
        .head(10)
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()