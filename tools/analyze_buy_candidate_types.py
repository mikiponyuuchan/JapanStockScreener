from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "buy_candidate_analysis.csv"
)

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "buy_candidate_type_analysis.csv"
)


# ============================================================
# 数値変換
# ============================================================

def to_numeric(df, columns):

    for column in columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df


# ============================================================
# タイプ仮分類
#
# 注意
# ------------------------------------------------------------
# これは買いルールではない。
#
# Max3という「その後の結果」を使って、
# 過去銘柄を研究しやすくするための分類。
#
# 実運用の買い判定にはそのまま使用しない。
# ============================================================

def classify_type(row):

    max3 = row["Max3"]

    if pd.isna(max3):

        return "未確定"

    change1 = row["ChangePercent"]
    change5 = row["5日騰落率"]

    candle = str(
        row.get(
            "足型",
            "",
        )
    )

    close_position = row.get(
        "終値位置",
        pd.NA,
    )

    upper_wick = row.get(
        "上ヒゲ率",
        pd.NA,
    )

    # --------------------------------------------------------
    # 押し・振り落とし型
    #
    # 当日の足は弱く見えるが、
    # その後 +5%以上まで上昇
    #
    # ANAP型をここで拾う
    # --------------------------------------------------------

    weak_candle = False

    if candle == "陰線":

        weak_candle = True

    if (
        pd.notna(close_position)
        and close_position < 0.40
    ):

        weak_candle = True

    if (
        pd.notna(upper_wick)
        and upper_wick >= 0.50
    ):

        weak_candle = True

    if (
        max3 >= 5
        and weak_candle
    ):

        return "押し・振り落とし型"

    # --------------------------------------------------------
    # 急騰継続型
    #
    # 検出時点ですでにかなり上昇しているが、
    # さらに +5%以上伸びたタイプ
    #
    # ハイパー型
    # --------------------------------------------------------

    already_extended = False

    if (
        pd.notna(change1)
        and change1 >= 20
    ):

        already_extended = True

    if (
        pd.notna(change5)
        and change5 >= 20
    ):

        already_extended = True

    if (
        max3 >= 5
        and already_extended
    ):

        return "急騰継続型"

    # --------------------------------------------------------
    # 初動継続型
    #
    # 過熱しすぎていない状態から
    # その後 +5%以上上昇
    #
    # 東京衡機型
    # --------------------------------------------------------

    if max3 >= 5:

        return "初動継続型"

    # --------------------------------------------------------
    # 中間型
    #
    # 0%以上 +5%未満
    # --------------------------------------------------------

    if max3 >= 0:

        return "中間型"

    # --------------------------------------------------------
    # 失速型
    #
    # 3日以内の最大騰落率でも0%未満
    # --------------------------------------------------------

    return "失速型"


# ============================================================
# 集計
# ============================================================

def summarize_group(df):

    if df.empty:

        return {
            "件数": 0,
            "Max3平均": pd.NA,
            "Max3中央値": pd.NA,
            "+5%到達率": pd.NA,
            "+10%到達率": pd.NA,
            "+20%到達率": pd.NA,
        }

    max3 = df["Max3"].dropna()

    if max3.empty:

        return {
            "件数": len(df),
            "Max3平均": pd.NA,
            "Max3中央値": pd.NA,
            "+5%到達率": pd.NA,
            "+10%到達率": pd.NA,
            "+20%到達率": pd.NA,
        }

    return {
        "件数":
            len(max3),

        "Max3平均":
            round(
                max3.mean(),
                2,
            ),

        "Max3中央値":
            round(
                max3.median(),
                2,
            ),

        "+5%到達率":
            round(
                (max3 >= 5).mean()
                * 100,
                1,
            ),

        "+10%到達率":
            round(
                (max3 >= 10).mean()
                * 100,
                1,
            ),

        "+20%到達率":
            round(
                (max3 >= 20).mean()
                * 100,
                1,
            ),
    }


# ============================================================
# 平均特徴量
# ============================================================

