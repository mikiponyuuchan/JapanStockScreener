from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PROGRESS_FILE = (
    ROOT / "data" / "analysis"
    / "earnings_progress_return_panel.csv"
)

FULL_YEAR_FILE = (
    ROOT / "data" / "analysis"
    / "earnings_full_year_return_panel.csv"
)

OUTPUT_CSV = (
    ROOT / "data" / "analysis"
    / "earnings_catalyst_unified.csv"
)

OUTPUT_XLSX = (
    ROOT / "data" / "analysis"
    / "earnings_catalyst_unified.xlsx"
)


def clean_code(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )


def first_existing(df, names, default=None):
    for name in names:
        if name in df.columns:
            return df[name]

    return pd.Series(
        default,
        index=df.index,
    )


def make_quarterly(df):
    out = pd.DataFrame(
        index=df.index
    )

    out["DetectionDate"] = first_existing(
        df,
        ["DetectionDate"],
    )

    out["Code"] = clean_code(
        first_existing(
            df,
            ["Code", "CodeKey"],
        )
    )

    out["Name"] = first_existing(
        df,
        [
            "Name",
            "Name_x",
            "Name_y",
        ],
    )

    out["EarningsType"] = "QUARTERLY"

    out["Rating"] = first_existing(
        df,
        [
            "Rating",
            "Rating_x",
            "Rating_y",
        ],
    )

    out["MinGrowth4"] = first_existing(
        df,
        ["MinGrowth4"],
    )

    out["MinProgressExcess"] = first_existing(
        df,
        ["MinProgressExcess"],
    )

    out["MinForecastGrowth4"] = pd.NA

    out["Revision"] = first_existing(
        df,
        [
            "Revision",
            "Revision_x",
            "Revision_y",
        ],
    )

    out["Next0930Pct"] = first_existing(
        df,
        ["Next0930Pct"],
    )

    out["NextHighPct"] = first_existing(
        df,
        ["NextHighPct"],
    )

    out["NextClosePct"] = first_existing(
        df,
        ["NextClosePct"],
    )

    out["WarningFlag"] = ""

    mask_warning = (
        pd.to_numeric(
            out["MinProgressExcess"],
            errors="coerce",
        )
        < -10.0
    )

    out.loc[
        mask_warning,
        "WarningFlag",
    ] = "PROGRESS_DELAY"

    out["HypothesisRank"] = "WATCH"

    strong = (
        out["Rating"]
        .astype(str)
        .eq("STRONG_GOOD")
    )

    balanced = (
        pd.to_numeric(
            out["MinGrowth4"],
            errors="coerce",
        )
        >= 20.0
    )

    out.loc[
        strong,
        "HypothesisRank",
    ] = "SG"

    out.loc[
        strong & balanced,
        "HypothesisRank",
    ] = "SG_BALANCED20"

    return out


def make_full_year(df):
    out = pd.DataFrame(
        index=df.index
    )

    out["DetectionDate"] = first_existing(
        df,
        ["DetectionDate"],
    )

    out["Code"] = clean_code(
        first_existing(
            df,
            ["Code", "CodeKey"],
        )
    )

    out["Name"] = first_existing(
        df,
        [
            "Name_FY",
            "Name",
            "Name_x",
            "Name_y",
        ],
    )

    out["EarningsType"] = "FULL_YEAR"

    out["Rating"] = first_existing(
        df,
        [
            "Rating_FY",
            "Rating",
            "Rating_x",
            "Rating_y",
        ],
    )

    out["MinGrowth4"] = pd.NA
    out["MinProgressExcess"] = pd.NA

    out["MinForecastGrowth4"] = first_existing(
        df,
        ["MinForecastGrowth4"],
    )

    out["Revision"] = first_existing(
        df,
        [
            "Revision_FY",
            "Revision",
            "Revision_x",
            "Revision_y",
        ],
    )

    out["Next0930Pct"] = first_existing(
        df,
        ["Next0930Pct"],
    )

    out["NextHighPct"] = first_existing(
        df,
        ["NextHighPct"],
    )

    out["NextClosePct"] = first_existing(
        df,
        ["NextClosePct"],
    )

    forecast = pd.to_numeric(
        out["MinForecastGrowth4"],
        errors="coerce",
    )

    out["WarningFlag"] = ""

    out.loc[
        forecast < 0,
        "WarningFlag",
    ] = "NEXT_FY_NEGATIVE"

    out["HypothesisRank"] = "WATCH"

    strong = (
        out["Rating"]
        .astype(str)
        .eq("STRONG_GOOD")
    )

    out.loc[
        strong,
        "HypothesisRank",
    ] = "SG"

    out.loc[
        strong & (forecast >= 0),
        "HypothesisRank",
    ] = "SG_NEXT_POSITIVE"

    out.loc[
        strong & (forecast >= 10),
        "HypothesisRank",
    ] = "SG_NEXT10"

    out.loc[
        strong & (forecast >= 20),
        "HypothesisRank",
    ] = "SG_NEXT20"

    return out


