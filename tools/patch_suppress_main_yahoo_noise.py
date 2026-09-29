from pathlib import Path

path = Path("src/main.py")
text = path.read_text(encoding="utf-8")

# import追加
old = """import time
"""

new = """import time
import io
from contextlib import redirect_stderr
"""

if old not in text:
    raise SystemExit("ERROR: import block not found")

text = text.replace(old, new, 1)

# Yahoo一括取得だけstderr抑制
old = """    history_map = _download_history_batch(
        codes,
        period="6mo",
        batch_size=BATCH_SIZE
    )
"""

new = """    with redirect_stderr(io.StringIO()):
        history_map = _download_history_batch(
            codes,
            period="6mo",
            batch_size=BATCH_SIZE
        )
"""

if old not in text:
    raise SystemExit("ERROR: Yahoo block not found")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("PATCHED :", path)
print("COMPLETE")
