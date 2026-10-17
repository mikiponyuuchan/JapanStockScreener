"""
Pure H1 board layout bridge.

No Excel connection, writes, or saves.
"""

from intraday.rss_h1_decision import build_h1_decisions
from intraday.rss_board_fixed_layout import build_fixed_layout



def board_rows_to_layout(current_rows):
    """
    Convert read_board() rows into a complete
    2-21 fixed layout. No Excel access.
    """
    layout = {
        row: ("", "")
        for row in range(2, 22)
    }

    seen = set()

    for item in current_rows:
        row = int(item["row"])

        if row not in layout:
            raise ValueError(f"Invalid board row: {row}")

        if row in seen:
            raise ValueError(f"Duplicate board row: {row}")

        seen.add(row)

        code = str(item.get("code") or "").strip()

        if code.endswith(".0"):
            code = code[:-2]

        label = str(item.get("label") or "").strip()

        if not code and label:
            raise ValueError(
                f"Label without stock code at row {row}"
            )

        layout[row] = (code, label)

    return layout

def build_h1_board_layout(
    current_layout,
    h1_codes,
    j1_codes,
    early_volume_map,
    snapshot_map,
    floor_to_tick,
    decision_enabled=False,
    growth_threshold=100.0,
    pullback_pct=-0.50,
):
    """
    Build the complete fixed board layout.

    decision_enabled=False:
        Display H1 CAND labels (09:30).

    decision_enabled=True:
        Display H1 BUY / WAIT / NO DATA (09:32).

    None for h1_codes or j1_codes preserves the
    corresponding existing section.
    """

    decisions = None

    if decision_enabled:
        if h1_codes is None:
            raise ValueError(
                "H1 codes required for decision update"
            )

        decisions = build_h1_decisions(
            candidates=h1_codes,
            early_volume_map=early_volume_map,
            snapshot_map=snapshot_map,
            floor_to_tick=floor_to_tick,
            growth_threshold=growth_threshold,
            pullback_pct=pullback_pct,
        )

    return build_fixed_layout(
        current_layout=current_layout,
        h1_codes=h1_codes,
        j1_codes=j1_codes,
        h1_decisions=decisions,
    )
