from pathlib import Path
import shutil

TARGET = Path(
    "src/services/jpx_risk_filter.py"
)

BACKUP = Path(
    "src/services/"
    "jpx_risk_filter_before_dataframe_filter.py"
)

text = TARGET.read_text(
    encoding="utf-8"
)

marker = """
if __name__ == "__main__":

    df = build_jpx_risk_list()
"""

new_block = """
def filter_blocked_stocks(
    df,
    code_column="Code",
    verbose=True,
):
    \"\"\"
    Remove JPX BLOCK stocks from a DataFrame.

    WARN stocks remain tradable.
    The original DataFrame is not modified.
    \"\"\"

    if df is None:
        return df

    if df.empty:
        return df.copy()

    if code_column not in df.columns:
        raise KeyError(
            f"Code column not found: "
            f"{code_column}"
        )

    blocked_codes = load_blocked_codes()

    if not blocked_codes:
        if verbose:
            print(
                "JPX RISK FILTER : "
                "no BLOCK codes loaded"
            )

        return df.copy()

    work = df.copy()

    normalized_codes = (
        work[code_column]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\\\\.0$",
            "",
            regex=True,
        )
    )

    blocked_mask = (
        normalized_codes.isin(
            blocked_codes
        )
    )

    removed = work[
        blocked_mask
    ].copy()

    filtered = work[
        ~blocked_mask
    ].copy()

    filtered = filtered.reset_index(
        drop=True
    )

    if verbose:
        print()
        print("=" * 60)
        print(" JPX RISK FILTER")
        print("=" * 60)

        print(
            "Input  :",
            len(work),
        )

        print(
            "Blocked:",
            len(removed),
        )

        print(
            "Output :",
            len(filtered),
        )

        if not removed.empty:
            print()
            print("Excluded codes:")

            for code in (
                normalized_codes[
                    blocked_mask
                ].tolist()
            ):
                print(
                    f"  {code}"
                )

        print("=" * 60)

    return filtered


if __name__ == "__main__":

    df = build_jpx_risk_list()
"""

count = text.count(marker)

if count != 1:
    raise RuntimeError(
        f"Target marker count is {count}; "
        "expected 1. No changes made."
    )

shutil.copy2(
    TARGET,
    BACKUP,
)

text = text.replace(
    marker,
    new_block,
    1,
)

TARGET.write_text(
    text,
    encoding="utf-8",
)

print(
    f"BACKUP  : {BACKUP}"
)
print(
    "PATCHED : DataFrame BLOCK filter"
)
print(
    f"PATCHED : {TARGET}"
)
print("COMPLETE")
