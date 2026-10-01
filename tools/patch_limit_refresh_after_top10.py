from pathlib import Path
import shutil

path = Path("src/intraday/rss_morning_runner.py")
backup = Path(
    "src/intraday/"
    "rss_morning_runner_before_limit_refresh_after_top10.py"
)

text = path.read_text(encoding="utf-8")

old = '''    print(
        "H1 TOP10 candidate live board update : OK"
    )

    run_capture()
'''

new = '''    print(
        "H1 TOP10 candidate live board update : OK"
    )

    # ============================================
    # Refresh stop-high prices AFTER the TOP10
    # stocks have been written to the live board.
    #
    # Every J row is first restored to the normal
    # TSE price-limit formula.  JPX expanded-limit
    # stocks are then overwritten with the official
    # JPX stop-high price.
    # ============================================

    print()
    print("=" * 60)
    print(" LIVE BOARD PRICE LIMIT")
    print("=" * 60)

    refresh_expanded_price_limits()

    run_capture()
'''

if old not in text:
    raise SystemExit(
        "PATCH TARGET NOT FOUND - no file changed"
    )

shutil.copy2(path, backup)

text = text.replace(old, new, 1)

path.write_text(
    text,
    encoding="utf-8",
)

print("PATCHED : price-limit refresh after TOP10")
print(f"BACKUP  : {backup}")
print(f"PATCHED : {path}")
print("COMPLETE")
