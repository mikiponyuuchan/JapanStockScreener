from pathlib import Path
import shutil

TARGET = Path("src/intraday/rss_morning_runner.py")

BACKUP = Path(
    "src/intraday/"
    "rss_morning_runner_before_jpx_risk_filter.py"
)

text = TARGET.read_text(encoding="utf-8")

# ----------------------------------------
# Add src to sys.path and import filter
# ----------------------------------------

old_import = '''ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from rss_watchlist import (
'''

new_import = '''ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
SRC = ROOT / "src"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from services.jpx_risk_filter import (
    filter_blocked_stocks,
)

from rss_watchlist import (
'''

if old_import not in text:
    raise RuntimeError(
        "ROOT/TOOLS import block not found. "
        "No changes made."
    )

# ----------------------------------------
# Insert filter before build_watchlist
# ----------------------------------------

old_h1 = '''    panel_df = read_panel(
        panel_path
    )

    watchlist = build_watchlist(
        panel_df
    )
'''

new_h1 = '''    panel_df = read_panel(
        panel_path
    )

    # JPX risk filter
    # BLOCK stocks are removed before CxV ranking.
    # WARN stocks remain tradable.
    panel_df = filter_blocked_stocks(
        panel_df,
        code_column="Code",
        verbose=True,
    )

    watchlist = build_watchlist(
        panel_df
    )
'''

if old_h1 not in text:
    raise RuntimeError(
        "H1 panel/watchlist block not found. "
        "No changes made."
    )

# ----------------------------------------
# Backup only after both targets found
# ----------------------------------------

shutil.copy2(TARGET, BACKUP)

text = text.replace(
    old_import,
    new_import,
    1,
)

text = text.replace(
    old_h1,
    new_h1,
    1,
)

TARGET.write_text(
    text,
    encoding="utf-8",
)

print(f"BACKUP  : {BACKUP}")
print("PATCHED : added SRC to sys.path")
print("PATCHED : imported JPX risk filter")
print("PATCHED : filter before H1 CxV ranking")
print(f"PATCHED : {TARGET}")
print("COMPLETE")
