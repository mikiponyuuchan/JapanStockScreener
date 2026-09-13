from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = (
    ROOT
    / "data"
    / "analysis"
)

FILE_PATTERN = "*_earnings_catalyst_ver1.csv"


TOP_N = 3

RANK_MAP = {
    "SG_NEXT20": 1,
    "SG_NEXT10": 2,
    "SG_BALANCED20": 3,
    "SG_NEXT_POSITIVE": 4,
    "SG": 5,
}


def find_first_column(df, candidates):
    for name in candidates:
        if name in df.columns:
            return name
    return None


def format_value(value, digits=1, suffix=""):
    if pd.isna(value):
        return "-"

    try:
        number = float(value)
        return f"{number:.{digits}f}{suffix}"
    except Exception:
        return str(value)


def main():
    files = sorted(
        INPUT_DIR.glob(FILE_PATTERN)
    )

    if not files:
        print(
            "Daily earnings catalyst CSV not found."
        )
        return

    input_csv = files[-1]

    print(
        "Source :",
        input_csv.name,
    )

    df = pd.read_csv(
        input_csv,
        dtype=str,
    )

    if df.empty:
        print(
            "Unified earnings catalyst CSV is empty."
        )
        return

    rank_col = find_first_column(
        df,
        [
            "HypothesisRank",
            "Hypothesis",
            "Rank",
        ],
    )

    if rank_col is None:
        print(
            "Hypothesis rank column not found."
        )
        print(
            "Columns:",
            list(df.columns),
        )
        return

    df["_Priority"] = (
        df[rank_col]
        .map(RANK_MAP)
    )

    work = df[
        df["_Priority"].notna()
    ].copy()

    if work.empty:
        print("=" * 72)
        print(" EARNINGS CATALYST Ver1 - TOP3")
        print("=" * 72)
        print(" No SG candidate.")
        print("=" * 72)
        return

    code_col = find_first_column(
        work,
        [
            "Code",
            "code",
        ],
    )

    name_col = find_first_column(
        work,
        [
            "Name",
            "CompanyName",
            "name",
        ],
    )

    date_col = find_first_column(
        work,
        [
            "DisclosureDate",
            "Date",
            "DetectionDate",
            "TargetDate",
        ],
    )

    warning_col = find_first_column(
        work,
        [
            "WarningFlag",
            "Warning",
        ],
    )

    min_growth_col = find_first_column(
        work,
        [
            "MinGrowth4",
            "MinForecastGrowth4",
        ],
    )

    progress_col = find_first_column(
        work,
        [
            "MinProgressExcess",
            "ProgressExcess",
        ],
    )

    score_col = find_first_column(
        work,
        [
            "ScoreV2",
            "StrengthScore",
            "Score",
        ],
    )

    # ======================================================
    # Use latest disclosure date only
    # ======================================================

    if date_col is not None:
        work["_DateParsed"] = pd.to_datetime(
            work[date_col],
            errors="coerce",
        )

        valid_dates = work["_DateParsed"].dropna()

        if not valid_dates.empty:
            latest_date = valid_dates.max()

            work = work[
                work["_DateParsed"] == latest_date
            ].copy()

    # Optional tie-breakers only.
    sort_cols = ["_Priority"]
    ascending = [True]

    if min_growth_col is not None:
        work["_MinGrowthNum"] = pd.to_numeric(
            work[min_growth_col],
            errors="coerce",
        )
        sort_cols.append("_MinGrowthNum")
        ascending.append(False)

    if score_col is not None:
        work["_ScoreNum"] = pd.to_numeric(
            work[score_col],
            errors="coerce",
        )
        sort_cols.append("_ScoreNum")
        ascending.append(False)

    work = work.sort_values(
        sort_cols,
        ascending=ascending,
        na_position="last",
    )

    top = work.head(TOP_N).copy()

    print()
    print("=" * 72)
    print(" *** EARNINGS CATALYST Ver1 - TOP3 ***")
    print("=" * 72)

    if date_col is not None:
        dates = (
            top[date_col]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if dates:
            print(
                " Date :",
                ", ".join(dates),
            )
            print("-" * 72)

    for number, (_, row) in enumerate(
        top.iterrows(),
        start=1,
    ):
        code = (
            row[code_col]
            if code_col is not None
            else "-"
        )

        name = (
            row[name_col]
            if name_col is not None
            else "-"
        )

        rank = row[rank_col]

        warning = (
            row[warning_col]
            if warning_col is not None
            and pd.notna(row[warning_col])
            and str(row[warning_col]).strip()
            else "-"
        )

        print()
        print(
            f"{number}. {code}  {name}"
        )
        print(
            f"   Rank    : {rank}"
        )

        if min_growth_col is not None:
            print(
                "   MinGrowth:",
                format_value(
                    row[min_growth_col],
                    digits=1,
                    suffix="%",
                ),
            )

        if progress_col is not None:
            print(
                "   Progress :",
                format_value(
                    row[progress_col],
                    digits=1,
                    suffix=" pt",
                ),
            )

        if score_col is not None:
            print(
                "   Score    :",
                format_value(
                    row[score_col],
                    digits=1,
                ),
            )

        print(
            f"   Warning  : {warning}"
        )

    print()
    print("=" * 72)
    print(
        " Candidates shown :",
        len(top),
    )
    print(
        " Eligible SG rows :",
        len(work),
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
