from pathlib import Path
import shutil

path = Path("tools/update_tracking_after_close.py")
backup = Path(
    "tools/update_tracking_after_close_before_remove_p5.py"
)

text = path.read_text(encoding="utf-8")

shutil.copy2(path, backup)

# --------------------------------------------------
# 1. result_writer から make_p5_candidates を削除
# --------------------------------------------------
text = text.replace(
    """from services.result_writer import (
    make_initial_move_top20,
    make_p5_candidates,
)""",
    """from services.result_writer import (
    make_initial_move_top20,
)""",
)

# --------------------------------------------------
# 2. P5 tracking service import を削除
# --------------------------------------------------
text = text.replace(
    """from services.p5_tracking_service import (
    load_p5_tracking,
    record_p5_candidates,
    update_p5_tracking,
)

""",
    "",
)

# --------------------------------------------------
# 3. P5 candidate生成を削除
# --------------------------------------------------
text = text.replace(
    """    p5_candidates = (
        make_p5_candidates(
            df
        )
    )

""",
    "",
)

# --------------------------------------------------
# 4. P5 candidate表示を削除
# --------------------------------------------------
text = text.replace(
    """    print(
        "P5 candidates :",
        len(p5_candidates),
    )

""",
    "",
)

# --------------------------------------------------
# 5. P5 trackingブロックを削除
# --------------------------------------------------
start_marker = """    # ======================================================
    # P5 tracking
    # ======================================================
"""

end_marker = """    # ======================================================
    # J1 Trade Ver1 result update
    # ======================================================
"""

start = text.find(start_marker)
end = text.find(end_marker)

if start == -1:
    raise RuntimeError(
        "P5 tracking start marker not found"
    )

if end == -1:
    raise RuntimeError(
        "J1 tracking marker not found"
    )

text = (
    text[:start]
    + end_marker
    + text[end + len(end_marker):]
)

path.write_text(
    text,
    encoding="utf-8",
)

print("Backup :", backup)
print("Patched :", path)
print("P5 removal : OK")
