from pathlib import Path


def patch_file(path_str, early20=False):
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")

    original = text

    # ----------------------------------------
    # Early20: add FORWARD_START
    # ----------------------------------------
    if early20:
        old = 'START_DATE = "2026-09-07"'

        new = '''START_DATE = "2026-09-07"
FORWARD_START = "2026-09-04"'''

        if old not in text:
            raise RuntimeError(
                f"START_DATE pattern not found: {path}"
            )

        text = text.replace(
            old,
            new,
            1,
        )

        # ------------------------------------
        # Early20: VALIDATION -> FORWARD /
        # DEVELOPMENT
        # ------------------------------------
        old = '''    for rank, (_, row) in enumerate(
        top3.iterrows(),
        start=1,
    ):
        rows.append(
            {
                "StrategyVersion":
                    "H1-Early20",
                "DataType":
                    "VALIDATION",'''

        new = '''    for rank, (_, row) in enumerate(
        top3.iterrows(),
        start=1,
    ):
        data_type = (
            "FORWARD"
            if snapshot_date >= FORWARD_START
            else "DEVELOPMENT"
        )

        rows.append(
            {
                "StrategyVersion":
                    "H1-Early20",
                "DataType":
                    data_type,'''

        if old not in text:
            raise RuntimeError(
                f"DataType pattern not found: {path}"
            )

        text = text.replace(
            old,
            new,
            1,
        )

    # ----------------------------------------
    # Replace old TOP3 for recalculated
    # DetectionDate + SnapshotTime
    # ----------------------------------------
    old = '''    combined = pd.concat(
        [existing, incoming],
        ignore_index=True,
    )'''

    new = '''    # Recalculated snapshots must replace the old TOP3.
    #
    # If ranking conditions change, keeping old rows would leave
    # obsolete candidates in the tracking CSV.
    snapshot_keys = (
        incoming[
            [
                "DetectionDate",
                "SnapshotTime",
            ]
        ]
        .drop_duplicates()
    )

    if not existing.empty:
        existing = existing.merge(
            snapshot_keys.assign(
                _replace_snapshot=True
            ),
            on=[
                "DetectionDate",
                "SnapshotTime",
            ],
            how="left",
        )

        existing = existing[
            existing["_replace_snapshot"]
            .isna()
        ].drop(
            columns=["_replace_snapshot"]
        )

    combined = pd.concat(
        [existing, incoming],
        ignore_index=True,
    )'''

    if old not in text:
        raise RuntimeError(
            f"concat pattern not found: {path}"
        )

    text = text.replace(
        old,
        new,
        1,
    )

    if text == original:
        raise RuntimeError(
            f"No changes made: {path}"
        )

    backup = path.with_name(
        path.stem
        + "_before_top3_replace_fix.py"
    )

    backup.write_text(
        original,
        encoding="utf-8",
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print("PATCHED :", path)
    print("BACKUP  :", backup)


patch_file(
    "tools/create_intraday_strategy_h1.py"
)

patch_file(
    "tools/create_intraday_strategy_h1_early20.py",
    early20=True,
)