def main():
    if not PROGRESS_FILE.exists():
        raise SystemExit(
            f"Missing: {PROGRESS_FILE}"
        )

    if not FULL_YEAR_FILE.exists():
        raise SystemExit(
            f"Missing: {FULL_YEAR_FILE}"
        )

    q = pd.read_csv(
        PROGRESS_FILE,
        dtype={"Code": str},
    )

    fy = pd.read_csv(
        FULL_YEAR_FILE,
        dtype={"Code": str},
    )

    quarterly = make_quarterly(q)
    full_year = make_full_year(fy)

    unified = pd.concat(
        [
            quarterly,
            full_year,
        ],
        ignore_index=True,
    )

    unified["DetectionDate"] = pd.to_datetime(
        unified["DetectionDate"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    rank_order = {
        "SG_NEXT20": 1,
        "SG_NEXT10": 2,
        "SG_BALANCED20": 3,
        "SG_NEXT_POSITIVE": 4,
        "SG": 5,
        "WATCH": 6,
    }

    unified["_RankOrder"] = (
        unified["HypothesisRank"]
        .map(rank_order)
        .fillna(99)
    )

    unified = unified.sort_values(
        [
            "DetectionDate",
            "_RankOrder",
            "Code",
        ],
        ascending=[
            True,
            True,
            True,
        ],
    ).drop(
        columns=["_RankOrder"]
    )

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    unified.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    with pd.ExcelWriter(
        OUTPUT_XLSX,
        engine="openpyxl",
    ) as writer:
        unified.to_excel(
            writer,
            sheet_name="EarningsCatalyst",
            index=False,
        )

        ws = writer.book[
            "EarningsCatalyst"
        ]

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        widths = {
            "A": 14,
            "B": 10,
            "C": 24,
            "D": 14,
            "E": 16,
            "F": 14,
            "G": 18,
            "H": 20,
            "I": 14,
            "J": 20,
            "K": 22,
            "L": 14,
            "M": 14,
            "N": 14,
        }

        for col, width in widths.items():
            ws.column_dimensions[
                col
            ].width = width

    print("=" * 100)
    print("EARNINGS CATALYST UNIFIED")
    print("=" * 100)

    print(
        "Quarterly :",
        len(quarterly),
    )

    print(
        "Full year :",
        len(full_year),
    )

    print(
        "Total     :",
        len(unified),
    )

    print()
    print("Type distribution")
    print(
        unified[
            "EarningsType"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print("Hypothesis rank distribution")
    print(
        unified[
            "HypothesisRank"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print("Warning distribution")

    warning = unified[
        unified["WarningFlag"]
        .astype(str)
        .ne("")
    ]

    if warning.empty:
        print("None")
    else:
        print(
            warning[
                "WarningFlag"
            ]
            .value_counts()
            .to_string()
        )

    print()
    print("CSV   :", OUTPUT_CSV)
    print("Excel :", OUTPUT_XLSX)


if __name__ == "__main__":
    main()
