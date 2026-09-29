from pathlib import Path

path = Path("tools/update_j_type_tracking.py")
text = path.read_text(encoding="utf-8")

old = """from pathlib import Path
from datetime import date
import sys
"""

new = """from pathlib import Path
from datetime import date
import sys
import io
from contextlib import redirect_stderr
"""

if old not in text:
    raise SystemExit("ERROR: import block not found")

text = text.replace(old, new, 1)

old = """    history_map = _download_history_batch(
        codes,
        period="3mo",
        batch_size=100,
    )
"""

new = """    with redirect_stderr(io.StringIO()):
        history_map = _download_history_batch(
            codes,
            period="3mo",
            batch_size=100,
        )
"""

if old not in text:
    raise SystemExit("ERROR: Yahoo block not found")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("PATCHED :", path)
print("COMPLETE")