def make_feature_summary(df):

    feature_columns = [
        "ChangePercent",
        "VolumeRatio",
        "VolumeRatio20",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "MA25Deviation",
        "終値位置",
        "実体率",
        "上ヒゲ率",
    ]

    rows = []

    confirmed = df[
        df["タイプ"] != "未確定"
    ].copy()

    for type_name, group in confirmed.groupby(
        "タイプ"
    ):

        row = {
            "タイプ": type_name,
            "件数": len(group),
        }

        for column in feature_columns:

            if column not in group.columns:
                continue

            values = pd.to_numeric(
                group[column],
                errors="coerce",
            )

            row[
                f"{column}平均"
            ] = round(
                values.mean(),
                2,
            )

            row[
                f"{column}中央値"
            ] = round(
                values.median(),
                2,
            )

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# メイン
# ============================================================

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
        "実体率",
        "上ヒゲ率",
        "Max3",
    ]

    df = to_numeric(
        df,
        numeric_columns,
    )

    # ========================================================
    # 6点・7点だけ
    # ========================================================

    df = df[
        df["初動スコア"] >= 6
    ].copy()

    # ========================================================
    # タイプ分類
    # ========================================================

    df["タイプ"] = df.apply(
        classify_type,
        axis=1,
    )

    # ========================================================
    # CSV保存
    # ========================================================

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "=" * 100
    )

    print(
        "初動スコア6・7点 "
        "買い候補タイプ分析"
    )

    print(
        "=" * 100
    )

    print()

    print(
        "対象件数 :",
        len(df)
    )

    print(
        "Max3確定 :",
        df["Max3"].notna().sum()
    )

    print()

    # ========================================================
    # タイプ別件数
    # ========================================================

    print(
        "=" * 100
    )

    print(
        "=== タイプ別件数 ==="
    )

    print(
        "=" * 100
    )

    print()

    counts = (
        df["タイプ"]
        .value_counts()
        .rename_axis("タイプ")
        .reset_index(name="件数")
    )

    print(
        counts.to_string(
            index=False
        )
    )

    # ========================================================
    # タイプ別成績
    # ========================================================

    print()
    print(
        "=" * 100
    )

    print(
        "=== タイプ別成績 ==="
    )

    print(
        "=" * 100
    )

    print()

    summary_rows = []

    for type_name, group in df.groupby(
        "タイプ"
    ):

        if type_name == "未確定":
            continue

        summary = summarize_group(
            group
        )

        summary_rows.append({
            "タイプ":
                type_name,
            **summary,
        })

    summary_df = pd.DataFrame(
        summary_rows
    )

    print(
        summary_df.to_string(
            index=False
        )
    )

    # ========================================================
    # タイプ別特徴
    # ========================================================

    print()
    print(
        "=" * 100
    )

    print(
        "=== タイプ別特徴量 ==="
    )

    print(
        "=" * 100
    )

    print()

    feature_summary = (
        make_feature_summary(
            df
        )
    )

    print(
        feature_summary.to_string(
            index=False
        )
    )

    # ========================================================
    # 確定銘柄一覧
    # ========================================================

    print()
    print(
        "=" * 100
    )

    print(
        "=== Max3確定銘柄 ==="
    )

    print(
        "=" * 100
    )

    print()

    display_columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "タイプ",
        "ChangePercent",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "MA25Deviation",
        "VolumeRatio",
        "VolumeRatio20",
        "足型",
        "終値位置",
        "実体率",
        "上ヒゲ率",
        "BreakoutSignal",
        "New30High",
        "Max3",
    ]

    display_columns = [
        column
        for column
        in display_columns
        if column in df.columns
    ]

    confirmed = df[
        df["Max3"].notna()
    ].copy()

    confirmed = confirmed.sort_values(
        [
            "タイプ",
            "Max3",
        ],
        ascending=[
            True,
            False,
        ],
    )

    print(
        confirmed[
            display_columns
        ].to_string(
            index=False
        )
    )

    # ========================================================
    # ANAP / Schoo 比較
    # ========================================================

    print()
    print(
        "=" * 100
    )

    print(
        "=== ANAP / Schoo 比較 ==="
    )

    print(
        "=" * 100
    )

    print()

    comparison = df[
        df["コード"].isin(
            [
                "3189",
                "264A",
            ]
        )
    ].copy()

    comparison_columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "タイプ",
        "ChangePercent",
        "VolumeRatio",
        "VolumeRatio20",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "MA25Deviation",
        "足型",
        "終値位置",
        "実体率",
        "上ヒゲ率",
        "BreakoutSignal",
        "New30High",
        "Max3",
    ]

    comparison_columns = [
        column
        for column
        in comparison_columns
        if column in comparison.columns
    ]

    print(
        comparison[
            comparison_columns
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "保存 :",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()