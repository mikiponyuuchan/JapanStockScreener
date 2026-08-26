from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT
    / "data"
    / "tracking"
    / "buy_decision_backtest_panel.csv"
)

E_DETAILS_INPUT = (
    ROOT
    / "data"
    / "tracking"
    / "early_buy_candidate_details.csv"
)

OUTPUT = (
    ROOT
    / "data"
    / "tracking"
    / "day2_rebound_boundary_summary.csv"
)

THRESHOLDS = [
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    3.5,
    4.0,
    5.0,
]


def main():

    print("=" * 140)
    print("Day2反発幅 境界精査")
    print("=" * 140)

    df = pd.read_csv(
        INPUT,
        encoding="utf-8-sig",
        low_memory=False,
    )

    print()
    print("読込 :", INPUT)
    print("行数 :", len(df))

    numeric_cols = [
        "初動スコア",
        "5日騰落率",
        "VolumeRatio20",
        "Day1",
        "Day2",
        "Day3",
        "Day4",
        "Day5",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    # ============================================================
    # 正式P5条件236件を取得
    # ============================================================

    e_source = pd.read_csv(
        E_DETAILS_INPUT,
        encoding="utf-8-sig",
        low_memory=False,
    )

    e_source = e_source[
        e_source["条件"]
        == "E_C_plus_Volume20gt1"
    ].copy()

    # 結合キーを文字列へ統一
    e_source["検出日"] = (
        e_source["検出日"]
        .astype(str)
    )

    e_source["コード"] = (
        e_source["コード"]
        .astype(str)
    )

    df["検出日"] = (
        df["検出日"]
        .astype(str)
    )

    df["コード"] = (
        df["コード"]
        .astype(str)
    )

    keys = (
        e_source[
            [
                "検出日",
                "コード",
            ]
        ]
        .drop_duplicates()
    )

    e = keys.merge(
        df,
        on=[
            "検出日",
            "コード",
        ],
        how="left",
    )

    print()
    print(
        "正式P5条件件数 :",
        len(keys),
    )

    print(
        "panel結合件数 :",
        len(e),
    )

    # Day1で下落した候補だけ
    e = e[
        e["Day1"] < 0
    ].copy()

    # Day1からDay2への反発幅
    e["反発幅"] = (
        e["Day2"]
        - e["Day1"]
    )

    # Day2終値で買った場合の
    # Day3～Day5の騰落率
    for day in [3, 4, 5]:

        e[f"買い後Day{day}"] = (
            (
                (1 + e[f"Day{day}"] / 100)
                / (1 + e["Day2"] / 100)
                - 1
            )
            * 100
        )

    future_cols = [
        "買い後Day3",
        "買い後Day4",
        "買い後Day5",
    ]

    complete = (
        e[future_cols]
        .notna()
        .all(axis=1)
    )

    e["EntryMax3"] = pd.NA
    e["EntryMin3"] = pd.NA

    e.loc[
        complete,
        "EntryMax3",
    ] = (
        e.loc[
            complete,
            future_cols,
        ]
        .max(axis=1)
    )

    e.loc[
        complete,
        "EntryMin3",
    ] = (
        e.loc[
            complete,
            future_cols,
        ]
        .min(axis=1)
    )

    e["EntryMax3"] = pd.to_numeric(
        e["EntryMax3"],
        errors="coerce",
    )

    e["EntryMin3"] = pd.to_numeric(
        e["EntryMin3"],
        errors="coerce",
    )

    print()
    print("P5基本 Day1下落件数 :", len(e))

    rows = []

    for threshold in THRESHOLDS:

        x = e[
            e["反発幅"] >= threshold
        ].copy()

        confirmed = x[
            x["EntryMax3"].notna()
            & x["EntryMin3"].notna()
        ].copy()

        n = len(confirmed)

        if n == 0:
            continue

        plus5 = (
            confirmed["EntryMax3"] >= 5
        ).sum()

        plus10 = (
            confirmed["EntryMax3"] >= 10
        ).sum()

        minus3 = (
            confirmed["EntryMin3"] <= -3
        ).sum()

        minus5 = (
            confirmed["EntryMin3"] <= -5
        ).sum()

        rows.append(
            {
                "反発幅閾値": threshold,
                "候補数": len(x),
                "有効件数": n,
                "Max3平均": round(
                    confirmed["EntryMax3"].mean(),
                    2,
                ),
                "Max3中央値": round(
                    confirmed["EntryMax3"].median(),
                    2,
                ),
                "+5%件数": int(plus5),
                "+5%到達率": round(
                    plus5 / n * 100,
                    2,
                ),
                "+10%件数": int(plus10),
                "+10%到達率": round(
                    plus10 / n * 100,
                    2,
                ),
                "-3%件数": int(minus3),
                "-3%逆行率": round(
                    minus3 / n * 100,
                    2,
                ),
                "-5%件数": int(minus5),
                "-5%逆行率": round(
                    minus5 / n * 100,
                    2,
                ),
            }
        )

    summary = pd.DataFrame(rows)

    print()
    print("=" * 140)
    print("境界テスト")
    print("=" * 140)

    print(
        summary.to_string(
            index=False
        )
    )

    # 1.5～4.0%の境界付近を実銘柄で確認
    focus = e[
        (e["反発幅"] >= 1.5)
        & (e["反発幅"] < 4.0)
    ].copy()

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "前日比",
        "5日騰落率",
        "VolumeRatio20",
        "Day1",
        "Day2",
        "反発幅",
        "Day3",
        "Day4",
        "Day5",
        "EntryMax3",
        "EntryMin3",
    ]

    print()
    print("=" * 140)
    print("反発幅 1.5%以上 4.0%未満")
    print("=" * 140)

    if focus.empty:
        print("該当なし")
    else:
        print(
            focus[
                columns
            ]
            .sort_values("反発幅")
            .to_string(index=False)
        )

    summary.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 140)
    print("保存 :", OUTPUT)
    print("=" * 140)


if __name__ == "__main__":
    main()
