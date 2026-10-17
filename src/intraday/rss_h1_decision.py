def _safe_positive(value):
    try:
        number = float(value)
        if not (0 < number < float("inf")):
            return None
        return number
    except (TypeError, ValueError, OverflowError):
        return None


def build_h1_decisions(
    candidates,
    early_volume_map,
    snapshot_map,
    floor_to_tick,
    growth_threshold=100.0,
    pullback_pct=-0.50,
):
    """
    Build H1 TOP10 BUY/WAIT/NO DATA labels.

    Pure calculation:
      - No Excel connection
      - No file writing
      - No workbook save

    Returns:
        {code: "H1 #n BUY/WAIT/NO DATA"}
    """
    decisions = {}

    for rank, code in enumerate(candidates, start=1):
        code = str(code).strip()
        if code.endswith(".0"):
            code = code[:-2]

        # Preserve the first CxV rank for duplicate codes.
        if not code or code in decisions:
            continue

        early = _safe_positive(early_volume_map.get(code))
        saved = snapshot_map.get(code)

        if not isinstance(saved, dict):
            saved = {}

        volume = _safe_positive(saved.get("Volume"))
        price = _safe_positive(saved.get("Price"))

        if early is None or volume is None or price is None:
            decisions[code] = f"H1 #{rank} NO DATA"
            continue

        growth = (volume / early - 1.0) * 100.0

        if growth < growth_threshold:
            decisions[code] = f"H1 #{rank} BUY"
            continue

        limit = floor_to_tick(
            price * (1.0 + pullback_pct / 100.0)
        )

        if limit is None or limit != limit:
            decisions[code] = f"H1 #{rank} WAIT"
        elif float(limit).is_integer():
            decisions[code] = f"H1 #{rank} WAIT {int(limit)}"
        else:
            decisions[code] = f"H1 #{rank} WAIT {limit:g}"

    return decisions