import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RESULTS = ROOT / "results"
ANALYSIS = ROOT / "data" / "analysis"


def default_target_date():
    now = datetime.now()

    if (
        now.weekday() < 5
        and (now.hour, now.minute) >= (15, 30)
    ):
        target = now.date()
    else:
        target = now.date() - timedelta(days=1)

        while target.weekday() >= 5:
            target -= timedelta(days=1)

    return target.strftime("%Y-%m-%d")


def run_step(title, command):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    result = subprocess.run(
        command,
        cwd=ROOT,
    )

    if result.returncode != 0:
        raise SystemExit(
            f"FAILED: {title}"
        )


def require_file(path, label):
    if not path.exists():
        raise SystemExit(
            f"Missing {label}: {path}"
        )


def remove_old(path):
    if path.exists():
        path.unlink()
        print(
            "Removed old output:",
            path,
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        default=None,
        help="Target date YYYY-MM-DD",
    )

    args = parser.parse_args()

    target_date = (
        args.date
        if args.date
        else default_target_date()
    )

    morning_file = (
        RESULTS
        / f"{target_date}_morning_catalyst.xlsx"
    )

    earnings_file = (
        RESULTS
        / f"{target_date}_earnings_catalyst.xlsx"
    )

    ver1_file = (
        ANALYSIS
        / f"{target_date}_earnings_catalyst_ver1.csv"
    )

    print("=" * 80)
    print("EVENING CATALYST")
    print("=" * 80)
    print(
        "Target date :",
        target_date,
    )

    # --------------------------------------------------
    # 1. General disclosure catalysts
    # --------------------------------------------------
    remove_old(
        morning_file
    )

    run_step(
        "1/4 GENERAL CATALYST",
        [
            sys.executable,
            str(
                TOOLS
                / "create_morning_catalyst.py"
            ),
            "--date",
            target_date,
        ],
    )

    require_file(
        morning_file,
        "general catalyst output",
    )

    # --------------------------------------------------
    # 2. Earnings PDF download and base analysis
    # --------------------------------------------------
    remove_old(
        earnings_file
    )

    run_step(
        "2/4 EARNINGS PDF ANALYSIS",
        [
            sys.executable,
            str(
                TOOLS
                / "create_earnings_catalyst_batch.py"
            ),
            "--date",
            target_date,
        ],
    )

    require_file(
        earnings_file,
        "earnings catalyst output",
    )

    # --------------------------------------------------
    # 3. Earnings Catalyst Ver1
    # --------------------------------------------------
    remove_old(
        ver1_file
    )

    run_step(
        "3/4 EARNINGS CATALYST VER1",
        [
            sys.executable,
            str(
                TOOLS
                / "create_earnings_catalyst_ver1.py"
            ),
            "--date",
            target_date,
        ],
    )

    require_file(
        ver1_file,
        "earnings catalyst Ver1 output",
    )

    # --------------------------------------------------
    # 4. Daily TOP3
    # --------------------------------------------------
    run_step(
        "4/4 EARNINGS TOP3",
        [
            sys.executable,
            str(
                TOOLS
                / "show_earnings_catalyst_top3.py"
            ),
            "--date",
            target_date,
        ],
    )

    print()
    print("=" * 80)
    print("EVENING CATALYST COMPLETED")
    print("=" * 80)
    print(
        "Date     :",
        target_date,
    )
    print(
        "General  :",
        morning_file,
    )
    print(
        "Earnings :",
        earnings_file,
    )
    print(
        "Ver1     :",
        ver1_file,
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
