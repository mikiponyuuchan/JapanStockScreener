from pathlib import Path

path = Path("tools/update_tracking_after_close.py")
backup = Path(
    "tools/update_tracking_after_close_before_jpx_risk_refresh.py"
)

text = path.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

# ==========================================================
# import追加
# ==========================================================

old_import = '''from services.result_writer import (
    make_initial_move_top20,
)
'''

new_import = '''from services.result_writer import (
    make_initial_move_top20,
)

from services.jpx_risk_filter import (
    build_jpx_risk_list,
)
'''

if old_import not in text:
    raise RuntimeError(
        "Import position not found."
    )

text = text.replace(
    old_import,
    new_import,
    1,
)

# ==========================================================
# J1 plan直前へJPX更新を追加
# ==========================================================

marker = '''    # ======================================================
    # J1 Trade Ver1 plan creation
    # ======================================================
'''

block = '''    # ======================================================
    # JPX risk cache refresh
    #
    # Refresh before creating tomorrow's J1 trade plan.
    # If refresh fails, keep using the last valid cache.
    # ======================================================

    print()
    print("[JPX risk cache refresh]")

    try:

        risk_df = build_jpx_risk_list()

        block_count = (
            risk_df["Action"]
            .eq("BLOCK")
            .sum()
        )

        warn_count = (
            risk_df["Action"]
            .eq("WARN")
            .sum()
        )

        print(
            "JPX risk rows :",
            len(risk_df),
        )

        print(
            "BLOCK         :",
            block_count,
        )

        print(
            "WARN          :",
            warn_count,
        )

        print(
            "JPX risk cache refresh : complete"
        )

    except Exception as e:

        print(
            "JPX risk cache refresh ERROR :",
            e,
        )

        print(
            "Using last valid JPX risk cache."
        )

    # ======================================================
    # J1 Trade Ver1 plan creation
    # ======================================================
'''

if marker not in text:
    raise RuntimeError(
        "J1 plan position not found."
    )

text = text.replace(
    marker,
    block,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print("Patched:", path)
print("Backup :", backup)
