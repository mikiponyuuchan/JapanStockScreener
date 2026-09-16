import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

ANALYSIS = ROOT / "data" / "analysis"
RESULTS = ROOT / "results"


RANK_ORDER = {
    "SG_NEXT20": 1,
    "SG_NEXT10": 2,
    "SG_BALANCED20": 3,
    "SG_NEXT_POSITIVE": 4,
    "SG": 5,
    "WATCH": 6,
}


def run(cmd):
    print()
    print("RUN :", " ".join(cmd))

    result = subprocess.run(
        cmd,
        cwd=ROOT,
    )

    if result.returncode != 0:
        raise SystemExit(
            f"Command failed: {result.returncode}"
        )


def clean_code(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )


def find_col(df, names):
    for name in names:
        if name in df.columns:
            return name

    return None


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
    )

    args = parser.parse_args()

    date_dash = args.date
    date_key = date_dash.replace(
        "-",
        "",
    )

    catalyst_file = (
        RESULTS
        / f"{date_dash}_earnings_catalyst.xlsx"
    )

    if not catalyst_file.exists():
        raise SystemExit(
            f"Missing: {catalyst_file}"
        )

    # Rebuild the existing earnings strength ranking.
    run(
        [
            sys.executable,
            "tools/analyze_earnings_strength.py",
            "--date",
            date_dash,
        ]
    )

    ranking_file = (
        ANALYSIS
        / f"{date_dash}_earnings_strength_ranking.csv"
    )

    if not ranking_file.exists():
        raise SystemExit(
            f"Missing: {ranking_file}"
        )

    rank = pd.read_csv(
        ranking_file,
        dtype=str,
    )

    if rank.empty:
        print()
        print("No eligible earnings.")
        return

    code_col = find_col(
        rank,
        [
            "Code",
            "???",
        ],
    )

    rating_col = find_col(
        rank,
        [
            "Rating",
            "????",
        ],
    )

    name_col = find_col(
        rank,
        [
            "Name",
            "???",
        ],
    )

    if code_col is None:
        raise SystemExit(
            "Code column not found."
        )

    if rating_col is None:
        raise SystemExit(
            "Rating column not found."
        )

    rank["CodeKey"] = clean_code(
        rank[code_col]
    )

    pdf_dir = (
        ANALYSIS
        / "earnings_pdf"
        / date_key
    )

    if not pdf_dir.exists():
        raise SystemExit(
            f"Missing PDF directory: {pdf_dir}"
        )

    sys.path.insert(
        0,
        str(ROOT / "tools"),
    )

    from earnings_progress_parser_v2 import (
        parse_pdf as parse_quarterly,
    )

    from earnings_full_year_parser_v1 import (
        parse_pdf as parse_full_year,
    )

    rows = []

    for _, source in rank.iterrows():
        code = source["CodeKey"]

        pdf = pdf_dir / f"{code}.pdf"

        if not pdf.exists():
            continue

        rating = str(
            source[rating_col]
        ).strip()

        name = (
            str(source[name_col]).strip()
            if name_col is not None
            else ""
        )

        q = parse_quarterly(
            pdf
        )

        q_status = str(
            q.get(
                "ParseStatus",
                "",
            )
        )

        # The quarterly parser explicitly marks
        # ordinary full-year results as FULL_YEAR.
        if q_status == "FULL_YEAR":
            fy = parse_full_year(
                pdf
            )

            status = str(
                fy.get(
                    "ParseStatus",
                    "",
                )
            )

            if status != "OK":
                rows.append(
                    {
                        "DetectionDate": date_dash,
                        "Code": code,
                        "Name": name,
                        "EarningsType": "FULL_YEAR",
                        "Rating": rating,
                        "ParseStatus": status,
                        "HypothesisRank": "WATCH",
                        "WarningFlag": "",
                    }
                )
                continue

            forecast = pd.to_numeric(
                fy.get(
                    "MinForecastGrowth4"
                ),
                errors="coerce",
            )

            warning = ""

            if pd.notna(
                forecast
            ) and forecast < 0:
                warning = "NEXT_FY_NEGATIVE"

            hypothesis = "WATCH"

            if rating == "STRONG_GOOD":
                hypothesis = "SG"

                if pd.notna(forecast):
                    if forecast >= 20:
                        hypothesis = "SG_NEXT20"
                    elif forecast >= 10:
                        hypothesis = "SG_NEXT10"
                    elif forecast >= 0:
                        hypothesis = (
                            "SG_NEXT_POSITIVE"
                        )

            rows.append(
                {
                    "DetectionDate": date_dash,
                    "Code": code,
                    "Name": name,
                    "EarningsType": "FULL_YEAR",
                    "Rating": rating,
                    "ParseStatus": status,
                    "MinGrowth4": pd.NA,
                    "MinProgressExcess": pd.NA,
                    "MinForecastGrowth4": forecast,
                    "Revision": "",
                    "WarningFlag": warning,
                    "HypothesisRank": hypothesis,
                }
            )

            continue

        if q_status != "OK":
            rows.append(
                {
                    "DetectionDate": date_dash,
                    "Code": code,
                    "Name": name,
                    "EarningsType": "QUARTERLY",
                    "Rating": rating,
                    "ParseStatus": q_status,
                    "HypothesisRank": "WATCH",
                    "WarningFlag": "",
                }
            )
            continue

        growth_values = []

        for key in [
            "SalesYoY",
            "OperatingYoY",
            "OrdinaryYoY",
            "NetYoY",
        ]:
            value = pd.to_numeric(
                q.get(key),
                errors="coerce",
            )

            growth_values.append(
                value
            )

        if all(
            pd.notna(x)
            for x in growth_values
        ):
            min_growth = min(
                growth_values
            )
        else:
            min_growth = pd.NA

        progress = pd.to_numeric(
            q.get(
                "MinProgressExcess"
            ),
            errors="coerce",
        )

        warning = ""

        if (
            pd.notna(progress)
            and progress < -10
        ):
            warning = "PROGRESS_DELAY"

        hypothesis = "WATCH"

        if rating == "STRONG_GOOD":
            hypothesis = "SG"

            if (
                pd.notna(min_growth)
                and min_growth >= 20
            ):
                hypothesis = (
                    "SG_BALANCED20"
                )

        rows.append(
            {
                "DetectionDate": date_dash,
                "Code": code,
                "Name": name,
                "EarningsType": "QUARTERLY",
                "Rating": rating,
                "ParseStatus": q_status,
                "MinGrowth4": min_growth,
                "MinProgressExcess": progress,
                "MinForecastGrowth4": pd.NA,
                "Revision": "",
                "WarningFlag": warning,
                "HypothesisRank": hypothesis,
            }
        )

    result = pd.DataFrame(
        rows
    )

    if result.empty:
        print()
        print("No parsed candidates.")
        return

    result["_RankOrder"] = (
        result[
            "HypothesisRank"
        ]
        .map(RANK_ORDER)
        .fillna(99)
    )

    result = result.sort_values(
        [
            "_RankOrder",
            "Code",
        ]
    )

    output_all = (
        ANALYSIS
        / f"{date_dash}_earnings_catalyst_ver1.csv"
    )

    result.drop(
        columns=["_RankOrder"]
    ).to_csv(
        output_all,
        index=False,
        encoding="utf-8-sig",
    )

    eligible = result[
        result[
            "HypothesisRank"
        ].ne("WATCH")
    ].copy()

    top3 = eligible.head(
        3
    ).drop(
        columns=["_RankOrder"]
    )

    output_top3 = (
        ANALYSIS
        / f"{date_dash}_earnings_catalyst_ver1_top3.csv"
    )

    top3.to_csv(
        output_top3,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 100)
    print("EARNINGS CATALYST VER1")
    print("=" * 100)

    print(
        "Detection date :",
        date_dash,
    )

    print(
        "Parsed         :",
        len(result),
    )

    print(
        "Eligible       :",
        len(eligible),
    )

    print(
        "TOP3           :",
        len(top3),
    )

    print()
    print("Hypothesis distribution")

    print(
        result[
            "HypothesisRank"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print("=" * 100)
    print("TOP3")
    print("=" * 100)

    if top3.empty:
        print(
            "No candidate."
        )
    else:
        show_cols = [
            "Code",
            "Name",
            "EarningsType",
            "Rating",
            "MinGrowth4",
            "MinProgressExcess",
            "MinForecastGrowth4",
            "WarningFlag",
            "HypothesisRank",
        ]

        show_cols = [
            x
            for x in show_cols
            if x in top3.columns
        ]

        print(
            top3[
                show_cols
            ].to_string(
                index=False
            )
        )

    print()
    print(
        "ALL  :",
        output_all,
    )

    print(
        "TOP3 :",
        output_top3,
    )


if __name__ == "__main__":
    main()
