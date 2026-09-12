import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "data" / "analysis"

COL_GU = "\u0047\u0055\u7387"
COL_0930 = "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387"
COL_HIGH = "\u7fcc\u65e5\u9ad8\u5024\u7387"
COL_CLOSE = "\u7fcc\u65e5\u7d42\u5024\u7387"


def normalize_code(value):
    s = str(value).strip()

    if s.endswith(".0"):
        s = s[:-2]

    return s


def load_one_day(target_date):
    date_str = target_date.strftime(
        "%Y-%m-%d"
    )

    strength_path = (
        ANALYSIS_DIR
        / f"{date_str}_earnings_strength_ranking.csv"
    )

    next_path = (
        ANALYSIS_DIR
        / f"{date_str}_earnings_next_day.csv"
    )

    if (
        not strength_path.exists()
        or not next_path.exists()
    ):
        return None

    try:
        strength = pd.read_csv(
            strength_path,
            dtype=str,
        )

        next_day = pd.read_csv(
            next_path,
            dtype=str,
        )
    except pd.errors.EmptyDataError:
        return None

    if (
        strength.empty
        or next_day.empty
    ):
        return None

    if (
        "StrengthScore" not in strength.columns
        or "StrengthScoreV2" not in strength.columns
        or "Code" not in next_day.columns
    ):
        return None

    code_col = strength.columns[0]

    strength["CodeKey"] = (
        strength[code_col]
        .map(normalize_code)
    )

    next_day["CodeKey"] = (
        next_day["Code"]
        .map(normalize_code)
    )

    strength["StrengthScore"] = pd.to_numeric(
        strength["StrengthScore"],
        errors="coerce",
    )

    strength["StrengthScoreV2"] = pd.to_numeric(
        strength["StrengthScoreV2"],
        errors="coerce",
    )

    v1 = strength.sort_values(
        "StrengthScore",
        ascending=False,
    ).copy()

    v1["RankV1"] = range(
        1,
        len(v1) + 1,
    )

    v2 = strength.sort_values(
        "StrengthScoreV2",
        ascending=False,
    ).copy()

    v2["RankV2"] = range(
        1,
        len(v2) + 1,
    )

    rank_v1 = dict(
        zip(
            v1["CodeKey"],
            v1["RankV1"],
        )
    )

    rank_v2 = dict(
        zip(
            v2["CodeKey"],
            v2["RankV2"],
        )
    )

    next_day["RankV1"] = (
        next_day["CodeKey"]
        .map(rank_v1)
    )

    next_day["RankV2"] = (
        next_day["CodeKey"]
        .map(rank_v2)
    )

    score_v1 = dict(
        zip(
            strength["CodeKey"],
            strength["StrengthScore"],
        )
    )

    score_v2 = dict(
        zip(
            strength["CodeKey"],
            strength["StrengthScoreV2"],
        )
    )

    next_day["StrengthScore"] = (
        next_day["CodeKey"]
        .map(score_v1)
    )

    next_day["StrengthScoreV2"] = (
        next_day["CodeKey"]
        .map(score_v2)
    )

    next_day["DetectionDate"] = date_str

    for col in [
        COL_GU,
        COL_0930,
        COL_HIGH,
        COL_CLOSE,
    ]:
        if col in next_day.columns:
            next_day[col] = pd.to_numeric(
                next_day[col],
                errors="coerce",
            )

    return next_day


