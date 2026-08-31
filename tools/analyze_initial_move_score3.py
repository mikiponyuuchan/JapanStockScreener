from pathlib import Path

import pandas as pd


PANEL_FILE = Path(
    "data/analysis/initial_move_highlow_panel.csv"
)

RESULT_DIR = Path("results")

START_DATE = pd.Timestamp("2026-08-18")


def find_col(df, candidates):

    for col in candidates:
        if col in df.columns:
            return col

    return None


def bool_value(v):

    if pd.isna(v):
        return False

    if isinstance(v, bool):
        return v

    s = str(v).strip().lower()

    return s in [
        "true",
        "1",
        "1.0",
        "yes",
        "○",
    ]


def main():

    panel = pd.read_csv(
        PANEL_FILE,
        encoding="utf-8-sig"
    )

    panel["DetectionDate"] = pd.to_datetime(
        panel["DetectionDate"],
        errors="coerce"
    )

    panel["InitialScore"] = pd.to_numeric(
        panel["InitialScore"],
        errors="coerce"
    )

    # ==========================================
    # 現行仕様期間
    # ==========================================

    panel = panel[
        panel["DetectionDate"]
        >= START_DATE
    ].copy()

    # ==========================================
    # First detection per code
    # ==========================================

    first = (
        panel
        .sort_values(
            [
                "DetectionDate",
                "Code",
            ]
        )
        .drop_duplicates(
            subset=["Code"],
            keep="first"
        )
        .copy()
    )

    # ==========================================
    # Day5成熟
    # ==========================================

    first = first[
        pd.to_numeric(
            first["Day5ClosePct"],
            errors="coerce"
        ).notna()
    ].copy()

    # ==========================================
    # Score3のみ
    # ==========================================

    score3 = first[
        first["InitialScore"] == 3
    ].copy()

    print("=" * 90)
    print("SCORE 3 - DAY5 MATURE FIRST DETECTION")
    print("=" * 90)

    print(
        "Target rows :",
        len(score3)
    )

    # ==========================================
    # 日別result CSVを読む
    # ==========================================

    result_maps = {}

    for date in sorted(
        score3["DetectionDate"]
        .dropna()
        .dt.normalize()
        .unique()
    ):

        date = pd.Timestamp(date)

        file = RESULT_DIR / (
            date.strftime("%Y-%m-%d")
            + "_stock_result.csv"
        )

        if not file.exists():

            print(
                "RESULT FILE NOT FOUND :",
                file
            )

            continue

        try:

            df = pd.read_csv(
                file,
                encoding="utf-8-sig"
            )

        except Exception as e:

            print(
                "READ ERROR :",
                file,
                e
            )

            continue

        code_col = find_col(
            df,
            [
                "コード",
                "Code",
                "code",
            ]
        )

        if code_col is None:

            print(
                "CODE COLUMN NOT FOUND :",
                file
            )

            continue

        df["_CodeKey"] = (
            df[code_col]
            .astype(str)
            .str.strip()
        )

        result_maps[
            date.normalize()
        ] = df

    # ==========================================
    # 検出時条件を付加
    # ==========================================

    rows = []

    for _, row in score3.iterrows():

        detection_date = (
            pd.Timestamp(
                row["DetectionDate"]
            )
            .normalize()
        )

        code = str(
            row["Code"]
        ).strip()

        result_df = result_maps.get(
            detection_date
        )

        if result_df is None:
            continue

        matched = result_df[
            result_df["_CodeKey"]
            == code
        ]

        if matched.empty:

            print(
                "CODE NOT FOUND :",
                detection_date.date(),
                code
            )

            continue

        src = matched.iloc[0]

        change1_col = find_col(
            result_df,
            [
                "前日比",
                "Change1",
                "ChangePercent",
            ]
        )

        change5_col = find_col(
            result_df,
            [
                "5日騰落率",
                "Change5",
            ]
        )

        vr_col = find_col(
            result_df,
            [
                "VolumeRatio",
                "出来高倍率",
            ]
        )

        vr20_col = find_col(
            result_df,
            [
                "VolumeRatio20",
            ]
        )

        breakout_col = find_col(
            result_df,
            [
                "BreakoutSignal",
            ]
        )

        high30_col = find_col(
            result_df,
            [
                "New30High",
            ]
        )

        rsi_col = find_col(
            result_df,
            [
                "RSI",
            ]
        )

        rsi_penalty_col = find_col(
            result_df,
            [
                "RSI減点",
            ]
        )

        out = row.to_dict()

        def num(col):

            if col is None:
                return None

            return pd.to_numeric(
                src[col],
                errors="coerce"
            )

        out["Change1"] = num(
            change1_col
        )

        out["Change5"] = num(
            change5_col
        )

        out["VolumeRatio"] = num(
            vr_col
        )

        out["VolumeRatio20"] = num(
            vr20_col
        )

        out["RSI"] = num(
            rsi_col
        )

        out["RSIPenalty"] = num(
            rsi_penalty_col
        )

        out["BreakoutSignal"] = (
            bool_value(
                src[breakout_col]
            )
            if breakout_col
            else False
        )

        out["New30High"] = (
            bool_value(
                src[high30_col]
            )
            if high30_col
            else False
        )

        # ======================================
        # 現行4条件を再構築
        # ======================================

        change_points = (
            3
            if (
                pd.notna(out["Change1"])
                and out["Change1"] >= 5
            )
            else 0
        )

        volume_points = (
            2
            if (
                pd.notna(out["VolumeRatio"])
                and out["VolumeRatio"] >= 3
            )
            else 0
        )

        breakout_points = (
            1
            if out["BreakoutSignal"]
            else 0
        )

        high30_points = (
            1
            if out["New30High"]
            else 0
        )

        raw_rebuilt = (
            change_points
            + volume_points
            + breakout_points
            + high30_points
        )

        out["ChangePoints"] = (
            change_points
        )

        out["VolumePoints"] = (
            volume_points
        )

        out["BreakoutPoints"] = (
            breakout_points
        )

        out["New30HighPoints"] = (
            high30_points
        )

        out["RawScoreRebuilt"] = (
            raw_rebuilt
        )

        # ======================================
        # 条件パターン
        # ======================================

        parts = []

        if change_points:
            parts.append("Change1")

        if volume_points:
            parts.append("Volume")

        if breakout_points:
            parts.append("Breakout")

        if high30_points:
            parts.append("New30High")

        if not parts:
            parts.append("None")

        out["ScorePattern"] = (
            "+".join(parts)
        )

        rows.append(out)

    detail = pd.DataFrame(
        rows
    )

    if detail.empty:

        print(
            "NO MATCHED DATA"
        )

        return

    # ==========================================
    # パターン分布
    # ==========================================

    print()
    print("=" * 90)
    print("SCORE PATTERN DISTRIBUTION")
    print("=" * 90)

    pattern_counts = (
        detail["ScorePattern"]
        .value_counts()
    )

    print(
        pattern_counts.to_string()
    )

    # ==========================================
    # 各パターンの5日結果
    # ==========================================

    print()
    print("=" * 90)
    print("PATTERN PERFORMANCE")
    print("=" * 90)

    for pattern, g in detail.groupby(
        "ScorePattern",
        sort=False
    ):

        high5 = pd.to_numeric(
            g["MaxHigh5Pct"],
            errors="coerce"
        ).dropna()

        low5 = pd.to_numeric(
            g["MinLow5Pct"],
            errors="coerce"
        ).dropna()

        peak = pd.to_numeric(
            g["PeakDay5"],
            errors="coerce"
        ).dropna()

        print()
        print(
            f"[{pattern}]  N={len(g)}"
        )

        if not high5.empty:

            print(
                "  MaxHigh5 "
                f"mean={high5.mean():6.2f}%  "
                f"median={high5.median():6.2f}%  "
                f"+5={((high5 >= 5).mean()*100):5.1f}%  "
                f"+10={((high5 >= 10).mean()*100):5.1f}%  "
                f"+20={((high5 >= 20).mean()*100):5.1f}%"
            )

        if not low5.empty:

            print(
                "  MinLow5  "
                f"mean={low5.mean():6.2f}%  "
                f"median={low5.median():6.2f}%  "
                f"-5={((low5 <= -5).mean()*100):5.1f}%  "
                f"-10={((low5 <= -10).mean()*100):5.1f}%"
            )

        if not peak.empty:

            print(
                "  PeakDay5 "
                f"median={peak.median():.1f}"
            )

    # ==========================================
    # 個別33銘柄
    # ==========================================

    print()
    print("=" * 90)
    print("DETAIL")
    print("=" * 90)

    detail_cols = [
        "DetectionDate",
        "Code",
        "Name",
        "Change1",
        "Change5",
        "VolumeRatio",
        "VolumeRatio20",
        "RSI",
        "RSIPenalty",
        "BreakoutSignal",
        "New30High",
        "RawScoreRebuilt",
        "ScorePattern",
        "MaxHigh5Pct",
        "MinLow5Pct",
        "PeakDay5",
    ]

    print(
        detail[
            detail_cols
        ]
        .sort_values(
            "MaxHigh5Pct",
            ascending=False
        )
        .to_string(
            index=False
        )
    )

    # ==========================================
    # CSV保存
    # ==========================================

    output = Path(
        "data/analysis/"
        "initial_move_score3_detail.csv"
    )

    detail.to_csv(
        output,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(
        "Saved :",
        output
    )


if __name__ == "__main__":
    main()
