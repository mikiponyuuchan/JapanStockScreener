from pathlib import Path
import shutil

TARGET = Path(
    "src/services/jpx_risk_filter.py"
)

BACKUP = Path(
    "src/services/"
    "jpx_risk_filter_before_cache_guard.py"
)

text = TARGET.read_text(
    encoding="utf-8"
)

old = '''def load_blocked_codes():
    if not OUTPUT_PATH.exists():
        return set()

    df = pd.read_csv(
        OUTPUT_PATH,
        dtype={"Code": str},
    )

    if "Action" not in df.columns:
        return set()

    blocked = df[
        df["Action"] == "BLOCK"
    ]

    return set(
        blocked["Code"]
        .astype(str)
        .str.strip()
    )
'''

new = '''def load_blocked_codes():
    if not OUTPUT_PATH.exists():
        raise RuntimeError(
            "JPX risk cache not found: "
            f"{OUTPUT_PATH}"
        )

    df = pd.read_csv(
        OUTPUT_PATH,
        dtype={"Code": str},
    )

    required_columns = {
        "Code",
        "Action",
    }

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "JPX risk cache is invalid. "
            "Missing columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    blocked = df[
        df["Action"] == "BLOCK"
    ]

    return set(
        blocked["Code"]
        .astype(str)
        .str.strip()
    )
'''

count = text.count(old)

if count != 1:
    raise RuntimeError(
        f"Target count is {count}; "
        "expected 1. No changes made."
    )

shutil.copy2(
    TARGET,
    BACKUP,
)

text = text.replace(
    old,
    new,
    1,
)

TARGET.write_text(
    text,
    encoding="utf-8",
)

print(f"BACKUP  : {BACKUP}")
print("PATCHED : JPX risk cache guard")
print(f"PATCHED : {TARGET}")
print("COMPLETE")
