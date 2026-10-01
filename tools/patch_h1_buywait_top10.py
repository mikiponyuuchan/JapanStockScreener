from pathlib import Path

path = Path("src/intraday/rss_morning_runner.py")

text = path.read_text(
    encoding="utf-8"
)

backup = Path(
    "src/intraday/"
    "rss_morning_runner_before_buywait_top10.py"
)

backup.write_text(
    text,
    encoding="utf-8",
)

old = '''    if not H1_TOP3_RANK:
        print(
            "No final H1 stocks."
        )
        H1_HYBRID_DECISION_DONE = True
        print("=" * 60)
        return

    for code, rank in sorted(
        H1_TOP3_RANK.items(),
        key=lambda item: item[1],
    ):
'''

new = '''    if not H1_CANDIDATES:
        print(
            "No H1 TOP10 candidates."
        )
        H1_HYBRID_DECISION_DONE = True
        print("=" * 60)
        return

    # BUY / WAIT is displayed for the full
    # 09:30 CxV TOP10 candidate pool.
    #
    # IMPORTANT:
    # H1_TOP3_RANK and H1_MAX_SELECTED remain
    # unchanged.  They continue to represent
    # the formal refill-selected TOP3.
    for rank, code in enumerate(
        H1_CANDIDATES,
        start=1,
    ):
'''

if old not in text:
    raise SystemExit(
        "ERROR: target block not found"
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

print("PATCHED : H1 BUY/WAIT TOP10 live display")
print("BACKUP  :", backup)
print("PATCHED :", path)
print("COMPLETE")
