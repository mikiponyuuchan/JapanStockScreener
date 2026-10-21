import sys
import pandas as pd

sys.path.insert(0, "src")

from intraday.h1_low_cxv_board import preview_low_cxv_board

df = pd.read_csv(
    "data/tracking/h1_top10_tracking.csv",
    dtype={"Code": str},
)

df = df[
    df["DetectionDate"].astype(str) == "2026-10-20"
].copy()

df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce")
df = df.sort_values("Rank").head(10)

df = df.rename(
    columns={
        "Code": "CodeX",
        "Change": "ChangeX",
    }
)

board_rows = {
    i + 2: code
    for i, code in enumerate(df["CodeX"])
}

print("=== TEST 1: MATCH ===")
selected = preview_low_cxv_board(df, board_rows)

assert selected["CodeX"].tolist() == [
    "9563", "4288", "9478"
]
print("TEST 1 PASSED")

print()
print("=== TEST 2: MISMATCH ===")

wrong_rows = board_rows.copy()
wrong_rows[2] = "9999"

try:
    preview_low_cxv_board(df, wrong_rows)
except RuntimeError as exc:
    assert "TOP10 board rows mismatch" in str(exc)
    print("ABORT detected correctly")
    print("TEST 2 PASSED")
else:
    raise AssertionError("Mismatch was not detected")

print()
print("ALL TESTS PASSED")
