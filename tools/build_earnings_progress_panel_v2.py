from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "tools"),
)

from earnings_progress_parser_v2 import parse_pdf


INPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_backtest_preprice.csv"
)

OUTPUT = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_progress_panel_v2.csv"
)


def get_col(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col

    return None


def main():
    df = pd.read_csv(
        INPUT,
        dtype=str,
    )

    date_col = get_col(
        df,
        [
            "DetectionDate",
            "Date",
        ],
    )

    code_col = get_col(
        df,
        [
            "Code",
            "\u30b3\u30fc\u30c9",
        ],
    )

    name_col = get_col(
        df,
        [
            "Name",
            "\u9298\u67c4\u540d",
        ],
    )

    rating_col = get_col(
        df,
        [
            "Rating",
            "\u6c7a\u7b97\u8a55\u4fa1",
        ],
    )

    if date_col is None:
        raise SystemExit(
            "DetectionDate column not found"
        )

    if code_col is None:
        raise SystemExit(
            "Code column not found"
        )

    rows = []

    total = len(df)

    for i, row in df.iterrows():
        detection_date = str(
            row[date_col]
        )[:10]

        code = str(
            row[code_col]
        ).strip()

        date_dir = detection_date.replace(
            "-",
            "",
        )

        pdf = (
            ROOT
            / "data"
            / "analysis"
            / "earnings_pdf"
            / date_dir
            / f"{code}.pdf"
        )

        out = {
            "DetectionDate":
                detection_date,
            "Code":
                code,
        }

        if name_col is not None:
            out["Name"] = row.get(
                name_col
            )

        if rating_col is not None:
            out["Rating"] = row.get(
                rating_col
            )

        if not pdf.exists():
            out[
                "ParseStatus"
            ] = "PDF_MISSING"

        else:
            try:
                result = parse_pdf(
                    pdf
                )

                out.update(
                    result
                )

            except Exception as e:
                out[
                    "ParseStatus"
                ] = "ERROR"

                out[
                    "ParseError"
                ] = str(e)

        rows.append(out)

        done = i + 1

        if (
            done % 20 == 0
            or done == total
        ):
            print(
                f"{done} / {total}"
            )

    result_df = pd.DataFrame(
        rows
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 80)
    print(
        "EARNINGS PROGRESS V2 BATCH"
    )
    print("=" * 80)

    print(
        f"Targets : {total}"
    )

    print()
    print(
        "Status distribution"
    )

    status = (
        result_df[
            "ParseStatus"
        ]
        .value_counts(
            dropna=False
        )
    )

    print(
        status.to_string()
    )

    print()

    quarterly = result_df[
        result_df[
            "Quarter"
        ].isin(
            [
                "Q1",
                "Q2",
                "Q3",
            ]
        )
    ]

    print(
        "Quarterly decisions :",
        len(quarterly),
    )

    if len(quarterly):
        ok_count = (
            quarterly[
                "ParseStatus"
            ]
            .eq("OK")
            .sum()
        )

        print(
            "Quarterly OK        :",
            ok_count,
        )

        print(
            "Quarterly OK rate   : "
            f"{ok_count / len(quarterly) * 100:.1f}%"
        )

    print()

    if "Quarter" in result_df.columns:
        print(
            "Quarter distribution"
        )

        print(
            result_df[
                "Quarter"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

    print()

    non_ok = result_df[
        result_df[
            "ParseStatus"
        ] != "OK"
    ]

    if not non_ok.empty:
        print("=" * 80)
        print(
            "NON-OK CASES"
        )
        print("=" * 80)

        cols = [
            c
            for c in [
                "DetectionDate",
                "Code",
                "Name",
                "Rating",
                "ParseStatus",
                "Quarter",
                "ActualRow",
                "ForecastRow",
                "ParseError",
            ]
            if c in non_ok.columns
        ]

        print(
            non_ok[
                cols
            ].to_string(
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
