from pathlib import Path

path = Path(
    "tools/analyze_earnings_strength.py"
)

text = path.read_text(
    encoding="utf-8"
)

backup = Path(
    "tools/analyze_earnings_strength_before_v2.py"
)

backup.write_text(
    text,
    encoding="utf-8"
)

needle = '''
def main():
'''

addition = r'''
def calculate_strength_v2(row, cols):
    sales = pd.to_numeric(
        row[cols["sales"]],
        errors="coerce",
    )
    operating = pd.to_numeric(
        row[cols["operating"]],
        errors="coerce",
    )
    ordinary = pd.to_numeric(
        row[cols["ordinary"]],
        errors="coerce",
    )
    net = pd.to_numeric(
        row[cols["net"]],
        errors="coerce",
    )

    values = [
        sales,
        operating,
        ordinary,
        net,
    ]

    score = 0.0

    #
    # Four growth components:
    # 15 points each.
    #
    score += capped_score(
        sales,
        50.0,
        15.0,
    )
    score += capped_score(
        operating,
        100.0,
        15.0,
    )
    score += capped_score(
        ordinary,
        100.0,
        15.0,
    )
    score += capped_score(
        net,
        100.0,
        15.0,
    )

    #
    # Balance bonus:
    # Reward the weakest of all four
    # growth measures.
    #
    if all(
        not pd.isna(x)
        for x in values
    ):
        min_growth = min(values)

        score += capped_score(
            min_growth,
            50.0,
            25.0,
        )

    #
    # Forecast upward revision bonus.
    #
    revision = str(
        row[cols["revision"]]
    ).strip()

    if revision == "\u6709":
        score += 15.0

    return round(
        score,
        1,
    )


'''

if needle not in text:
    raise RuntimeError(
        "Insert point not found"
    )

text = text.replace(
    needle,
    addition + needle,
    1,
)

needle = '''    df["StrengthScore"] = df.apply(
        calculate_strength,
        axis=1,
        cols=cols,
    )
'''

replacement = '''    df["StrengthScore"] = df.apply(
        calculate_strength,
        axis=1,
        cols=cols,
    )

    df["StrengthScoreV2"] = df.apply(
        calculate_strength_v2,
        axis=1,
        cols=cols,
    )
'''

if needle not in text:
    raise RuntimeError(
        "Score block not found"
    )

text = text.replace(
    needle,
    replacement,
    1,
)

needle = '''    eligible["Priority"] = "WATCH"
'''

replacement = '''    eligible["Priority"] = "WATCH"

    v2 = eligible.sort_values(
        [
            "StrengthScoreV2",
            cols["sales"],
            cols["operating"],
        ],
        ascending=[
            False,
            False,
            False,
        ],
    ).copy()

    v2["PriorityV2"] = "WATCH"

    if len(v2) > 0:
        v2.iloc[
            0:min(3, len(v2)),
            v2.columns.get_loc(
                "PriorityV2"
            ),
        ] = "PRIORITY_1"

    if len(v2) > 3:
        v2.iloc[
            3:min(8, len(v2)),
            v2.columns.get_loc(
                "PriorityV2"
            ),
        ] = "PRIORITY_2"

    priority_v2_map = dict(
        zip(
            v2[cols["code"]].astype(str),
            v2["PriorityV2"],
        )
    )

    eligible["PriorityV2"] = (
        eligible[cols["code"]]
        .astype(str)
        .map(priority_v2_map)
        .fillna("WATCH")
    )
'''

if needle not in text:
    raise RuntimeError(
        "Priority block not found"
    )

text = text.replace(
    needle,
    replacement,
    1,
)

needle = '''            "StrengthScore",
            "Priority",
'''

replacement = '''            "StrengthScore",
            "Priority",
            "StrengthScoreV2",
            "PriorityV2",
'''

if needle not in text:
    raise RuntimeError(
        "Display block not found"
    )

text = text.replace(
    needle,
    replacement,
    1,
)

needle = '''    print()
    print(
        "Saved :",
        out_path,
    )
'''

replacement = '''    print()
    print(
        "=" * 78
    )
    print(
        "PRIORITY_1 V2"
    )
    print(
        "=" * 78
    )

    p1_v2 = v2[
        v2["PriorityV2"]
        == "PRIORITY_1"
    ]

    if p1_v2.empty:
        print(
            "No candidates."
        )
    else:
        for rank, (_, row) in enumerate(
            p1_v2.iterrows(),
            start=1,
        ):
            print(
                rank,
                row[cols["code"]],
                row[cols["name"]],
                "ScoreV2=",
                row["StrengthScoreV2"],
            )

    print()
    print(
        "Saved :",
        out_path,
    )
'''

if needle not in text:
    raise RuntimeError(
        "Output block not found"
    )

text = text.replace(
    needle,
    replacement,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "PATCHED :",
    path,
)
print(
    "BACKUP  :",
    backup,
)
