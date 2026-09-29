from pathlib import Path

path = Path("tools/update_morning_baseline_after_close.py")
text = path.read_text(encoding="utf-8")

# import追加
old = """import sys
import time
from pathlib import Path
"""

new = """import sys
import time
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
"""

if old not in text:
    raise SystemExit("ERROR: import block not found")

text = text.replace(old, new, 1)

# 最初のYahoo取得
old = """    history_map = _download_history_batch(
        codes,
        period="6mo",
        batch_size=BATCH_SIZE,
    )
"""

new = """    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        history_map = _download_history_batch(
            codes,
            period="6mo",
            batch_size=BATCH_SIZE,
        )
"""

if old not in text:
    raise SystemExit("ERROR: first Yahoo block not found")

text = text.replace(old, new, 1)

# Retry取得
old = """        retry_map = _download_history_batch(
            retry_codes,
            period="6mo",
            batch_size=BATCH_SIZE,
        )
"""

new = """        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            retry_map = _download_history_batch(
                retry_codes,
                period="6mo",
                batch_size=BATCH_SIZE,
            )
"""

if old not in text:
    raise SystemExit("ERROR: retry Yahoo block not found")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("PATCHED :", path)
print("COMPLETE")
