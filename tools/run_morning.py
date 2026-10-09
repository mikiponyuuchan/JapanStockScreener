import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MORNING_LIVE = ROOT / "tools" / "run_morning_live.py"
RSS_MORNING = ROOT / "src" / "intraday" / "rss_morning_runner.py"


def main():
    print("=" * 72)
    print(" MORNING ALL-IN-ONE LAUNCHER")
    print("=" * 72)
    print("1. SSR / Early20 : tools\\run_morning_live.py")
    print("2. J1 / H1       : src\\intraday\\rss_morning_runner.py")
    print("=" * 72)

    processes = []

    try:
        print()
        print("Starting MORNING LIVE...")
        live_process = subprocess.Popen(
            [sys.executable, str(MORNING_LIVE)],
            cwd=str(ROOT),
        )
        processes.append(("MORNING LIVE", live_process))
        print(f"MORNING LIVE PID : {live_process.pid}")

        print()
        print("Starting RSS MORNING...")
        rss_process = subprocess.Popen(
            [sys.executable, str(RSS_MORNING)],
            cwd=str(ROOT),
        )
        processes.append(("RSS MORNING", rss_process))
        print(f"RSS MORNING PID  : {rss_process.pid}")

        print()
        print("=" * 72)
        print(" BOTH MORNING RUNNERS STARTED")
        print("=" * 72)

        remaining = dict(processes)

        while remaining:
            for name, process in list(remaining.items()):
                return_code = process.poll()

                if return_code is not None:
                    print()
                    print(
                        f"{name} finished "
                        f"(return code={return_code})"
                    )
                    del remaining[name]

            if remaining:
                import time
                time.sleep(1)

        print()
        print("=" * 72)
        print(" ALL MORNING RUNNERS COMPLETE")
        print("=" * 72)

    except KeyboardInterrupt:
        print()
        print("Launcher interrupted.")
        print("Child processes are left running.")
        print(
            "Stop them individually with Ctrl+C "
            "in their own console if necessary."
        )


if __name__ == "__main__":
    main()
