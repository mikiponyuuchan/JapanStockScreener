import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

COL_CODE = "\u30b3\u30fc\u30c9"
COL_NAME = "\u9285\u67c4\u540d"
COL_TIME = "\u767a\u8868\u65e5\u6642"
COL_TYPE = "\u6750\u6599\u5206\u985e"
COL_IMPORTANCE = "\u91cd\u8981\u5ea6"
COL_FOCUS = "\u7fcc\u671d\u6ce8\u76ee"
COL_AVOID = "\u56de\u907f\u30d5\u30e9\u30b0"


def latest_file():
    files = sorted(
        RESULTS.glob(
            "*_morning_catalyst.xlsx"
        )
    )

    if not files:
        raise SystemExit(
            "Morning catalyst Excel not found."
        )

    return files[-1]


def clean_text(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


def unique_join(values, sep=" / "):
    result = []

    for value in values:
        text = clean_text(value)

        if text and text not in result:
            result.append(text)

    return sep.join(result)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        default=None,
        help="YYYY-MM-DD",
    )

    args = parser.parse_args()

    if args.date:
        path = (
            RESULTS
            / f"{args.date}_morning_catalyst.xlsx"
        )
    else:
        path = latest_file()

    if not path.exists():
        raise SystemExit(
            f"Missing: {path}"
        )

    df = pd.read_excel(
        path,
        dtype={
            COL_CODE: str,
        },
    )

    if df.empty:
        print()
        print("=" * 72)
        print(" GENERAL CATALYST - FOCUS")
        print("=" * 72)
        print("No catalyst candidates.")
        print("=" * 72)
        return

    rows = []

    for code, group in df.groupby(
        COL_CODE,
        sort=False,
    ):
        name = clean_text(
            group.iloc[0][COL_NAME]
        )

        focus_values = [
            clean_text(x)
            for x in group[COL_FOCUS]
        ]

        avoid_values = [
            clean_text(x)
            for x in group[COL_AVOID]
        ]

        if (
            "\u56de\u907f" in focus_values
            or "\u25cb" in avoid_values
        ):
            category = "AVOID"
            order = 3

        elif "\u9ad8" in focus_values:
            category = "HIGH"
            order = 1

        else:
            category = "WATCH"
            order = 2

        material = unique_join(
            group[COL_TYPE]
        )

        importance = unique_join(
            group[COL_IMPORTANCE],
            sep=" ",
        )

        times = pd.to_datetime(
            group[COL_TIME],
            errors="coerce",
        )

        latest_time = times.max()

        rows.append(
            {
                "Code": clean_text(code),
                "Name": name,
                "Category": category,
                "Order": order,
                "Material": material,
                "Importance": importance,
                "Time": latest_time,
            }
        )

    out = pd.DataFrame(rows)

    out = out.sort_values(
        [
            "Order",
            "Time",
            "Code",
        ],
        ascending=[
            True,
            False,
            True,
        ],
        na_position="last",
    )

    date_text = path.name[
        :10
    ]

    print()
    print("=" * 72)
    print(" GENERAL CATALYST - FOCUS")
    print("=" * 72)
    print(
        " Date :",
        date_text,
    )

    for category in [
        "HIGH",
        "WATCH",
        "AVOID",
    ]:
        part = out[
            out["Category"].eq(
                category
            )
        ]

        print()
        print(
            f"[{category}]"
        )

        if part.empty:
            print("  None")
            continue

        for _, row in part.iterrows():
            print(
                f"{row['Code']}  "
                f"{row['Name']}"
            )

            detail = (
                row["Material"]
            )

            if row["Importance"]:
                detail += (
                    "  "
                    + row["Importance"]
                )

            print(
                f"   {detail}"
            )

    print()
    print("=" * 72)
    print(
        "HIGH  :",
        int(
            (
                out["Category"]
                == "HIGH"
            ).sum()
        ),
    )
    print(
        "WATCH :",
        int(
            (
                out["Category"]
                == "WATCH"
            ).sum()
        ),
    )
    print(
        "AVOID :",
        int(
            (
                out["Category"]
                == "AVOID"
            ).sum()
        ),
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
