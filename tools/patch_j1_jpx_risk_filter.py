from pathlib import Path
import shutil

TARGET = Path(
    "tools/create_j1_trade_plan.py"
)

BACKUP = Path(
    "tools/"
    "create_j1_trade_plan_before_jpx_risk_filter.py"
)

text = TARGET.read_text(
    encoding="utf-8"
)

old_import = '''from pathlib import Path
from datetime import date

import pandas as pd
'''

new_import = '''from pathlib import Path
from datetime import date
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from services.jpx_risk_filter import (
    filter_blocked_stocks,
)
'''

old_trade = '''    trade = today_j1[
        (today_j1["Change1"] >= CHANGE_MIN)
        & (today_j1["Change1"] < CHANGE_MAX)
    ].copy()

    trade = trade.sort_values(
'''

new_trade = '''    trade = today_j1[
        (today_j1["Change1"] >= CHANGE_MIN)
        & (today_j1["Change1"] < CHANGE_MAX)
    ].copy()

    # JPX risk filter
    # BLOCK stocks must not enter
    # tomorrow's real J1 trade plan.
    trade = filter_blocked_stocks(
        trade,
        code_column="Code",
        verbose=True,
    )

    trade = trade.sort_values(
'''

if text.count(old_import) != 1:
    raise RuntimeError(
        "Import target not found exactly once. "
        "No changes made."
    )

if text.count(old_trade) != 1:
    raise RuntimeError(
        "Trade target not found exactly once. "
        "No changes made."
    )

shutil.copy2(
    TARGET,
    BACKUP,
)

text = text.replace(
    old_import,
    new_import,
    1,
)

text = text.replace(
    old_trade,
    new_trade,
    1,
)

TARGET.write_text(
    text,
    encoding="utf-8",
)

print(f"BACKUP  : {BACKUP}")
print(
    "PATCHED : J1 JPX risk filter"
)
print(f"PATCHED : {TARGET}")
print("COMPLETE")