def print_stats(
    title,
    df,
):
    print()
    print(
        "=" * 86
    )
    print(title)
    print(
        "=" * 86
    )

    if df.empty:
        print("N=0")
        return

    print(
        "N =",
        len(df),
    )

    metrics = [
        ("GU", COL_GU),
        ("09:30", COL_0930),
        ("HIGH", COL_HIGH),
        ("CLOSE", COL_CLOSE),
    ]

    for label, col in metrics:
        if col not in df.columns:
            continue

        values = (
            pd.to_numeric(
                df[col],
                errors="coerce",
            )
            .dropna()
        )

        if values.empty:
            continue

        print(
            f"{label:<6}",
            f"mean={values.mean():7.2f}%",
            f"median={values.median():7.2f}%",
            f"plus={(values > 0).mean() * 100:6.1f}%",
        )

    if COL_HIGH in df.columns:
        high = (
            pd.to_numeric(
                df[COL_HIGH],
                errors="coerce",
            )
            .dropna()
        )

        if not high.empty:
            print(
                "HIGH thresholds:",
                f"+3={(high >= 3).mean() * 100:5.1f}%",
                f"+5={(high >= 5).mean() * 100:5.1f}%",
                f"+10={(high >= 10).mean() * 100:5.1f}%",
            )

    if COL_CLOSE in df.columns:
        close = (
            pd.to_numeric(
                df[COL_CLOSE],
                errors="coerce",
            )
            .dropna()
        )

        if not close.empty:
            print(
                "Close positive:",
                f"{(close > 0).mean() * 100:.1f}%",
            )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start",
        default="2026-08-14",
    )

    parser.add_argument(
        "--end",
        default="2026-09-10",
    )

    args = parser.parse_args()

    start = pd.Timestamp(
        args.start
    )

    end = pd.Timestamp(
        args.end
    )

    frames = []

    d = start

    while d <= end:
        frame = load_one_day(
            d
        )

        if frame is not None:
            frames.append(
                frame
            )

        d += pd.Timedelta(
            days=1
        )

    if not frames:
        print(
            "No backtest data."
        )
        return

    panel = pd.concat(
        frames,
        ignore_index=True,
    )

    out_path = (
        ANALYSIS_DIR
        / "earnings_backtest_panel.csv"
    )

    panel.to_csv(
        out_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "=" * 86
    )
    print(
        "EARNINGS BACKTEST SUMMARY"
    )
    print(
        "=" * 86
    )

    print(
        "Period :",
        args.start,
        "-",
        args.end,
    )

    print(
        "Days with candidates :",
        panel["DetectionDate"].nunique(),
    )

    print(
        "Total candidates     :",
        len(panel),
    )

    #
    # V1 / V2 TOP3
    #
    v1_top3 = panel[
        panel["RankV1"] <= 3
    ].copy()

    v2_top3 = panel[
        panel["RankV2"] <= 3
    ].copy()

    print_stats(
        "V1 TOP3",
        v1_top3,
    )

    print_stats(
        "V2 TOP3",
        v2_top3,
    )

    #
    # V2 rank-by-rank
    #
    for rank in [
        1,
        2,
        3,
    ]:
        part = panel[
            panel["RankV2"] == rank
        ]

        print_stats(
            f"V2 RANK {rank}",
            part,
        )

    #
    # Original earnings rating
    #
    if "Rating" in panel.columns:
        for rating in [
            "STRONG_GOOD",
            "GOOD",
        ]:
            part = panel[
                panel["Rating"]
                == rating
            ]

            print_stats(
                rating,
                part,
            )

    #
    # Difference between V1 and V2 selections.
    #
    v1_keys = set(
        zip(
            v1_top3[
                "DetectionDate"
            ],
            v1_top3[
                "CodeKey"
            ],
        )
    )

    v2_keys = set(
        zip(
            v2_top3[
                "DetectionDate"
            ],
            v2_top3[
                "CodeKey"
            ],
        )
    )

    v1_only_keys = (
        v1_keys - v2_keys
    )

    v2_only_keys = (
        v2_keys - v1_keys
    )

    v1_only = panel[
        panel.apply(
            lambda row: (
                row["DetectionDate"],
                row["CodeKey"],
            ) in v1_only_keys,
            axis=1,
        )
    ]

    v2_only = panel[
        panel.apply(
            lambda row: (
                row["DetectionDate"],
                row["CodeKey"],
            ) in v2_only_keys,
            axis=1,
        )
    ]

    print_stats(
        "V1 ONLY",
        v1_only,
    )

    print_stats(
        "V2 ONLY",
        v2_only,
    )

    print()
    print(
        "Saved :",
        out_path,
    )


if __name__ == "__main__":
    main()
