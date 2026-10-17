"""
Pure adapter for the H1 fixed live board.

No Excel connection, writing, or saving.
"""

from intraday.rss_h1_board_bridge import (
    board_rows_to_layout,
    build_h1_board_layout,
)


def prepare_h1_fixed_board(
    current_rows,
    h1_candidates,
    early_volume_map,
    snapshot_map,
    floor_to_tick,
    *,
    j1_codes=None,
    decision_enabled=False,
    growth_threshold=100.0,
    pullback_pct=-0.50,
):
    """
    Convert Morning Runner data to a complete
    fixed layout for rows 2-21.

    09:30: decision_enabled=False
    09:32: decision_enabled=True

    No workbook access.
    """

    current_layout = board_rows_to_layout(
        current_rows
    )

    return build_h1_board_layout(
        current_layout=current_layout,
        h1_codes=list(h1_candidates),
        j1_codes=j1_codes,
        early_volume_map=early_volume_map,
        snapshot_map=snapshot_map,
        floor_to_tick=floor_to_tick,
        decision_enabled=decision_enabled,
        growth_threshold=growth_threshold,
        pullback_pct=pullback_pct,
    )
