from pathlib import Path

import pandas as pd


PANEL_FILE = Path(
    "data/analysis/initial_move_highlow_panel.csv"
)

RESULT_DIR = Path("results")

OUTPUT_FILE = Path(
    "data/analysis/initial_move_score_components.csv"
)

START_DATE = pd.Timestamp("2026-08-18")


def _bool_value(value):
    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "1.0",
        "yes",
        "y",
    }


def _number(value):
    return pd.to_numeric(
        value,
        errors="coerce",
    )


def _normalize_code(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def _rsi_penalty(rsi):
    rsi = _number(rsi)

    if pd.isna(rsi):
        return 0

    if rsi >= 95:
        return -3

    if rsi >= 90:
        return -2

    if rsi >= 85:
        return -1

    return 0


def _component_pattern(
    change,
    volume_ratio,
    breakout,
    new30,
):
    parts = []

    if pd.notna(change) and change >= 5:
        parts.append("Change")

    if (
        pd.notna(volume_ratio)
        and volume_ratio >= 3
    ):
        parts.append("Volume")

    if breakout:
        parts.append("Breakout")

    if new30:
        parts.append("New30High")

    if not parts:
        return "None"

    return "+".join(parts)


def _load_result(date_text):
    path = (
        RESULT_DIR
        / f"{date_text}_stock_result.csv"
    )

    if not path.exists():
        return None

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype=str,
    )

    code_col = "\u30b3\u30fc\u30c9"

    if code_col not in df.columns:
        return None

    df["_CodeKey"] = (
        df[code_col]
        .map(_normalize_code)
    )

    return df


def _summarize(group):
    n = len(group)

    high = pd.to_numeric(
        group["MaxHigh5Pct"],
        errors="coerce",
    )

    low = pd.to_numeric(
        group["MinLow5Pct"],
        errors="coerce",
    )

    peak = pd.to_numeric(
        group["PeakDay5"],
        errors="coerce",
    )

    return {
        "N": n,
        "HighMean": high.mean(),
        "HighMedian": high.median(),
        "Hit5": (high >= 5).mean() * 100,
        "Hit10": (high >= 10).mean() * 100,
        "Hit20": (high >= 20).mean() * 100,
        "LowMean": low.mean(),
        "LowMedian": low.median(),
        "TouchMinus5": (
            (low <= -5).mean() * 100
        ),
        "TouchMinus10": (
            (low <= -10).mean() * 100
        ),
        "PeakMedian": peak.median(),
    }


