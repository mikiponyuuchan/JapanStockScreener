from pathlib import Path
import shutil


TARGET = Path(
    "src/intraday/rss_morning_runner.py"
)

BACKUP = Path(
    "src/intraday/"
    "rss_morning_runner_before_startup_retry.py"
)


def main():

    text = TARGET.read_text(
        encoding="utf-8"
    )

    old = """    check_rss_startup()

    # ============================================
    # Refresh live-board volume master.
"""

    new = """    # ============================================
    # RSS startup retry
    #
    # Excel / Rakuten RSS COM may temporarily point
    # to another Excel instance or reject COM calls.
    # Do not terminate the morning runner for a
    # temporary startup failure.
    #
    # Keep retrying until the RSS workbooks become
    # available or today's capture window ends.
    # ============================================

    startup_retry_seconds = 5

    while True:

        try:
            check_rss_startup()
            break

        except Exception as exc:

            retry_now = datetime.now()

            if retry_now > final_time:
                print()
                print(
                    "RSS startup check could not "
                    "recover before the end of "
                    "today's capture window."
                )
                print(
                    "Morning Runner : END"
                )
                return

            print()
            print(
                "RSS startup check temporarily failed."
            )
            print(
                "Morning Runner will continue."
            )
            print(
                f"Retry in {startup_retry_seconds} sec..."
            )
            print(
                f"Reason : {exc}"
            )

            time.sleep(
                startup_retry_seconds
            )

    # ============================================
    # Refresh live-board volume master.
"""

    if old not in text:
        raise RuntimeError(
            "Target block not found. "
            "Patch was not applied."
        )

    if not BACKUP.exists():
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
        "PATCHED : RSS startup retry"
    )
    print(
        "BACKUP  :",
        BACKUP,
    )
    print(
        "PATCHED :",
        TARGET,
    )
    print(
        "COMPLETE"
    )


if __name__ == "__main__":
    main()