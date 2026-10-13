import argparse
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "intraday"))

from rss_ssr_reader import (
    load_ssr_snapshot,
    read_ssr_rows,
)
from watch_short_sale_trigger_rakuten import (
    find_latest_trigger_file,
    read_trigger_file,
    save_ssr_ver2_rows,
    print_ssr_ver2_candidate,
    scan_row,
    evaluate_ssr_ver2,
)

from rss_live_board import (
    add_candidate,
)


SSR_INTERVAL = 30

EARLY_START = (9, 20)
EARLY_END = (9, 25)

H1_START = (9, 30)
H1_END = (9, 35)

SSR_END = (9, 30)


def today_at(hour, minute):
    now = datetime.now()

    return now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )


def wait_until(hour, minute):
    target = today_at(
        hour,
        minute,
    )

    now = datetime.now()

    if now >= target:
        return

    print(
        f"Waiting for "
        f"{hour:02d}:{minute:02d} ..."
    )

    while True:
        now = datetime.now()

        if now >= target:
            return

        remaining = (
            target - now
        ).total_seconds()

        time.sleep(
            min(
                max(remaining, 0.5),
                10.0,
            )
        )


def in_window(
    start_hour,
    start_minute,
    end_hour,
    end_minute,
):
    now = datetime.now()

    start = today_at(
        start_hour,
        start_minute,
    )

    end = today_at(
        end_hour,
        end_minute,
    )

    return start <= now <= end


def run_script(script_name):
    print()
    print("=" * 72)
    print(
        " RUN :",
        script_name,
    )
    print("=" * 72)

    result = subprocess.run(
        [
            sys.executable,
            f"tools/{script_name}",
        ],
        check=False,
    )

    print(
        "RETURN CODE :",
        result.returncode,
    )

    return result.returncode


def print_ssr_candidate(row):
    print()
    print("=" * 72)
    print(" SSR-Ver1 CANDIDATE")
    print("=" * 72)

    print(
        f'{row["Code"]} '
        f'{row["Name"]}'
    )

    print(
        f'Open     : '
        f'{row["Open"]:.0f}'
    )

    print(
        f'OpenTime : '
        f'{row["OpenTime"]}'
    )

    print(
        f'Gap      : '
        f'{row["GapPct"]:+.2f}%'
    )

    print("=" * 72)
    print()