def main():
    print("=" * 78)
    print("INITIAL MOVE - SCORE COMPONENT ANALYSIS")
    print("=" * 78)

    panel = pd.read_csv(
        PANEL_FILE,
        encoding="utf-8-sig",
        dtype={
            "Code": str,
        },
    )

    panel["DetectionDate"] = pd.to_datetime(
        panel["DetectionDate"],
        errors="coerce",
    )

    panel["Code"] = (
        panel["Code"]
        .map(_normalize_code)
    )

    # Same basic cohort as Day5 analysis.
    cohort = panel[
        panel["DetectionDate"].notna()
        & (
            panel["DetectionDate"]
            >= START_DATE
        )
        & panel["InitialScore"].between(
            3,
            7,
        )
    ].copy()

    cohort = (
        cohort
        .sort_values(
            [
                "DetectionDate",
                "Code",
            ]
        )
        .drop_duplicates(
            subset=["Code"],
            keep="first",
        )
    )

    cohort = cohort[
        cohort["MaxHigh5Pct"].notna()
        & cohort["MinLow5Pct"].notna()
    ].copy()

    print(
        "Day5 first-detection cohort :",
        len(cohort),
    )

    result_cache = {}
    rows = []

    change_col = "\u524d\u65e5\u6bd4"

    for _, row in cohort.iterrows():

        date_text = (
            row["DetectionDate"]
            .strftime("%Y-%m-%d")
        )

        code = row["Code"]

        if date_text not in result_cache:
            result_cache[date_text] = (
                _load_result(date_text)
            )

        result_df = result_cache[
            date_text
        ]

        if result_df is None:
            continue

        matched = result_df[
            result_df["_CodeKey"] == code
        ]

        if matched.empty:
            continue

        source = matched.iloc[0]

        change = _number(
            source.get(change_col)
        )

        volume_ratio = _number(
            source.get("VolumeRatio")
        )

        breakout = _bool_value(
            source.get("BreakoutSignal")
        )

        new30 = _bool_value(
            source.get("New30High")
        )

        rsi = _number(
            source.get("RSI")
        )

        raw_score = 0

        if (
            pd.notna(change)
            and change >= 5
        ):
            raw_score += 3

        if (
            pd.notna(volume_ratio)
            and volume_ratio >= 3
        ):
            raw_score += 2

        if breakout:
            raw_score += 1

        if new30:
            raw_score += 1

        penalty = _rsi_penalty(rsi)

        rule_score = (
            raw_score
            + penalty
        )

        tracking_score = int(
            row["InitialScore"]
        )

        pattern = _component_pattern(
            change,
            volume_ratio,
            breakout,
            new30,
        )

        rows.append(
            {
                "DetectionDate": (
                    date_text
                ),
                "Code": code,
                "Name": row.get(
                    "Name"
                ),
                "TrackingScore": (
                    tracking_score
                ),
                "RuleRawScore": (
                    raw_score
                ),
                "RSI": rsi,
                "RSIPenalty": (
                    penalty
                ),
                "RuleScore": (
                    rule_score
                ),
                "ScoreConsistent": (
                    tracking_score
                    == rule_score
                ),
                "ChangePct": (
                    change
                ),
                "VolumeRatio": (
                    volume_ratio
                ),
                "BreakoutSignal": (
                    breakout
                ),
                "New30High": (
                    new30
                ),
                "Pattern": (
                    pattern
                ),
                "MaxHigh5Pct": row[
                    "MaxHigh5Pct"
                ],
                "MinLow5Pct": row[
                    "MinLow5Pct"
                ],
                "PeakDay5": row[
                    "PeakDay5"
                ],
            }
        )

    detail = pd.DataFrame(rows)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    detail.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "Result matched              :",
        len(detail),
    )

    consistent = detail[
        detail["ScoreConsistent"]
    ].copy()

    inconsistent = detail[
        ~detail["ScoreConsistent"]
    ].copy()

    print(
        "Current-rule consistent     :",
        len(consistent),
    )

    print(
        "Score mismatch              :",
        len(inconsistent),
    )

    print()
    print("=" * 78)
    print("PATTERN - CURRENT RULE CONSISTENT ONLY")
    print("=" * 78)

    if consistent.empty:
        print("No consistent rows")
        return

    groups = []

    for pattern, group in (
        consistent
        .groupby("Pattern")
    ):
        stats = _summarize(
            group
        )

        groups.append(
            {
                "Pattern": pattern,
                **stats,
            }
        )

    summary = pd.DataFrame(
        groups
    ).sort_values(
        [
            "N",
            "HighMedian",
        ],
        ascending=[
            False,
            False,
        ],
    )

    for _, r in summary.iterrows():
        print()
        print(
            f"{r['Pattern']}  "
            f"N={int(r['N'])}"
        )

        print(
            "  Day5 High "
            f"mean={r['HighMean']:6.2f}%  "
            f"median={r['HighMedian']:6.2f}%  "
            f"+5={r['Hit5']:5.1f}%  "
            f"+10={r['Hit10']:5.1f}%  "
            f"+20={r['Hit20']:5.1f}%"
        )

        print(
            "  Day5 Low  "
            f"mean={r['LowMean']:6.2f}%  "
            f"median={r['LowMedian']:6.2f}%  "
            f"-5={r['TouchMinus5']:5.1f}%  "
            f"-10={r['TouchMinus10']:5.1f}%  "
            f"PeakDayMed={r['PeakMedian']:.1f}"
        )

    print()
    print("=" * 78)
    print("SCORE x PATTERN")
    print("=" * 78)

    grouped = (
        consistent
        .groupby(
            [
                "TrackingScore",
                "Pattern",
            ]
        )
    )

    for (
        score,
        pattern,
    ), group in grouped:

        stats = _summarize(
            group
        )

        print(
            f"Score {score}  "
            f"{pattern:<42} "
            f"N={stats['N']:3d}  "
            f"HighMed={stats['HighMedian']:6.2f}%  "
            f"+5={stats['Hit5']:5.1f}%  "
            f"+10={stats['Hit10']:5.1f}%  "
            f"LowMed={stats['LowMedian']:6.2f}%  "
            f"-5={stats['TouchMinus5']:5.1f}%  "
            f"Peak={stats['PeakMedian']:.1f}"
        )

    print()
    print(
        "Saved :",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()
