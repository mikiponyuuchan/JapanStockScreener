from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

TRACKING_DIR = (
    ROOT_DIR
    / "data"
    / "tracking"
)

AVOID_FILE = (
    TRACKING_DIR
    / "buy_avoid_alert_analysis.csv"
)

FACTOR_FILE = (
    TRACKING_DIR
    / "high_score_buy_factor_analysis.csv"
)

CANDLE_FILE = (
    TRACKING_DIR
    / "candle_buy_signal_analysis.csv"
)

OUTPUT_FILE = (
    TRACKING_DIR
    / "buy_candidate_analysis.csv"
)


def normalize_code(value):
    return (
        str(value)
        .replace(".0", "")
        .strip()
    )


def main():

    # ========================================================
    # 読み込み
    # ========================================================

    avoid = pd.read_csv(
        AVOID_FILE,
        encoding="utf-8-sig",
        dtype={"コード": str},
    )

    factor = pd.read_csv(
        FACTOR_FILE,
        encoding="utf-8-sig",
        dtype={"コード": str},
    )

    candle = pd.read_csv(
        CANDLE_FILE,
        encoding="utf-8-sig",
        dtype={"コード": str},
    )

    for df in [
        avoid,
        factor,
        candle,
    ]:
        df["コード"] = (
            df["コード"]
            .map(normalize_code)
        )

        df["検出日"] = (
            df["検出日"]
            .astype(str)
            .str[:10]
        )

    # ========================================================
    # 初動6・7点
    # ========================================================

    factor["初動スコア"] = pd.to_numeric(
        factor["初動スコア"],
        errors="coerce",
    )

    factor = factor[
        factor["初動スコア"] >= 6
    ].copy()

    # ========================================================
    # 買い回避情報を結合
    # ========================================================

    avoid_columns = [
        "検出日",
        "コード",
        "買い回避",
        "買い回避理由",
    ]

    work = factor.merge(
        avoid[avoid_columns],
        on=[
            "検出日",
            "コード",
        ],
        how="left",
    )

    # ========================================================
    # ローソク足情報を結合
    # ========================================================

    candle_columns = [
        "検出日",
        "コード",
        "陽線",
        "陰線",
        "実体騰落率",
        "当日値幅率",
        "高値終値乖離率",
        "終値位置",
        "実体率",
        "上ヒゲ率",
        "下ヒゲ率",
    ]

    work = work.merge(
        candle[candle_columns],
        on=[
            "検出日",
            "コード",
        ],
        how="left",
    )

    # ========================================================
    # 買い回避なしだけ残す
    # ========================================================

    work["買い回避"] = (
        work["買い回避"]
        .fillna(False)
        .astype(bool)
    )

    work = work[
        ~work["買い回避"]
    ].copy()

    # ========================================================
    # Max3確定分
    # ========================================================

    work["Max3"] = pd.to_numeric(
        work["Max3"],
        errors="coerce",
    )

    confirmed = work[
        work["Max3"].notna()
    ].copy()

    # ========================================================
    # 成績分類
    # ========================================================

    def classify(value):

        if value >= 5:
            return "成功(+5%以上)"

        if value >= 0:
            return "中間(0～+5%)"

        return "失敗(0%未満)"

    confirmed["結果区分"] = (
        confirmed["Max3"]
        .map(classify)
    )

    # ========================================================
    # 保存
    # ========================================================

    confirmed.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 100)
    print(
        "買い回避通過 × 初動スコア6・7点"
    )
    print("=" * 100)

    print(
        "対象件数 :",
        len(confirmed)
    )

    print()

    # ========================================================
    # 分類件数
    # ========================================================

    order = [
        "成功(+5%以上)",
        "中間(0～+5%)",
        "失敗(0%未満)",
    ]

    print("=" * 100)
    print("=== 成績分類 ===")
    print("=" * 100)

    for label in order:

        part = confirmed[
            confirmed["結果区分"] == label
        ]

        if part.empty:
            continue

        print(
            f"{label:14s} : "
            f"{len(part)}件"
        )

    # ========================================================
    # 比較する数値項目
    # ========================================================

    columns = [
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
    ]

    for column in columns:

        if column not in confirmed.columns:
            continue

        confirmed[column] = pd.to_numeric(
            confirmed[column],
            errors="coerce",
        )

    print()
    print("=" * 100)
    print("=== 成功・中間・失敗 平均値比較 ===")
    print("=" * 100)

    summary_rows = []

    for label in order:

        part = confirmed[
            confirmed["結果区分"] == label
        ]

        if part.empty:
            continue

        row = {
            "区分": label,
            "件数": len(part),
        }

        for column in columns:

            if column not in part.columns:
                continue

            row[column] = round(
                part[column].mean(),
                2,
            )

        summary_rows.append(row)

    summary = pd.DataFrame(
        summary_rows
    )

    print(
        summary.to_string(
            index=False
        )
    )

    # ========================================================
    # Breakout / New30High
    # ========================================================

    print()
    print("=" * 100)
    print("=== シグナル発生率 ===")
    print("=" * 100)

    signal_columns = [
        "BreakoutSignal",
        "New30High",
    ]

    signal_rows = []

    for label in order:

        part = confirmed[
            confirmed["結果区分"] == label
        ]

        if part.empty:
            continue

        row = {
            "区分": label,
            "件数": len(part),
        }

        for column in signal_columns:

            if column not in part.columns:
                continue

            values = (
                part[column]
                .astype(str)
                .str.lower()
                .eq("true")
            )

            row[
                f"{column}率"
            ] = round(
                values.mean()
                * 100,
                1,
            )

        signal_rows.append(row)

    signal_summary = pd.DataFrame(
        signal_rows
    )

    print(
        signal_summary.to_string(
            index=False
        )
    )

    # ========================================================
    # 銘柄一覧
    # ========================================================

    print()
    print("=" * 100)
    print("=== 個別銘柄 ===")
    print("=" * 100)

    display_columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "結果区分",
        "ChangePercent",
        "VolumeRatio",
        "VolumeRatio20",
        "5日騰落率",
        "RSI",
        "MA25Deviation",
        "足型",
        "終値位置",
        "上ヒゲ率",
        "BreakoutSignal",
        "New30High",
        "Max3",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in confirmed.columns
    ]

    print(
        confirmed[
            display_columns
        ]
        .sort_values(
            "Max3",
            ascending=False,
        )
        .to_string(
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