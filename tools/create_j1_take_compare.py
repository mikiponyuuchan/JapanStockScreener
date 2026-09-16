from pathlib import Path

src = Path("tools/analyze_j1_stop_compare.py")
dst = Path("tools/analyze_j1_take_compare.py")

text = src.read_text(encoding="utf-8")

text = text.replace(
    'OUTPUT_PATH = Path(\n'
    '    "data/analysis/j1_stop_compare_520_549.csv"\n'
    ')',
    'OUTPUT_PATH = Path(\n'
    '    "data/analysis/j1_take_compare_520_549.csv"\n'
    ')',
)

text = text.replace(
    '''TAKE_PCT = 3.0

STOP_LEVELS = [
    -2.0,
    -3.0,
    -4.0,
    -5.0,
]
''',
    '''TAKE_LEVELS = [
    2.0,
    3.0,
    4.0,
    5.0,
    7.0,
]

STOP_PCT = -5.0
''',
)

text = text.replace(
    '''def analyze_one(
    bars,
    stop_pct,
):''',
    '''def analyze_one(
    bars,
    take_pct,
):''',
)

text = text.replace(
    '''        * (1 + TAKE_PCT / 100)
''',
    '''        * (1 + take_pct / 100)
''',
)

text = text.replace(
    '''        * (1 + stop_pct / 100)
''',
    '''        * (1 + STOP_PCT / 100)
''',
)

text = text.replace(
    '''            ret = TAKE_PCT
''',
    '''            ret = take_pct
''',
)

text = text.replace(
    '''            ret = stop_pct
''',
    '''            ret = STOP_PCT
''',
)

text = text.replace(
    '''        ret = TAKE_PCT
''',
    '''        ret = take_pct
''',
)

text = text.replace(
    '''        ret = stop_pct
''',
    '''        ret = STOP_PCT
''',
)

text = text.replace(
    '''        for stop_pct in STOP_LEVELS:

            result = analyze_one(
                bars,
                stop_pct,
            )
''',
    '''        for take_pct in TAKE_LEVELS:

            result = analyze_one(
                bars,
                take_pct,
            )
''',
)

text = text.replace(
    '''                    "TakeProfitPct":
                        TAKE_PCT,
                    "StopLossPct":
                        stop_pct,
''',
    '''                    "TakeProfitPct":
                        take_pct,
                    "StopLossPct":
                        STOP_PCT,
''',
)

text = text.replace(
    '''    for stop_pct in STOP_LEVELS:

        g = out[
            out["StopLossPct"]
            == stop_pct
        ].copy()
''',
    '''    for take_pct in TAKE_LEVELS:

        g = out[
            out["TakeProfitPct"]
            == take_pct
        ].copy()
''',
)

text = text.replace(
    '''            f"TP +3 / SL {stop_pct:.0f}"
''',
    '''            f"TP +{take_pct:.0f} / SL -5"
''',
)

text = text.replace(
    '''        "J1 STOP COMPARISON "
''',
    '''        "J1 TAKE COMPARISON "
''',
)

dst.write_text(
    text,
    encoding="utf-8",
)

print(f"CREATED : {dst}")
