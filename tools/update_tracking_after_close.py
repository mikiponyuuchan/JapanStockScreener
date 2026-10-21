import sys
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from services.result_writer import (
    make_initial_move_top20,
)

from services.jpx_risk_filter import (
    build_jpx_risk_list,
)

from services.tracking_service import (
    load_tracking,
    update_tracking_results,
    record_initial_move,
)


RESULT_DIR = ROOT / "results"


def main():

    now = datetime.now()

    print("=" * 60)
    print("After Close Tracking Update")
    print("=" * 60)

    print(
        "Run time :",
        now.strftime("%Y-%m-%d %H:%M:%S"),
    )

    # --------------------------------
    # Safety guard
    # --------------------------------

    if now.weekday() >= 5:
        print("SKIP : weekend")
        return

    if (
        now.hour < 15
        or (
            now.hour == 15
            and now.minute < 30
        )
    ):
        print("SKIP : before 15:30")
        return

    today = now.strftime("%Y-%m-%d")

    result_file = (
        RESULT_DIR
        / f"{today}_stock_result.csv"
    )

    if not result_file.exists():
        raise RuntimeError(
            "Today's stock result not found : "
            f"{result_file}"
        )

    df = pd.read_csv(
        result_file,
        encoding="utf-8-sig",
    )

    if df.empty:
        raise RuntimeError(
            "Today's stock result is empty"
        )

    print()
    print(
        "Stock result rows :",
        len(df),
    )

    # ======================================================
    # Rebuild today's candidates
    # ======================================================

    initial_move_top20 = (
        make_initial_move_top20(
            df
        )
    )

    print(
        "Initial TOP20 :",
        len(initial_move_top20),
    )

    # ======================================================
    # Initial move tracking
    # ======================================================

    print()
    print("[Initial tracking]")

    try:

        tracking_df = load_tracking()

        tracking_df = (
            update_tracking_results(
                tracking_df
            )
        )

        tracking_df = (
            record_initial_move(
                initial_move_top20
            )
        )

        print(
            "Initial tracking rows :",
            len(tracking_df),
        )

    except Exception as e:

        print(
            "Initial tracking ERROR :",
            e,
        )

    # ======================================================
    # J1 / SSR validation finished.
    # Historical scripts and tracking CSVs are preserved.
    # New detection, tracking and trade plans are disabled.
    print()
    print("[J1 / SSR] DISABLED - validation finished")

    # ======================================================
    # Intraday Strategy H1 result update
    # ======================================================

    print()
    print("[Intraday Strategy H1]")

    try:

        subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools"
                    / "update_intraday_strategy_h1.py"
                ),
            ],
            cwd=ROOT,
            check=True,
        )

        print(
            "Intraday Strategy H1 : complete"
        )

    except Exception as e:

        print(
            "Intraday Strategy H1 ERROR :",
            e,
        )

    # ======================================================
    # ======================================================
    # Intraday Strategy H1 LOW-CxV result update
    # ======================================================

    print()
    print("[Intraday Strategy H1 LOW-CxV]")

    try:
        subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools"
                    / "update_intraday_strategy_h1_low_cxv.py"
                ),
            ],
            cwd=ROOT,
            check=True,
        )

        print("Intraday Strategy H1 LOW-CxV : complete")

    except Exception as e:
        print("Intraday Strategy H1 LOW-CxV ERROR :", e)

    # ======================================================
    # Intraday Strategy H1-Early20
    # Validation finished. Keep historical updater/data
    # for reference and rollback only.
    # ======================================================

    print()
    print(
        "[Intraday Strategy H1-Early20] "
        "DISABLED - validation finished"
    )

    # ======================================================
    # Morning baseline for next trading day
    # ======================================================

    print()
    print("[Morning Baseline]")

    try:

        subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools"
                    / "update_morning_baseline_after_close.py"
                ),
            ],
            cwd=ROOT,
            check=True,
        )

        print(
            "Morning Baseline : complete"
        )

    except Exception as e:

        print(
            "Morning Baseline ERROR :",
            e,
        )

    print()
    print("=" * 60)
    print("After-close update complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
