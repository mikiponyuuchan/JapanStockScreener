"""
H1 fixed board preview.

Pure calculation only.
No Excel access, writing, or saving.
"""

from intraday.rss_h1_board_adapter import (
    prepare_h1_fixed_board,
)


def preview_h1_fixed_board(
    current_rows,
    h1_candidates,
    early_volume_map,
    snapshot_map,
    floor_to_tick,
    *,
    decision_enabled=False,
    growth_threshold=100.0,
    pullback_pct=-0.50,
):
    layout = prepare_h1_fixed_board(
        current_rows=current_rows,
        h1_candidates=h1_candidates,
        early_volume_map=early_volume_map,
        snapshot_map=snapshot_map,
        floor_to_tick=floor_to_tick,
        j1_codes=None,
        decision_enabled=decision_enabled,
        growth_threshold=growth_threshold,
        pullback_pct=pullback_pct,
    )

    stage = "09:32" if decision_enabled else "09:30"

    print()
    print("=" * 60)
    print(f" H1 FIXED BOARD DRY RUN {stage}")
    print("=" * 60)

    for row in range(2, 22):
        code, label = layout[row]
        print(
            f"ROW {row:02d} | "
            f"{str(code):<6} | {label}"
        )

    print("NO EXCEL ACCESS / NO WRITE / NO SAVE")

    return layout
