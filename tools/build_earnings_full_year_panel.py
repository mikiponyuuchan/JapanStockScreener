import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "tools"),
)

from earnings_full_year_parser_v1 import parse_pdf


PROGRESS = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_progress_panel_v2.csv"
)

PDF_ROOT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_pdf"
)

OUTPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_full_year_panel.csv"
)


def find_pdf(
    detection_date,
    code,
):
    date_key = (
        str(detection_date)
        .replace("-", "")
    )

    direct = (
        PDF_ROOT
        / date_key
        / f"{code}.pdf"
    )

    if direct.exists():
        return direct

    matches = list(
        PDF_ROOT.rglob(
            f"{code}.pdf"
        )
    )

    if not matches:
        return None

    for path in matches:
        if date_key in str(path):
            return path

    return matches[0]


def main():
    src = pd.read_csv(
        PROGRESS,
        dtype={
            "Code": str,
        },
    )

    fy = src[
        src["ParseStatus"]
        .eq("FULL_YEAR")
    ].copy()

    print("=" * 100)
    print("EARNINGS FULL-YEAR BATCH")
    print("=" * 100)
    print(
        "Targets :",
        len(fy),
    )

    rows = []

    for _, row in fy.iterrows():
        code = str(
            row["Code"]
        ).strip()

        detection_date = str(
            row["DetectionDate"]
        )

        pdf = find_pdf(
            detection_date,
            code,
        )

        base = {
            "DetectionDate": detection_date,
            "Code": code,
            "Name": row.get(
                "Name",
                "",
            ),
            "Rating": row.get(
                "Rating",
                "",
            ),
        }

        if pdf is None:
            base[
                "ParseStatus"
            ] = "PDF_NOT_FOUND"

            rows.append(
                base
            )
            continue

        try:
            parsed = parse_pdf(
                pdf
            )

            base.update(
                parsed
            )

            base[
                "PdfPath"
            ] = str(pdf)

        except Exception as exc:
            base[
                "ParseStatus"
            ] = "ERROR"

            base[
                "Error"
            ] = repr(exc)

        rows.append(
            base
        )

    out = pd.DataFrame(
        rows
    )

    out.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("Status distribution")

    if (
        not out.empty
        and "ParseStatus"
        in out.columns
    ):
        print(
            out[
                "ParseStatus"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

    print()
    print("=" * 100)
    print("NON-OK CASES")
    print("=" * 100)

    if (
        not out.empty
        and "ParseStatus"
        in out.columns
    ):
        bad = out[
            ~out["ParseStatus"]
            .eq("OK")
        ].copy()

        if bad.empty:
            print(
                "None"
            )
        else:
            cols = [
                "DetectionDate",
                "Code",
                "Name",
                "Rating",
                "ParseStatus",
                "ActualRow",
                "ForecastRow",
                "Error",
            ]

            cols = [
                c
                for c in cols
                if c in bad.columns
            ]

            print(
                bad[
                    cols
                ]
                .to_string(
                    index=False
                )
            )

    print()
    print("=" * 100)
    print("OK SAMPLE")
    print("=" * 100)

    if (
        not out.empty
        and "ParseStatus"
        in out.columns
    ):
        ok = out[
            out["ParseStatus"]
            .eq("OK")
        ].copy()

        cols = [
            "DetectionDate",
            "Code",
            "Name",
            "Rating",
            "ForecastSalesGrowth",
            "ForecastOperatingGrowth",
            "ForecastOrdinaryGrowth",
            "ForecastNetGrowth",
            "MinForecastGrowth4",
        ]

        cols = [
            c
            for c in cols
            if c in ok.columns
        ]

        print(
            ok[
                cols
            ]
            .head(30)
            .to_string(
                index=False
            )
        )

    print()
    print(
        "Saved :",
        OUTPUT,
    )


if __name__ == "__main__":
    main()
