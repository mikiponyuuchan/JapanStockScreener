from pathlib import Path

path = Path("tools/run_morning_screener_rss.py")
backup = Path(
    "tools/run_morning_screener_rss_before_snapshot_retry.py"
)

text = path.read_text(encoding="utf-8")

old = '''    morning, rss_metadata = fetch_full_snapshot()

    if morning is None or morning.empty:
        raise RuntimeError(
            "Morning Rakuten RSS data is empty"
        )
'''

new = '''    morning, rss_metadata = fetch_full_snapshot()

    # ==================================================
    # Full-market snapshot safety retry
    #
    # A normal Rakuten RSS scan obtains almost the whole
    # universe.  Retry once only when the first scan is
    # clearly abnormal.
    # ==================================================

    expected_rss_rows = len(codes)
    minimum_rss_rows = int(
        expected_rss_rows * 0.80
    )

    actual_rss_rows = (
        0
        if morning is None
        else len(morning)
    )

    if actual_rss_rows < minimum_rss_rows:
        print()
        print("=" * 72)
        print(" RSS FULL SNAPSHOT SAFETY RETRY")
        print("=" * 72)
        print(
            "First scan rows :",
            actual_rss_rows,
            "/",
            expected_rss_rows,
        )
        print(
            "Minimum rows    :",
            minimum_rss_rows,
        )
        print(
            "Abnormal snapshot detected."
        )
        print(
            "Retrying once after 5 seconds..."
        )
        print()

        time.sleep(5)

        morning, rss_metadata = (
            fetch_full_snapshot()
        )

        actual_rss_rows = (
            0
            if morning is None
            else len(morning)
        )

        print()
        print(
            "Retry scan rows :",
            actual_rss_rows,
            "/",
            expected_rss_rows,
        )

    if morning is None or morning.empty:
        raise RuntimeError(
            "Morning Rakuten RSS data is empty "
            "after safety retry"
        )

    if len(morning) < minimum_rss_rows:
        raise RuntimeError(
            "Morning Rakuten RSS data is abnormally low "
            f"after safety retry : "
            f"{len(morning)} / {expected_rss_rows}"
        )
'''

if old not in text:
    raise SystemExit(
        "STOP : target block was not found."
    )

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

text = text.replace(
    old,
    new,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "PATCHED : full snapshot safety retry"
)
print(
    "BACKUP  :",
    backup,
)
print(
    "PATCHED :",
    path,
)
print("COMPLETE")
