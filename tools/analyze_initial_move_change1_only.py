from pathlib import Path

import pandas as pd


INPUT_FILE = Path(
    "data/analysis/initial_move_score3_detail.csv"
)


def stats(series):

    s = pd.to_numeric(
        series,
        errors="coerce"
    ).dropna()

    if s.empty:
        return None

    return {
        "N": len(s),
        "Mean": s.mean(),
        "Median": s.median(),
        "Min": s.min(),
        "Max": s.max(),
    }


def main():

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    # ==========================================
    # 現行仕様の Change1-only だけ
    # ==========================================

    target = df[
        df["ScorePattern"] == "Change1"
    ].copy()

    print("=" * 100)
    print("CHANGE1-ONLY ANALYSIS")
    print("=" * 100)

    print("Target :", len(target))

    # ==========================================
    # 成功区分
    # ==========================================

    high5 = pd.to_numeric(
        target["MaxHigh5Pct"],
        errors="coerce"
    )

    target["OutcomeGroup"] = "Middle"

    target.loc[
        high5 >= 10,
        "OutcomeGroup"
    ] = "Success"

    target.loc[
        high5 < 5,
        "OutcomeGroup"
    ] = "Failure"

    print()
    print("Outcome distribution")
    print(
        target["OutcomeGroup"]
        .value_counts()
        .reindex(
            [
                "Success",
                "Middle",
                "Failure",
            ]
        )
        .fillna(0)
        .astype(int)
        .to_string()
    )

    # ==========================================
    # 検出時指標
    # ==========================================

    candidates = [
        "Change1",
        "Change5",
        "VolumeRatio",
        "VolumeRatio20",
        "RSI",
    ]

    available = [
        c
        for c in candidates
        if c in target.columns
    ]

    print()
    print("=" * 100)
    print("DETECTION-TIME FACTORS")
    print("=" * 100)

    for col in available:

        print()
        print(f"[{col}]")

        for group in [
            "Success",
            "Middle",
            "Failure",
        ]:

            g = target[
                target["OutcomeGroup"]
                == group
            ]

            result = stats(
                g[col]
            )

            if result is None:
                continue

            print(
                f"{group:8s} "
                f"N={result['N']:2d}  "
                f"mean={result['Mean']:8.2f}  "
                f"median={result['Median']:8.2f}  "
                f"min={result['Min']:8.2f}  "
                f"max={result['Max']:8.2f}"
            )

    # ==========================================
    # 結果側
    # ==========================================

    print()
    print("=" * 100)
    print("OUTCOME CHARACTERISTICS")
    print("=" * 100)

    outcome_cols = [
        "MaxHigh5Pct",
        "MinLow5Pct",
        "PeakDay5",
    ]

    for col in outcome_cols:

        print()
        print(f"[{col}]")

        for group in [
            "Success",
            "Middle",
            "Failure",
        ]:

            g = target[
                target["OutcomeGroup"]
                == group
            ]

            result = stats(
                g[col]
            )

            if result is None:
                continue

            print(
                f"{group:8s} "
                f"N={result['N']:2d}  "
                f"mean={result['Mean']:8.2f}  "
                f"median={result['Median']:8.2f}"
            )

    # ==========================================
    # 個別一覧
    # ==========================================

    print()
    print("=" * 100)
    print("DETAIL")
    print("=" * 100)

    cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Change1",
        "Change5",
        "VolumeRatio",
        "VolumeRatio20",
        "RSI",
        "MaxHigh5Pct",
        "MinLow5Pct",
        "PeakDay5",
        "OutcomeGroup",
    ]

    cols = [
        c
        for c in cols
        if c in target.columns
    ]

    target = target.sort_values(
        "MaxHigh5Pct",
        ascending=False
    )

    print(
        target[cols]
        .to_string(index=False)
    )

    # ==========================================
    # 保存
    # ==========================================

    output = Path(
        "data/analysis/"
        "initial_move_change1_only_analysis.csv"
    )

    target.to_csv(
        output,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("Saved :", output)


if __name__ == "__main__":
    main()
