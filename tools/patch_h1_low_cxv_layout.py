from pathlib import Path

path = Path("src/intraday/rss_board_fixed_layout.py")
text = path.read_text(encoding="utf-8")

old = '''        if row >= 17
        else ("", "")
        for row in range(FIRST_ROW, LAST_ROW + 1)
'''

new = '''        if row >= 12
        else ("", "")
        for row in range(FIRST_ROW, LAST_ROW + 1)
'''

if text.count(old) != 1:
    raise SystemExit(
        "PATCH ABORT: expected layout block was not found exactly once"
    )

updated = text.replace(old, new, 1)

compile(updated, str(path), "exec")
path.write_text(updated, encoding="utf-8", newline="")

print("PATCH OK:", path)
print("Changed: preserve existing rows 12-21")
print("Syntax: OK")
