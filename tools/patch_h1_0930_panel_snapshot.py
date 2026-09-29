from pathlib import Path
import shutil

TARGET = Path("src/intraday/rss_morning_runner.py")
BACKUP = Path(
    "src/intraday/"
    "rss_morning_runner_before_0930_panel_snapshot.py"
)

text = TARGET.read_text(encoding="utf-8")

old = '''    global H1_CANDIDATES

    H1_CANDIDATES = [
        str(code).strip().replace(
            ".0",
            "",
        )
        for code
        in h1_candidates["CodeX"].tolist()
    ]

    print()
'''

new = '''    global H1_CANDIDATES
    global H1_0930_SNAPSHOT

    H1_CANDIDATES = [
        str(code).strip().replace(
            ".0",
            "",
        )
        for code
        in h1_candidates["CodeX"].tolist()
    ]

    # ============================================
    # Preserve the 09:30 full-market scan values.
    #
    # The full-market Rakuten RSS scan can finish
    # after 09:30:05.  Therefore the normal capture
    # slot may already have been missed.
    #
    # Use the values already stored in the 09:30
    # morning panel as the authoritative base for
    # the later 09:32 refill filter and BUY/WAIT.
    # ============================================

    H1_0930_SNAPSHOT = {}

    panel_code_map = {}

    for _, panel_row in panel_df.iterrows():

        code = str(
            panel_row.get("Code", "")
        ).strip()

        if code.endswith(".0"):
            code = code[:-2]

        if code:
            panel_code_map[code] = panel_row

    for code in H1_CANDIDATES:

        panel_row = panel_code_map.get(
            code
        )

        if panel_row is None:
            continue

        price = _safe_float(
            panel_row.get("MorningPrice")
        )

        volume = _safe_float(
            panel_row.get("MorningVolume")
        )

        if (
            price is None
            or price <= 0
            or volume is None
            or volume < 0
        ):
            continue

        H1_0930_SNAPSHOT[code] = {
            "Price": price,
            "Volume": volume,
        }

    print()
    print(
        "H1 09:30 panel snapshot : "
        f"{len(H1_0930_SNAPSHOT)} / "
        f"{len(H1_CANDIDATES)}"
    )

    print()
'''

if old not in text:
    raise SystemExit(
        "ERROR: target block not found. "
        "No changes made."
    )

if not BACKUP.exists():
    shutil.copy2(TARGET, BACKUP)
    print("Backup :", BACKUP)

text = text.replace(old, new, 1)

TARGET.write_text(
    text,
    encoding="utf-8",
)

print("Patched :", TARGET)
print("H1 09:30 panel snapshot patch : OK")
