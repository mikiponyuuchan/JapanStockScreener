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
    make_p5_candidates,
)

from services.tracking_service import (
    load_tracking,
    update_tracking_results,
    record_initial_move,
)

from services.p5_tracking_service import (
    load_p5_tracking,
    record_p5_candidates,
    update_p5_tracking,
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

    p5_candidates = (
        make_p5_candidates(
            df
        )
    )

    print(
        "Initial TOP20 :",
        len(initial_move_top20),
    )

    print(
        "P5 candidates :",
        len(p5_candidates),
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
    # P5 tracking
    # ======================================================

    print()
    print("[P5 tracking]")

    try:

        p5_tracking_df = (
            load_p5_tracking()
        )

        p5_tracking_df = (
            record_p5_candidates(
                p5_candidates
            )
        )

        p5_tracking_df = (
            update_p5_tracking(
                p5_tracking_df
            )
        )

        print(
            "P5 tracking rows :",
            len(p5_tracking_df),
        )

    except Exception as e:

        print(
            "P5 tracking ERROR :",
            e,
        )

    # ======================================================
    # J1 detection
    # ======================================================

    print()
    print("[J1 detection]")

    j1_detect_ok = False

    try:

        subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools"
                    / "validate_j_type.py"
                ),
            ],
            cwd=ROOT,
            check=True,
        )

        j1_detect_ok = True

        print(
            "J1 detection : complete"
        )

    except Exception as e:

        print(
            "J1 detection ERROR :",
            e,
        )

    # ======================================================
    # J1 confirmed daily tracking
    # ======================================================

    print()
    print("[J1 confirmed tracking]")

    try:

        subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools"
                    / "update_j_type_tracking.py"
                ),
            ],
            cwd=ROOT,
            check=True,
        )

        print(
            "J1 confirmed tracking : complete"
        )

    except Exception as e:

        print(
            "J1 confirmed tracking ERROR :",
            e,
        )

    print()
    print("=" * 60)
    print("After-close update complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
