from pathlib import Path
import shutil

TARGET = Path("src/intraday/rss_snapshot.py")
BACKUP = Path(
    "src/intraday/"
    "rss_snapshot_before_clear_calculate_retry.py"
)

text = TARGET.read_text(
    encoding="utf-8"
)

old = '''        clear_board(
            sheet
        )

        excel.Calculate()

        time.sleep(
            0.25
        )
'''

new = '''        clear_board(
            sheet
        )

        # Excel may temporarily reject Calculate while
        # Rakuten RSS / Excel is still busy after the
        # previous batch.  Retry here just like the
        # Calculate call used when starting a batch.
        calc_max_retries = 20
        calc_retry_wait = 0.25
        calc_last_error = None

        for calc_attempt in range(
            1,
            calc_max_retries + 1,
        ):
            try:
                excel.Calculate()
                calc_last_error = None

                if calc_attempt > 1:
                    print(
                        "  Excel COM clear calculate recovered "
                        f"after {calc_attempt - 1} retries"
                    )

                break

            except Exception as exc:
                calc_last_error = exc

                if calc_attempt >= calc_max_retries:
                    break

                if calc_attempt == 1:
                    print(
                        "  Excel COM clear calculate busy "
                        "- retrying..."
                    )

                time.sleep(
                    calc_retry_wait
                )

        if calc_last_error is not None:
            raise RuntimeError(
                "Excel COM clear calculate failed after "
                f"{calc_max_retries} retries : "
                f"{calc_last_error}"
            ) from calc_last_error

        time.sleep(
            0.25
        )
'''

count = text.count(old)

if count != 1:
    raise RuntimeError(
        "Target block count must be 1, "
        f"but found {count}."
    )

shutil.copy2(
    TARGET,
    BACKUP,
)

text = text.replace(
    old,
    new,
    1,
)

TARGET.write_text(
    text,
    encoding="utf-8",
)

print(
    "BACKUP  :",
    BACKUP,
)
print(
    "PATCHED : RSS snapshot clear Calculate retry"
)
print(
    "PATCHED :",
    TARGET,
)
print("COMPLETE")
