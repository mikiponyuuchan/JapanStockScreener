from pathlib import Path
import shutil

TARGET = Path("src/intraday/rss_morning_runner.py")
BACKUP = Path(
    "src/intraday/"
    "rss_morning_runner_before_h1_buy_wait_retry.py"
)

text = TARGET.read_text(encoding="utf-8")

old = """        add_candidate(
            code,
            label,
        )

        print(
            f"H1 #{rank} "
"""

new = """        # Excel COM may temporarily reject a live-board
        # write while Rakuten RSS / Excel is busy.
        add_max_retries = 20
        add_retry_wait = 0.25
        add_last_error = None

        for add_attempt in range(
            1,
            add_max_retries + 1,
        ):
            try:
                add_candidate(
                    code,
                    label,
                )
                add_last_error = None

                if add_attempt > 1:
                    print(
                        "  H1 live-board write recovered "
                        f"after {add_attempt - 1} retries"
                    )

                break

            except Exception as exc:
                add_last_error = exc

                if add_attempt >= add_max_retries:
                    break

                if add_attempt == 1:
                    print(
                        "  H1 live-board COM busy "
                        "- retrying..."
                    )

                import time
                time.sleep(
                    add_retry_wait
                )

        if add_last_error is not None:
            raise RuntimeError(
                "H1 live-board write failed after "
                f"{add_max_retries} retries : "
                f"{add_last_error}"
            ) from add_last_error

        print(
            f"H1 #{rank} "
"""

count = text.count(old)

if count != 1:
    raise RuntimeError(
        f"Target block count is {count}; expected 1. "
        "No changes made."
    )

shutil.copy2(TARGET, BACKUP)

text = text.replace(old, new, 1)

TARGET.write_text(
    text,
    encoding="utf-8",
)

print(f"BACKUP  : {BACKUP}")
print("PATCHED : H1 BUY/WAIT live-board COM retry")
print(f"PATCHED : {TARGET}")
print("COMPLETE")
