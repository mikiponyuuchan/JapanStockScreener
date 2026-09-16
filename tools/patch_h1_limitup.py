from pathlib import Path

FILES = [
    Path("tools/create_intraday_strategy_h1.py"),
    Path("tools/create_intraday_strategy_h1_early20.py"),
]

LIMIT_FUNC = r'''

def get_normal_limit_up_price(prev_close):
    """
    Calculate the normal TSE daily upper price limit
    from the reference price (normally previous close).

    NOTE:
    This handles the normal daily price-limit table only.
    Temporary expanded price limits are not handled.
    """
    try:
        price = float(prev_close)
    except (TypeError, ValueError):
        return None

    if pd.isna(price) or price <= 0:
        return None

    bands = [
        (100, 30),
        (200, 50),
        (500, 80),
        (700, 100),
        (1000, 150),
        (1500, 300),
        (2000, 400),
        (3000, 500),
        (5000, 700),
        (7000, 1000),
        (10000, 1500),
        (15000, 3000),
        (20000, 4000),
        (30000, 5000),
        (50000, 7000),
        (70000, 10000),
        (100000, 15000),
        (150000, 30000),
        (200000, 40000),
        (300000, 50000),
        (500000, 70000),
        (700000, 100000),
        (1000000, 150000),
        (1500000, 300000),
        (2000000, 400000),
        (3000000, 500000),
        (5000000, 700000),
        (7000000, 1000000),
        (10000000, 1500000),
        (15000000, 3000000),
        (20000000, 4000000),
        (30000000, 5000000),
        (50000000, 7000000),
    ]

    for upper, width in bands:
        if price < upper:
            return price + width

    return price + 10000000


def calc_limit_up_room_pct(snapshot_price, limit_up_price):
    try:
        price = float(snapshot_price)
        limit_price = float(limit_up_price)
    except (TypeError, ValueError):
        return None

    if (
        pd.isna(price)
        or pd.isna(limit_price)
        or price <= 0
    ):
        return None

    return (
        limit_price / price - 1.0
    ) * 100.0
'''

for path in FILES:
    text = path.read_text(encoding="utf-8")

    if '"LimitUpPrice"' not in text:
        text = text.replace(
            '    "CxV",\n'
            '    "TakeProfitPct",',
            '    "CxV",\n'
            '    "LimitUpPrice",\n'
            '    "LimitUpRoomPct",\n'
            '    "TakeProfitPct",',
            1,
        )

    if "def get_normal_limit_up_price(" not in text:
        marker = "\n\ndef "
        pos = text.find(marker)

        if pos == -1:
            raise RuntimeError(
                f"Function insertion point not found: {path}"
            )

        text = (
            text[:pos]
            + LIMIT_FUNC
            + text[pos:]
        )

    if '"PrevClose"' not in text.split("missing =", 1)[0]:
        text = text.replace(
            '        "MorningPrice",\n'
            '        "MorningChangePct",',
            '        "MorningPrice",\n'
            '        "PrevClose",\n'
            '        "MorningChangePct",',
            1,
        )

    if 'work["PrevCloseX"]' not in text:
        marker = '''    work["ChangeX"] = pd.to_numeric(
'''
        insert = '''    work["PrevCloseX"] = pd.to_numeric(
        work["PrevClose"],
        errors="coerce",
    )

    work["LimitUpPriceX"] = (
        work["PrevCloseX"]
        .map(get_normal_limit_up_price)
    )

    work["LimitUpRoomPctX"] = [
        calc_limit_up_room_pct(price, limit_price)
        for price, limit_price in zip(
            work["PriceX"],
            work["LimitUpPriceX"],
        )
    ]

'''
        text = text.replace(
            marker,
            insert + marker,
            1,
        )

    if '"LimitUpPrice": row["LimitUpPriceX"]' not in text:
        text = text.replace(
            '''                "CxV": row["CxV"],
''',
            '''                "CxV": row["CxV"],
                "LimitUpPrice": row["LimitUpPriceX"],
                "LimitUpRoomPct": row["LimitUpRoomPctX"],
''',
            1,
        )

        text = text.replace(
            '''                "CxV":
                    row["CxV"],
''',
            '''                "CxV":
                    row["CxV"],
                "LimitUpPrice":
                    row["LimitUpPriceX"],
                "LimitUpRoomPct":
                    row["LimitUpRoomPctX"],
''',
            1,
        )

    old_print = '''                f"CxV={row['CxV']:.2f}"
'''

    new_print = '''                f"CxV={row['CxV']:.2f} "
                f"LimitUp={row['LimitUpPrice']:.0f} "
                f"Room={row['LimitUpRoomPct']:.2f}%"
'''

    if old_print in text:
        text = text.replace(
            old_print,
            new_print,
            1,
        )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print(f"PATCHED : {path}")

print("PATCH OK")
