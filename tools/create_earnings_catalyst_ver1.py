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
    # Keep source ASCII-only.
    #
    # Existing ranking CSV uses:
    #   code   = U+30B3 U+30FC U+30C9
    #   name   = either the correct name column
    #            or the historical typo column
    #   rating = earnings rating
    #
    # Determine the requested semantic field from
    # the ASCII aliases passed by the caller.

    cols = list(df.columns)

    if "Code" in names:
        candidates = [
            "Code",
            "\u30b3\u30fc\u30c9",
        ]

    elif "Rating" in names:
        candidates = [
            "Rating",
            "\u6c7a\u7b97\u8a55\u4fa1",
        ]

    elif "Name" in names:
        candidates = [
            "Name",
            "\u9298\u67c4\u540d",
            "\u9285\u67c4\u540d",
        ]

    elif "SalesYoY" in names:
        candidates = [
            "SalesYoY",
            "\u58f2\u4e0a\u524d\u5e74\u6bd4",
        ]

    elif "OperatingYoY" in names:
        candidates = [
            "OperatingYoY",
            "\u55b6\u696d\u5229\u76ca\u524d\u5e74\u6bd4",
        ]

    elif "OrdinaryYoY" in names:
        candidates = [
            "OrdinaryYoY",
            "\u7d4c\u5e38\u5229\u76ca\u524d\u5e74\u6bd4",
        ]

    elif "NetYoY" in names:
        candidates = [
            "NetYoY",
            "\u7d14\u5229\u76ca\u524d\u5e74\u6bd4",
        ]

    else:
        candidates = names

    for candidate in candidates:
        if candidate in cols:
            return candidate

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

    sales_yoy_col = find_col(
        rank,
        [
            "SalesYoY",
        ],
    )

    operating_yoy_col = find_col(
        rank,
        [
            "OperatingYoY",
        ],
    )

    ordinary_yoy_col = find_col(
        rank,
        [
            "OrdinaryYoY",
        ],
    )

    net_yoy_col = find_col(
        rank,
        [
            "NetYoY",
        ],
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

        for col in [
            sales_yoy_col,
            operating_yoy_col,
            ordinary_yoy_col,
            net_yoy_col,
        ]:
            if col is None:
                value = pd.NA
            else:
                value = pd.to_numeric(
                    source.get(col),
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

        operating_excess = pd.to_numeric(
            q.get(
                "OperatingProgressExcess"
            ),
            errors="coerce",
        )

        net_excess = pd.to_numeric(
            q.get(
                "NetProgressExcess"
            ),
            errors="coerce",
        )

        progress_values = [
            x
            for x in [
                operating_excess,
                net_excess,
            ]
            if pd.notna(x)
        ]

        if progress_values:
            progress = min(
                progress_values
            )
        else:
            progress = pd.NA

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

    result["_TieValue"] = pd.NA

    quarterly_mask = (
        result["EarningsType"]
        .eq("QUARTERLY")
    )

    full_year_mask = (
        result["EarningsType"]
        .eq("FULL_YEAR")
    )

    result.loc[
        quarterly_mask,
        "_TieValue",
    ] = pd.to_numeric(
        result.loc[
            quarterly_mask,
            "MinGrowth4",
        ],
        errors="coerce",
    )

    result.loc[
        full_year_mask,
        "_TieValue",
    ] = pd.to_numeric(
        result.loc[
            full_year_mask,
            "MinForecastGrowth4",
        ],
        errors="coerce",
    )

    result = result.sort_values(
        [
            "_RankOrder",
            "_TieValue",
            "Code",
        ],
        ascending=[
            True,
            False,
            True,
        ],
        na_position="last",
    )

    output_all = (
        ANALYSIS
        / f"{date_dash}_earnings_catalyst_ver1.csv"
    )

    result.drop(
        columns=[
            "_RankOrder",
            "_TieValue",
        ]
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
        columns=[
            "_RankOrder",
            "_TieValue",
        ]
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
