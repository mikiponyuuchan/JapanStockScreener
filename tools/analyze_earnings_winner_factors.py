from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

path = (
    ROOT
    / "data"
    / "analysis"
    / "earnings_backtest_panel.csv"
)

df = pd.read_csv(path)

target = df[
    df["Rating"] == "STRONG_GOOD"
].copy()

numeric_cols = [
    "SalesYoY",
    "OperatingYoY",
    "OrdinaryYoY",
    "NetYoY",
    "StrengthScore",
    "StrengthScoreV2",
    "\u7fcc\u65e5\u9ad8\u5024\u7387",
    "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387",
    "\u7fcc\u65e5\u7d42\u5024\u7387",
]

for col in numeric_cols:
    if col in target.columns:
        target[col] = pd.to_numeric(
            target[col],
            errors="coerce",
        )

target["MinGrowth4"] = target[
    [
        "SalesYoY",
        "OperatingYoY",
        "OrdinaryYoY",
        "NetYoY",
    ]
].min(axis=1)

target["MaxGrowth4"] = target[
    [
        "SalesYoY",
        "OperatingYoY",
        "OrdinaryYoY",
        "NetYoY",
    ]
].max(axis=1)

target["GrowthSpread"] = (
    target["MaxGrowth4"]
    - target["MinGrowth4"]
)

high_col = "\u7fcc\u65e5\u9ad8\u5024\u7387"
m0930_col = "\u0030\u0039\u003a\u0033\u0030\u9a30\u843d\u7387"
close_col = "\u7fcc\u65e5\u7d42\u5024\u7387"

target["Hit5"] = (
    target[high_col] >= 5.0
)

target["Hit10"] = (
    target[high_col] >= 10.0
)


def summary(label, part):
    if part.empty:
        return

    print()
    print("=" * 82)
    print(label)
    print("=" * 82)

    print("N             :", len(part))
    print(
        "09:30 mean    :",
        round(part[m0930_col].mean(), 2),
    )
    print(
        "High mean     :",
        round(part[high_col].mean(), 2),
    )
    print(
        "Close mean    :",
        round(part[close_col].mean(), 2),
    )
    print(
        "High +5% rate :",
        round(part["Hit5"].mean() * 100, 1),
        "%",
    )
    print(
        "High +10% rate:",
        round(part["Hit10"].mean() * 100, 1),
        "%",
    )


print("=" * 82)
print("STRONG_GOOD FACTOR ANALYSIS")
print("=" * 82)
print("Total :", len(target))


#
# Forecast revision
#
for value in [
    "\u6709",
    "\u7121",
    "\u4e0d\u660e",
]:
    part = target[
        target["Revision"].astype(str)
        == value
    ]

    summary(
        "REVISION = " + value,
        part,
    )


#
# Minimum growth
#
for threshold in [
    0,
    10,
    20,
    30,
    40,
]:
    part = target[
        target["MinGrowth4"]
        >= threshold
    ]

    summary(
        f"MIN GROWTH >= {threshold}%",
        part,
    )


#
# Sales growth
#
for threshold in [
    10,
    20,
    30,
    50,
]:
    part = target[
        target["SalesYoY"]
        >= threshold
    ]

    summary(
        f"SALES >= {threshold}%",
        part,
    )


#
# V2 score bands
#
for threshold in [
    40,
    50,
    60,
    70,
    80,
]:
    part = target[
        target["StrengthScoreV2"]
        >= threshold
    ]

    summary(
        f"SCORE V2 >= {threshold}",
        part,
    )


#
# Winners versus others
#
winners = target[
    target["Hit5"]
]

others = target[
    ~target["Hit5"]
]

print()
print("=" * 82)
print("HIGH +5% WINNERS VS OTHERS")
print("=" * 82)

for col in [
    "SalesYoY",
    "OperatingYoY",
    "OrdinaryYoY",
    "NetYoY",
    "MinGrowth4",
    "GrowthSpread",
    "StrengthScoreV2",
]:
    print()
    print(col)

    print(
        "  Winner mean :",
        round(winners[col].mean(), 2),
    )

    print(
        "  Other mean  :",
        round(others[col].mean(), 2),
    )

print()
print("=" * 82)
print("TOP +5% WINNERS")
print("=" * 82)

show_cols = [
    "DetectionDate",
    "Code",
    "Name",
    "SalesYoY",
    "OperatingYoY",
    "OrdinaryYoY",
    "NetYoY",
    "Revision",
    "StrengthScoreV2",
    high_col,
    m0930_col,
    close_col,
]

print(
    winners[
        show_cols
    ]
    .sort_values(
        high_col,
        ascending=False,
    )
    .to_string(
        index=False
    )
)
