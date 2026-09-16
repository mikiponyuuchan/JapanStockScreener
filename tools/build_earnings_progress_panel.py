from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "tools"),
)

from test_earnings_progress_parser import parse_pdf


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
    / "earnings_progress_panel.csv"
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

    work = df.copy()

    work[date_col] = (
        work[date_col]
        .astype(str)
        .str[:10]
    )

    work[code_col] = (
        work[code_col]
        .astype(str)
        .str.strip()
    )

    rows = []

    total = len(work)

    pdf_found = 0
    parsed = 0
    missing = 0
    failed = 0

    for i, row in work.iterrows():
        detection_date = row[date_col]
        code = row[code_col]

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
            "DetectionDate": detection_date,
            "Code": code,
        }

        if name_col is not None:
            out["Name"] = row.get(
                name_col,
            )

        if rating_col is not None:
            out["Rating"] = row.get(
                rating_col,
            )

        if not pdf.exists():
            out["ParseStatus"] = (
                "PDF_MISSING"
            )

            rows.append(out)

            missing += 1

        else:
            pdf_found += 1

            try:
                result = parse_pdf(
                    pdf
                )

                out.update(
                    {
                        "Quarter":
                            result.get(
                                "Quarter"
                            ),
                        "HasEBITDA":
                            result.get(
                                "HasEBITDA"
                            ),
                        "ActualOperating":
                            result.get(
                                "ActualOperating"
                            ),
                        "ForecastOperating":
                            result.get(
                                "ForecastOperating"
                            ),
                        "OperatingProgress":
                            result.get(
                                "OperatingProgress"
                            ),
                        "OperatingProgressExcess":
                            result.get(
                                "OperatingProgressExcess"
                            ),
                        "ActualNet":
                            result.get(
                                "ActualNet"
                            ),
                        "ForecastNet":
                            result.get(
                                "ForecastNet"
                            ),
                        "NetProgress":
                            result.get(
                                "NetProgress"
                            ),
                        "NetProgressExcess":
                            result.get(
                                "NetProgressExcess"
                            ),
                        "ActualRow":
                            result.get(
                                "ActualRow"
                            ),
                        "ForecastRow":
                            result.get(
                                "ForecastRow"
                            ),
                    }
                )

                required = [
                    out.get(
                        "Quarter"
                    ),
                    out.get(
                        "ActualOperating"
                    ),
                    out.get(
                        "ForecastOperating"
                    ),
                    out.get(
                        "OperatingProgress"
                    ),
                    out.get(
                        "ActualNet"
                    ),
                    out.get(
                        "ForecastNet"
                    ),
                    out.get(
                        "NetProgress"
                    ),
                ]

                if all(
                    x is not None
                    for x in required
                ):
                    out[
                        "ParseStatus"
                    ] = "OK"

                    parsed += 1

                else:
                    out[
                        "ParseStatus"
                    ] = "PARSE_FAIL"

                    failed += 1

            except Exception as e:
                out[
                    "ParseStatus"
                ] = "ERROR"

                out[
                    "ParseError"
                ] = str(e)

                failed += 1

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
        "EARNINGS PROGRESS BATCH"
    )
    print("=" * 80)

    print(
        f"Targets       : {total}"
    )
    print(
        f"PDF found     : {pdf_found}"
    )
    print(
        f"Parsed OK     : {parsed}"
    )
    print(
        f"PDF missing   : {missing}"
    )
    print(
        f"Parse failed  : {failed}"
    )

    if total:
        print(
            f"Success rate  : "
            f"{parsed / total * 100:.1f}%"
        )

    print()

    if (
        "Quarter"
        in result_df.columns
    ):
        print(
            "Quarter distribution"
        )

        print(
            result_df[
                result_df[
                    "ParseStatus"
                ] == "OK"
            ]["Quarter"]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

    print()

    if (
        "HasEBITDA"
        in result_df.columns
    ):
        ebitda_count = (
            result_df[
                "HasEBITDA"
            ]
            .astype(str)
            .eq("True")
            .sum()
        )

        print(
            f"EBITDA format : "
            f"{ebitda_count}"
        )

    print()
    print(
        "Status distribution"
    )

    print(
        result_df[
            "ParseStatus"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    bad = result_df[
        result_df[
            "ParseStatus"
        ] != "OK"
    ]

    if not bad.empty:
        print()
        print(
            "=" * 80
        )
        print(
            "FAILED CASES"
        )
        print(
            "=" * 80
        )

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
            if c in bad.columns
        ]

        print(
            bad[cols]
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
