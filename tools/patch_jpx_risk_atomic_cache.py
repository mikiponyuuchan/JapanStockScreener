from pathlib import Path

path = Path("src/services/jpx_risk_filter.py")
backup = Path(
    "src/services/jpx_risk_filter_before_atomic_cache.py"
)

text = path.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

old = '''    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    return df
'''

new = '''    # ======================================================
    # Safe cache replacement
    #
    # Never write directly to the current valid cache.
    # Write and validate a temporary file first, then replace.
    # ======================================================

    temp_path = OUTPUT_PATH.with_suffix(
        ".tmp.csv"
    )

    try:
        df.to_csv(
            temp_path,
            index=False,
            encoding="utf-8-sig",
        )

        check_df = pd.read_csv(
            temp_path,
            dtype={"Code": str},
            encoding="utf-8-sig",
        )

        required_columns = {
            "Code",
            "RiskType",
            "Action",
            "Reason",
            "UpdatedAt",
        }

        missing_columns = (
            required_columns
            - set(check_df.columns)
        )

        if missing_columns:
            raise RuntimeError(
                "Temporary JPX risk cache "
                "missing columns: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        if check_df.empty:
            raise RuntimeError(
                "Temporary JPX risk cache is empty."
            )

        if len(check_df) != len(df):
            raise RuntimeError(
                "Temporary JPX risk cache "
                "row count mismatch: "
                f"{len(check_df)} != {len(df)}"
            )

        # Atomic replacement on the same filesystem.
        temp_path.replace(
            OUTPUT_PATH
        )

    finally:
        if temp_path.exists():
            temp_path.unlink()

    return df
'''

if old not in text:
    raise RuntimeError(
        "Target save block not found."
    )

text = text.replace(
    old,
    new,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print("Patched:", path)
print("Backup :", backup)
