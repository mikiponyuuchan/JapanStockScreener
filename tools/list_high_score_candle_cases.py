from pathlib import Path
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

CANDLE_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "candle_buy_signal_analysis.csv"
)

TRACKING_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "initial_move_tracking_rebuilt.csv"
)


def main():

    candle = pd.read_csv(
        CANDLE_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
    )

    tracking = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
    )

    candle["検出日"] = (
        candle["検出日"]
        .astype(str)
        .str[:10]
    )

    tracking["検出日"] = (
        tracking["検出日"]
        .astype(str)
        .str[:10]
    )

    numeric_cols = [
        "初動スコア",
        "実体騰落率",
        "終値位置",
        "上ヒゲ率",
        "高値終値乖離率",
        "3日以内最大騰落率",
    ]

    for col in numeric_cols:

        candle[col] = pd.to_numeric(
            candle[col],
            errors="coerce",
        )

    for col in [
        "1日後騰落率",
        "2日後騰落率",
        "3日後騰落率",
    ]:

        tracking[col] = pd.to_numeric(
            tracking[col],
            errors="coerce",
        )

    # --------------------------------------------------
    # 初動スコア6点以上
    # --------------------------------------------------

    work = candle[
        candle["初動スコア"] >= 6
    ].copy()

    work = work.merge(
        tracking[
            [
                "検出日",
                "コード",
                "1日後騰落率",
                "2日後騰落率",
                "3日後騰落率",
            ]
        ],
        on=[
            "検出日",
            "コード",
        ],
        how="left",
    )

    # --------------------------------------------------
    # 足型
    # --------------------------------------------------

    work["足型"] = "同値"

    work.loc[
        work["陽線"] == True,
        "足型"
    ] = "陽線"

    work.loc[
        work["陰線"] == True,
        "足型"
    ] = "陰線"

    # --------------------------------------------------
    # 表示用
    # --------------------------------------------------

    work = work.rename(
        columns={
            "実体騰落率":
                "実体%",

            "上ヒゲ率":
                "上ヒゲ",

            "高値終値乖離率":
                "高値乖離%",

            "1日後騰落率":
                "Day1",

            "2日後騰落率":
                "Day2",

            "3日後騰落率":
                "Day3",

            "3日以内最大騰落率":
                "Max3",
        }
    )

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "足型",
        "実体%",
        "終値位置",
        "上ヒゲ",
        "高値乖離%",
        "Day1",
        "Day2",
        "Day3",
        "Max3",
    ]

    work = (
        work[
            columns
        ]
        .sort_values(
            [
                "初動スコア",
                "検出日",
                "コード",
            ],
            ascending=[
                False,
                True,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    print()
    print("=" * 120)
    print(
        "初動スコア6・7点 ローソク足検証"
    )
    print("=" * 120)
    print()

    print(
        work.to_string(
            index=False
        )
    )

    print()
    print(
        "対象件数 :",
        len(work)
    )


if __name__ == "__main__":
    main()