def ssr_worker(
    stop_event,
):
    print()
    print("=" * 72)
    print(
        " SSR WATCH START - Rakuten RSS"
    )
    print("=" * 72)

    path = find_latest_trigger_file()

    if path is None:
        print(
            "SSR : No JPX trigger file."
        )
        return

    trigger = read_trigger_file(
        path
    )

    if trigger.empty:
        print(
            "SSR : No trigger rows."
        )
        return

    watch = {}

    for _, row in trigger.iterrows():
        code = str(
            row["Code"]
        )

        if code.endswith(".0"):
            code = code[:-2]

        watch[code] = {
            "TriggerDate":
                row.get(
                    "TriggerDate",
                    "",
                ),
            "TriggerTime":
                row.get(
                    "TriggerTime",
                    "",
                ),
            "Code":
                code,
            "Name":
                row["Name"],
        }

    unresolved = set(
        watch.keys()
    )

    completed = {}

    ssr_codes = set()

    # SSR-Ver1 stocks remain under observation
    # until 09:30 for independent SSR-Ver2
    # forward validation.
    ver2_watch = set()

    cutoff = today_at(
        SSR_END[0],
        SSR_END[1],
    )

    print(
        "Trigger file :",
        path.name,
    )

    print(
        "Trigger count:",
        len(watch),
    )

    print()

    # Load trigger codes into the dedicated
    # Rakuten RSS SSR workbook once.
    try:
        initial_rows = load_ssr_snapshot(
            list(watch.keys()),
            wait_seconds=5.0,
        )

        print(
            "Rakuten RSS SSR rows :",
            len(initial_rows),
            "/",
            len(watch),
        )

    except Exception as exc:
        print(
            "SSR Rakuten RSS startup error :",
            exc,
        )
        return

    while (
        not stop_event.is_set()
        and datetime.now() < cutoff
        and (
            unresolved
            or ver2_watch
        )
    ):
        rss_errors = 0

        try:
            rss_rows = read_ssr_rows()

        except Exception as exc:
            print(
                "SSR Rakuten RSS read error :",
                exc,
            )

            stop_event.wait(
                SSR_INTERVAL
            )

            continue

        rss_map = {
            str(row["Code"]):
                row
            for row in rss_rows
        }

        for code in list(
            unresolved
        ):
            if (
                stop_event.is_set()
                or datetime.now() >= cutoff
            ):
                break

            item = watch[
                code
            ]

            rss_row = rss_map.get(
                code
            )

            if rss_row is None:
                rss_errors += 1
                continue

            try:
                row = scan_row(
                    rss_row
                )

            except Exception as exc:
                rss_errors += 1

                print(
                    f"SSR RSS ERROR "
                    f"{code}: {exc}"
                )

                continue

            status = row[
                "Status"
            ]

            if status == "WAITING_OPEN":
                continue

            completed[
                code
            ] = row

            unresolved.discard(
                code
            )

            if (
                status == "SSR-Ver1"
                and code not in ssr_codes
            ):
                ssr_codes.add(
                    code
                )

                ver2_watch.add(
                    code
                )

                print_ssr_candidate(
                    row
                )

                try:
                    add_candidate(
                        code,
                        "SSR-Ver1",
                    )

                except Exception as exc:
                    print(
                        "SSR-Ver1 RSS board update skipped : "
                        f"{exc}"
                    )

        print(
            datetime.now().strftime(
                "%H:%M:%S"
            ),
            "| SSR:",
            len(ssr_codes),
            "| Waiting:",
            len(unresolved),
            "| RSS errors:",
            rss_errors,
        )

        if datetime.now() >= cutoff:
            break

        if (
            not unresolved
            and not ver2_watch
        ):
            break

        remaining = (
            cutoff - datetime.now()
        ).total_seconds()

        if remaining <= 0:
            break

        stop_event.wait(
            min(
                SSR_INTERVAL,
                remaining,
            )
        )

    # ==================================================
    # SSR-Ver2 09:30 forward evaluation
    # ==================================================

    ver2_rows = []

    if ver2_watch:
        print()
        print("=" * 72)
        print(
            " SSR-Ver2 09:30 EVALUATION - Rakuten RSS"
        )
        print("=" * 72)

        try:
            final_rows = read_ssr_rows()

            final_map = {
                str(row["Code"]):
                    row
                for row in final_rows
            }

        except Exception as exc:
            print(
                "SSR-Ver2 RSS read error :",
                exc,
            )
            final_map = {}

        for code in sorted(
            ver2_watch
        ):
            item = watch[
                code
            ]

            rss_row = final_map.get(
                code
            )

            if rss_row is None:
                print(
                    f"SSR-Ver2 NO DATA : "
                    f"{code}"
                )
                continue

            # Preserve JPX trigger metadata in the
            # existing SSR-Ver2 CSV format.
            rss_row = dict(
                rss_row
            )

            rss_row[
                "TriggerDate"
            ] = item.get(
                "TriggerDate",
                "",
            )

            try:
                ver2_row = evaluate_ssr_ver2(
                    rss_row,
                    item.get(
                        "TriggerTime",
                        "",
                    ),
                )

            except Exception as exc:
                print(
                    f"SSR-Ver2 RSS ERROR "
                    f"{code}: {exc}"
                )
                continue

            if ver2_row is None:
                print(
                    f"SSR-Ver2 NO DATA : "
                    f"{code}"
                )
                continue

            ver2_rows.append(
                ver2_row
            )

            if ver2_row[
                "Ver2Candidate"
            ]:
                print_ssr_ver2_candidate(
                    ver2_row
                )

                try:
                    add_candidate(
                        code,
                        "SSR-Ver2",
                    )

                except Exception as exc:
                    print(
                        "SSR-Ver2 RSS board update skipped : "
                        f"{exc}"
                    )

            else:
                print(
                    f'SSR-Ver2 FILTERED : '
                    f'{code} '
                    f'Rebound='
                    f'{ver2_row["ReboundLowTo0930Pct"]:+.2f}% '
                    f'LowAge='
                    f'{ver2_row["MinutesSinceLow"]:.1f}m'
                )

        save_ssr_ver2_rows(
            ver2_rows
        )

    else:
        print()
        print(
            "SSR-Ver2 : "
            "No SSR-Ver1 stocks to evaluate."
        )

    print()
    print("=" * 72)
    print(
        " SSR WATCH SUMMARY"
    )
    print("=" * 72)

    if ssr_codes:
        rows = [
            completed[code]
            for code in ssr_codes
            if code in completed
        ]

        rows = sorted(
            rows,
            key=lambda x: x["GapPct"],
        )

        for row in rows:
            print(
                f'{row["Code"]} '
                f'{row["Name"]} '
                f'Open={row["Open"]:.0f} '
                f'Time={row["OpenTime"]} '
                f'Gap={row["GapPct"]:+.2f}%'
            )

    else:
        print(
            "No SSR-Ver1 candidates."
        )

    print(
        "SSR candidates :",
        len(ssr_codes),
    )

    print(
        "Waiting open   :",
        len(unresolved),
    )

    print("=" * 72)

