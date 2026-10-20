import pandas as pd

CHANGE_MAX = 13.23
CXV_MAX = 17.34
MAX_STOCKS = 3
FIRST_ROW = 12


def select_h1_low_cxv(h1_candidates):
    """
    Select up to 3 LOW-CxV stocks from H1 TOP10.
    No Excel or CSV access.
    """
    required = ["CodeX", "ChangeX", "CxV"]

    missing = [
        col for col in required
        if col not in h1_candidates.columns
    ]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = h1_candidates.head(10).copy()

    df["CodeX"] = (
        df["CodeX"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    for col in ["ChangeX", "CxV"]:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    df = df[
        df["CodeX"].ne("")
        & df["CodeX"].ne("nan")
    ].drop_duplicates("CodeX")

    selected = (
        df[
            (df["ChangeX"] <= CHANGE_MAX)
            & (df["CxV"] <= CXV_MAX)
        ]
        .sort_values(
            ["CxV", "CodeX"],
            ascending=[True, True]
        )
        .head(MAX_STOCKS)
        .copy()
    )

    selected["BoardRow"] = range(
        FIRST_ROW,
        FIRST_ROW + len(selected)
    )

    selected["LowCxVRank"] = range(
        1,
        len(selected) + 1
    )

    return selected
