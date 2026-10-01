from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]

RUNNER = (
    ROOT
    / "src"
    / "intraday"
    / "rss_morning_runner.py"
)


def main():

    path = RUNNER

    text = path.read_text(
        encoding="utf-8"
    )

    # ============================================
    # Already patched check
    # ============================================

    if "def load_today_j1_live_board():" in text:
        print(
            "SKIP    : J1 live-board integration "
            "already exists"
        )
        print("COMPLETE")
        return

    # ============================================
    # Backup
    # ============================================

    backup_path = path.with_name(
        "rss_morning_runner"
        "_before_j1_live_board_v2.py"
    )

    if not backup_path.exists():
        shutil.copy2(
            path,
            backup_path,
        )

    print(
        "BACKUP  : "
        f"{backup_path.relative_to(ROOT)}"
    )

    # ============================================
    # 1. Extend rss_live_board import
    # ============================================

    old_import = """from rss_live_board import (
    get_live_board,
    clear_h1_labels,
    add_candidate,
    refresh_volume_master,
    refresh_expanded_price_limits,
)"""

    new_import = """from rss_live_board import (
    get_live_board,
    clear_h1_labels,
    clear_j1_labels,
    add_candidate,
    add_j1_live_board_codes,
    refresh_volume_master,
    refresh_expanded_price_limits,
)"""

    if old_import not in text:
        raise RuntimeError(
            "Expected rss_live_board import "
            "block was not found."
        )

    text = text.replace(
        old_import,
        new_import,
        1,
    )

    # ============================================
    # 2. Add J1 loader
    #
    # We use the date in the trade-plan filename.
    #
    # Example:
    #   2026-09-30_j1_trade_plan.csv
    #
    # The file is valid only when its date is the
    # latest weekday before today.
    #
    # This handles normal weekends.
    #
    # For Japanese holidays, the existing J1 plan
    # itself is used as the authoritative source:
    # among past plan files, use only the newest
    # plan and require that no newer plan exists.
    #
    # More importantly, we never use today's file:
    # J1 is NEXT_OPEN from the previous detection
    # session.
    # ============================================

    marker = "\ndef prepare_h1_hybrid_wait("

    if marker not in text:
        raise RuntimeError(
            "prepare_h1_hybrid_wait() "
            "marker was not found."
        )

    block = r'''

def load_today_j1_live_board():
    """
    Put the latest valid J1 NEXT_OPEN stocks
    on the RSS live board.

    J1 is detected from the previous session
    and entered at today's open.

    Source:
        data/trading/YYYY-MM-DD_j1_trade_plan.csv

    Today's own trade-plan file is never used.
    """

    print()
    print("=" * 60)
    print(" J1 LIVE BOARD")
    print("=" * 60)

    # Remove yesterday's J1 labels only.
    # H1 / SSR labels are preserved.
    clear_j1_labels()

    trading_dir = (
        ROOT
        / "data"
        / "trading"
    )

    if not trading_dir.exists():
        print(
            "J1 trading directory not found."
        )
        print("=" * 60)
        return []

    today = datetime.now().date()

    candidates = []

    for path in trading_dir.glob(
        "*_j1_trade_plan.csv"
    ):
        date_text = path.name[
            :10
        ]

        try:
            plan_date = datetime.strptime(
                date_text,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            continue

        # J1 uses the previous session's plan.
        # Never load a plan dated today or later.
        if plan_date >= today:
            continue

        candidates.append(
            (
                plan_date,
                path,
            )
        )

    if not candidates:
        print(
            "No previous J1 trade plan found."
        )
        print("=" * 60)
        return []

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    plan_date, plan_path = (
        candidates[0]
    )

    try:
        df = pd.read_csv(
            plan_path,
            dtype={
                "Code": str,
            },
        )
    except Exception as exc:
        print(
            "J1 plan read failed : "
            f"{exc}"
        )
        print("=" * 60)
        return []

    if df.empty:
        print(
            "J1 trade plan is empty."
        )
        print("=" * 60)
        return []

    if "Code" not in df.columns:
        print(
            "J1 trade plan has no Code column."
        )
        print("=" * 60)
        return []

    # Additional safety:
    # if DetectionDate exists, it must agree
    # with the plan filename.
    if "DetectionDate" in df.columns:

        detection_dates = pd.to_datetime(
            df["DetectionDate"],
            errors="coerce",
        )

        valid_dates = (
            detection_dates
            .dropna()
            .dt.date
        )

        if not valid_dates.empty:
            valid_df = df.loc[
                detection_dates
                .dt.date
                .eq(plan_date)
            ].copy()

            if valid_df.empty:
                print(
                    "J1 DetectionDate does not "
                    "match plan date."
                )
                print("=" * 60)
                return []

            df = valid_df

    codes = (
        df["Code"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    valid_mask = (
        codes.ne("")
        & codes.str.lower().ne("nan")
    )

    df = df.loc[
        valid_mask
    ].copy()

    codes = codes.loc[
        valid_mask
    ].tolist()

    print(
        "J1 plan date            : "
        f"{plan_date}"
    )

    print(
        "J1 plan                 : "
        f"{plan_path.name}"
    )

    print(
        "J1 stocks               : "
        f"{len(codes)}"
    )

    if "Name" in df.columns:
        names = (
            df["Name"]
            .fillna("")
            .astype(str)
            .tolist()
        )
    else:
        names = [
            ""
            for _ in codes
        ]

    for rank, (
        code,
        name,
    ) in enumerate(
        zip(
            codes,
            names,
        ),
        start=1,
    ):
        if name:
            print(
                f"  J1 #{rank} "
                f"{code} "
                f"{name}"
            )
        else:
            print(
                f"  J1 #{rank} "
                f"{code}"
            )

    add_j1_live_board_codes(
        codes
    )

    print("=" * 60)

    return codes
'''

    text = text.replace(
        marker,
        block + marker,
        1,
    )

    # ============================================
    # 3. Call it immediately after
    #    refresh_volume_master()
    # ============================================

    old_call = """    refresh_volume_master()

    # ============================================
    # Refresh today's JPX expanded price limits."""

    new_call = """    refresh_volume_master()

    # ============================================
    # J1 NEXT_OPEN live-board stocks.
    #
    # This is display-only.
    # It does not change J1 selection or trading
    # rules.
    # ============================================

    try:
        load_today_j1_live_board()

    except Exception as exc:
        print()
        print("=" * 60)
        print(" J1 LIVE BOARD")
        print("=" * 60)
        print(
            "J1 live-board update failed."
        )
        print(
            "Morning Runner will continue."
        )
        print(
            f"Reason : {exc}"
        )

    # ============================================
    # Refresh today's JPX expanded price limits."""

    if old_call not in text:
        raise RuntimeError(
            "refresh_volume_master() insertion "
            "point was not found."
        )

    text = text.replace(
        old_call,
        new_call,
        1,
    )

    # ============================================
    # Save
    # ============================================

    path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "PATCHED : "
        "J1 NEXT_OPEN live-board integration"
    )
    print(
        "PATCHED : "
        "src/intraday/rss_morning_runner.py"
    )
    print("COMPLETE")


if __name__ == "__main__":
    main()