def run_early20():
    if not in_window(
        EARLY_START[0],
        EARLY_START[1],
        EARLY_END[0],
        EARLY_END[1],
    ):
        print()
        print(
            "H1-Early20 : SKIPPED "
            "- outside 09:20-09:25"
        )
        return

    rc = run_script(
        "run_morning_screener.py"
    )

    if rc != 0:
        print(
            "H1-Early20 : "
            "morning screener failed."
        )
        return

    run_script(
        "create_intraday_strategy_h1_early20.py"
    )


def run_h1():
    if not in_window(
        H1_START[0],
        H1_START[1],
        H1_END[0],
        H1_END[1],
    ):
        print()
        print(
            "H1 : SKIPPED "
            "- outside 09:30-09:35"
        )
        return

    rc = run_script(
        "run_morning_screener.py"
    )

    if rc != 0:
        print(
            "H1 : "
            "morning screener failed."
        )
        return

    rc = run_script(
        "create_intraday_strategy_h1.py"
    )

    if rc != 0:
        print(
            "H1 : strategy creation failed."
        )
        return

    rc = run_script(
        "update_rss_live_board_h1.py"
    )

    if rc != 0:
        print(
            "H1 : live board update failed."
        )
        return

    print(
        "H1 : live board update OK"
    )


def check_mode():
    path = find_latest_trigger_file()

    print("=" * 72)
    print(
        " MORNING LIVE CHECK"
    )
    print("=" * 72)

    print(
        "Current time :",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        "SSR trigger  :",
        path.name
        if path is not None
        else "NOT FOUND",
    )

    print(
        "H1-Early20   : 09:20-09:25"
    )

    print(
        "H1           : 09:30-09:35"
    )

    print(
        "SSR-Ver1     : until 09:30"
    )

    print(
        "SSR-Ver2     : 09:30 evaluation"
    )

    print("=" * 72)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check",
        action="store_true",
    )

    args = parser.parse_args()

    if args.check:
        check_mode()
        return

    now = datetime.now()

    h1_end = today_at(
        H1_END[0],
        H1_END[1],
    )

    if now > h1_end:
        print(
            "Morning live runner cannot "
            "start after 09:35."
        )
        print(
            "Use --check for configuration check."
        )
        return

    print("=" * 72)
    print(
        " MORNING LIVE RUNNER"
    )
    print("=" * 72)

    print(
        "Start time :",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    print(
        "SSR-Ver1   : until 09:30"
    )

    print(
        "SSR-Ver2   : 09:30"
    )

    print(
        "H1-Early20 : 09:20"
    )

    print(
        "H1         : 09:30"
    )

    print("=" * 72)
    print()

    # Refresh the JPX trigger files before starting SSR.
    print("=" * 72)
    print(" JPX TRIGGER REFRESH")
    print("=" * 72)

    rc = run_script(
        "download_short_sale_trigger_jpx.py"
    )

    if rc != 0:
        print(
            "WARNING : JPX trigger refresh failed."
        )
        print(
            "SSR will use the latest local trigger file."
        )

    latest_trigger = find_latest_trigger_file()

    print()
    print(
        "SSR trigger :",
        latest_trigger.name
        if latest_trigger is not None
        else "NOT FOUND",
    )
    print()

    if latest_trigger is None:
        print(
            "WARNING : SSR cannot start "
            "because no JPX trigger file exists."
        )

    stop_event = threading.Event()

    ssr_thread = threading.Thread(
        target=ssr_worker,
        args=(
            stop_event,
        ),
        daemon=False,
    )

    ssr_thread.start()

    # H1-Early20 validation is finished.
    # Keep run_early20() above for historical
    # reference / rollback only.
    print()
    print(
        "H1-Early20 : DISABLED "
        "- validation finished."
    )

    # ==================================================
    # Legacy H1 is disabled here.
    #
    # H1 is now handled independently by:
    #
    #     python src/intraday/rss_morning_runner.py
    #
    # Keep run_h1() above temporarily for rollback only.
    # SSR-Ver1 / SSR-Ver2 remain active.
    # ==================================================

    print()
    print(
        "Legacy H1 : DISABLED "
        "- handled by rss_morning_runner.py"
    )

    # SSR worker finishes its own 09:30 processing,
    # including SSR-Ver2 evaluation and CSV save.
    # Wait for it before completing the runner.
    ssr_thread.join()

    print()
    print("=" * 72)
    print(
        " MORNING LIVE COMPLETE"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
