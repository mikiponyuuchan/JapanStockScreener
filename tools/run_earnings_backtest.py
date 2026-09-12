import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import holidays
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

CREATE_TOOL = (
    ROOT
    / "tools"
    / "create_earnings_catalyst_batch.py"
)

STRENGTH_TOOL = (
    ROOT
    / "tools"
    / "analyze_earnings_strength.py"
)

NEXT_DAY_TOOL = (
    ROOT
    / "tools"
    / "analyze_earnings_next_day.py"
)


def is_business_day(d, jp_holidays):
    return (
        d.weekday() < 5
        and d not in jp_holidays
    )


def get_business_days(
    end_date,
    count,
):
    years = list(
        range(
            end_date.year - 1,
            end_date.year + 1,
        )
    )

    jp_holidays = holidays.JP(
        years=years
    )

    days = []
    d = end_date

    while len(days) < count:
        if is_business_day(
            d,
            jp_holidays,
        ):
            days.append(d)

        d -= timedelta(days=1)

    days.reverse()

    return days


def run_tool(
    tool,
    target_date,
):
    command = [
        sys.executable,
        str(tool),
        "--date",
        target_date.isoformat(),
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
    )

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--end",
        default="2026-09-10",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    end_date = date.fromisoformat(
        args.end
    )

    days = get_business_days(
        end_date,
        args.days,
    )

    print(
        "=" * 76
    )
    print(
        "EARNINGS CATALYST BACKTEST"
    )
    print(
        "=" * 76
    )
    print(
        "Start :",
        days[0],
    )
    print(
        "End   :",
        days[-1],
    )
    print(
        "Days  :",
        len(days),
    )
    print()

    status_rows = []

    for number, target_date in enumerate(
        days,
        start=1,
    ):
        print()
        print(
            "#" * 76
        )
        print(
            f"[{number}/{len(days)}]",
            target_date,
        )
        print(
            "#" * 76
        )

        create_ok = run_tool(
            CREATE_TOOL,
            target_date,
        )

        if not create_ok:
            print(
                "CREATE ERROR"
            )

            status_rows.append(
                {
                    "Date":
                        target_date,
                    "Create":
                        "ERROR",
                    "Strength":
                        "-",
                    "NextDay":
                        "-",
                }
            )

            continue

        strength_ok = run_tool(
            STRENGTH_TOOL,
            target_date,
        )

        if not strength_ok:
            print(
                "STRENGTH ERROR"
            )

            status_rows.append(
                {
                    "Date":
                        target_date,
                    "Create":
                        "OK",
                    "Strength":
                        "ERROR",
                    "NextDay":
                        "-",
                }
            )

            continue

        next_ok = run_tool(
            NEXT_DAY_TOOL,
            target_date,
        )

        status_rows.append(
            {
                "Date":
                    target_date,
                "Create":
                    "OK",
                "Strength":
                    "OK",
                "NextDay":
                    (
                        "OK"
                        if next_ok
                        else "ERROR"
                    ),
            }
        )

    status = pd.DataFrame(
        status_rows
    )

    out_dir = (
        ROOT
        / "data"
        / "analysis"
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    status_path = (
        out_dir
        / "earnings_backtest_status.csv"
    )

    status.to_csv(
        status_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "=" * 76
    )
    print(
        "BACKTEST DOWNLOAD COMPLETE"
    )
    print(
        "=" * 76
    )

    print(
        status.to_string(
            index=False
        )
    )

    print()
    print(
        "Saved :",
        status_path,
    )


if __name__ == "__main__":
    main()
