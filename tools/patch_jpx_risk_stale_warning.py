from pathlib import Path
import shutil

TARGET = Path(
    "src/services/jpx_risk_filter.py"
)

BACKUP = Path(
    "src/services/"
    "jpx_risk_filter_before_stale_warning.py"
)

text = TARGET.read_text(
    encoding="utf-8"
)

old = '''    required_columns = {
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
'''

new = '''    required_columns = {
        "Code",
        "Action",
        "UpdatedAt",
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

    updated_values = pd.to_datetime(
        df["UpdatedAt"],
        errors="coerce",
    ).dropna()

    if updated_values.empty:
        raise RuntimeError(
            "JPX risk cache has no valid "
            "UpdatedAt value."
        )

    updated_at = updated_values.max()
    now = pd.Timestamp.now()

    age_days = (
        now - updated_at
    ).total_seconds() / 86400.0

    if age_days >= 3.0:
        print()
        print(
            "WARNING : JPX RISK CACHE "
            "IS STALE"
        )
        print(
            "UpdatedAt :",
            updated_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )
        print(
            "Age       : "
            f"{age_days:.1f} days"
        )
        print(
            "Using last valid cache."
        )
        print()

    blocked = df[
        df["Action"] == "BLOCK"
    ]
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
print(
    "PATCHED : JPX risk stale "
    "cache warning"
)
print(f"PATCHED : {TARGET}")
print("COMPLETE")
