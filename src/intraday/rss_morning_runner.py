# ================================================
# 楽天 MarketSpeed II RSS
# 朝ライブ 一発起動ランナー
#
# 既存 run_morning_live.py とは独立して動作する。
#
# 1. 09:20 morning_panel の生成を待つ
# 2. CxV 上位20を楽天RSS Excelへセット
# 3. 09:30～09:35を毎分05秒に保存
# ================================================

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
SRC = ROOT / "src"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from services.jpx_risk_filter import (
    filter_blocked_stocks,
)
from services.yahoo_service import (
    get_expected_market_date,
)

from rss_watchlist import (
    read_panel,
    build_watchlist,
    write_excel,
)
from volume_tracker import (
    build_snapshot,
    save_snapshot,
)
from rss_reader import read_rss_rows
from rss_excel import ensure_rss_workbooks
from rss_live_board import (
    get_live_board,
    read_board_preview_safe,
    clear_h1_labels,
    clear_j1_labels,
    add_candidate,
    add_j1_live_board_codes,
    refresh_volume_master,
    refresh_expanded_price_limits,
)
from run_morning_screener_rss import build_morning_panel
from analyze_h1_true_pullback_entry import floor_to_tick
from intraday.rss_h1_board_preview import preview_h1_fixed_board


# H1 fixed-board preview (disabled by default).
# No Excel access in the preview itself.
H1_FIXED_BOARD_DRY_RUN = False

# Production fixed-board switch.
# Keep False until integration tests and Excel verification pass.
H1_FIXED_BOARD_WRITE_ENABLED = False


def update_h1_fixed_board_live(*, decision_enabled):
    """
    Update the H1 fixed board using verified backup,
    guarded cell writes and one workbook save.

    Never called while the production switch is False.
    """
    if not H1_FIXED_BOARD_WRITE_ENABLED:
        raise RuntimeError(
            "H1 fixed-board production write is disabled"
        )

    from intraday.rss_h1_board_adapter import (
        prepare_h1_fixed_board,
    )
    from intraday.rss_board_transaction import (
        execute_and_save_verified_board,
    )

    excel, book, sheet = get_live_board()

    current_rows = [
        {
            "row": row,
            "code": sheet.Cells(row, 1).Value,
            "label": sheet.Cells(row, 8).Value,
        }
        for row in range(2, 22)
    ]

    layout = prepare_h1_fixed_board(
        current_rows=current_rows,
        h1_candidates=H1_CANDIDATES,
        early_volume_map=H1_EARLY_VOLUME,
        snapshot_map=H1_0930_SNAPSHOT,
        floor_to_tick=floor_to_tick,
        j1_codes=J1_CODES,
        decision_enabled=decision_enabled,
        growth_threshold=H1_WAIT_GROWTH_THRESHOLD,
        pullback_pct=H1_WAIT_PULLBACK_LEVEL,
    )

    backup_dir = (
        Path("data")
        / "intraday"
        / "board_backups"
    )

    return execute_and_save_verified_board(
        excel,
        book,
        sheet,
        layout,
        backup_dir,
        dry_run=False,
    )


J1_CODES = []


def preview_h1_runner_board(*, decision_enabled):
    if not H1_FIXED_BOARD_DRY_RUN:
        return

    current_rows = read_board_preview_safe()

    if not current_rows:
        raise RuntimeError(
            "H1 PREVIEW BLOCKED: existing board is empty"
        )

    preview_h1_fixed_board(
        current_rows=current_rows,
        h1_candidates=H1_CANDIDATES,
        j1_codes=J1_CODES,
        early_volume_map=H1_EARLY_VOLUME,
        snapshot_map=H1_0930_SNAPSHOT,
        floor_to_tick=floor_to_tick,
        decision_enabled=decision_enabled,
        growth_threshold=H1_WAIT_GROWTH_THRESHOLD,
        pullback_pct=H1_WAIT_PULLBACK_LEVEL,
    )


MORNING_DIR = Path(
    "data/analysis/morning"
)

PANEL_START = (9, 20)
PANEL_END = (9, 25)

CAPTURE_START = (9, 30)
CAPTURE_END = (9, 35)

CAPTURE_SECOND = 5

PANEL_CHECK_INTERVAL = 5


# ================================================
# H1 HYBRID WAIT
#
# VolumeRatioGrowthPct < 100%
#     -> BUY at 09:30
#
# VolumeRatioGrowthPct >= 100%
#     -> WAIT at -0.50% pullback
#
# The decision is fixed at the first 09:30 capture.
# ================================================

H1_WAIT_GROWTH_THRESHOLD = 100.0
H1_WAIT_PULLBACK_LEVEL = -0.50

# 09:32 refill filter.
#
# PASS:
#     -3.00% <= move from 09:30 <= +1.00%
#
# Final stocks are selected in the original
# 09:30 CxV ranking order.
H1_FILTER_HOUR = 9
H1_FILTER_MINUTE = 32
H1_FILTER_SECOND = 2

H1_FILTER_LOWER = -3.0
H1_FILTER_UPPER = 1.0

H1_MAX_SELECTED = 3

H1_0932_REFILL_LOG_FILE = (
    ROOT
    / "data"
    / "tracking"
    / "h1_0932_refill_log.csv"
)

H1_EARLY_VOLUME = {}
H1_TOP3_RANK = {}
H1_HYBRID_DECISION_DONE = False

# 09:30 full-market CxV TOP10 candidate pool.
H1_CANDIDATES = []

# Preserve the 09:30 RSS price/volume for the
# candidates.  BUY / WAIT is decided later, after
# the 09:32 PASS / SKIP refill selection, but it
# must still use the original 09:20 -> 09:30 growth.
H1_0930_SNAPSHOT = {}



# ================================================
# Microsoft Excel / RSS workbook preparation
# ================================================

def prepare_rss_excel():
    """
    Prepare the dedicated Microsoft Excel instance
    and all Rakuten RSS workbooks.

    WPS / Kingsoft is ignored by rss_excel.
    """
    print()
    print("=" * 60)
    print(" MICROSOFT EXCEL PREPARE")
    print("=" * 60)

    excel, results = ensure_rss_workbooks()

    print(
        "Microsoft Excel COM       : OK"
    )
    print(
        f"Microsoft Excel Version   : "
        f"{excel.Version}"
    )
    print(
        f"Microsoft Excel Path      : "
        f"{excel.Path}"
    )

    for workbook_name, status in (
        results.items()
    ):
        print(
            f"{workbook_name:<34}: "
            f"{status}"
        )

    print(
        "RSS Excel preparation     : OK"
    )
    print("=" * 60)

    return excel


# ================================================
# 時刻生成
# ================================================

def today_at(
    hour,
    minute,
    second=0,
):
    now = datetime.now()

    return now.replace(
        hour=hour,
        minute=minute,
        second=second,
        microsecond=0,
    )


# ================================================
# 本日の09:20～09:25 panel検索
# ================================================

def find_today_panel():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    candidates = []

    for path in MORNING_DIR.glob(
        f"{today}_*_morning_panel.csv"
    ):

        parts = path.stem.split("_")

        if len(parts) < 2:
            continue

        hhmm = parts[1]

        if (
            len(hhmm) != 4
            or not hhmm.isdigit()
        ):
            continue

        hour = int(
            hhmm[:2]
        )

        minute = int(
            hhmm[2:]
        )

        total_minutes = (
            hour * 60
            + minute
        )

        start_minutes = (
            PANEL_START[0] * 60
            + PANEL_START[1]
        )

        end_minutes = (
            PANEL_END[0] * 60
            + PANEL_END[1]
        )

        if (
            start_minutes
            <= total_minutes
            <= end_minutes
        ):
            candidates.append(
                (
                    total_minutes,
                    path,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (
            x[0],
            str(x[1]),
        )
    )

    return candidates[0][1]


# ================================================
# panel待機
# ================================================

def wait_for_panel():

    panel_deadline = today_at(
        PANEL_END[0],
        PANEL_END[1],
        59,
    )

    while True:

        path = find_today_panel()

        if path is not None:
            return path

        now = datetime.now()

        if now > panel_deadline:
            return None

        # 5秒ごとの待機ログは表示しない。
        # panelの存在確認自体は従来どおり5秒ごとに行う。
        time.sleep(
            PANEL_CHECK_INTERVAL
        )


# ================================================
# 1スロット取得
# ================================================

def _safe_float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result != result:
        return None

    return result



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

    # J1 must use exactly the previous market session.
    # Do not fall back to an older trade plan.
    expected_plan_date = (
        get_expected_market_date()
        .date()
    )

    plan_path = (
        trading_dir
        / (
            f"{expected_plan_date:%Y-%m-%d}"
            "_j1_trade_plan.csv"
        )
    )

    if not plan_path.exists():
        print(
            "No J1 trade plan for previous session :",
            expected_plan_date,
        )
        print("=" * 60)
        return []

    plan_date = expected_plan_date

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

def prepare_h1_hybrid_wait(
    panel_df,
    h1_top3=None,
):
    """
    Store the 09:20-side volume for the full market.

    Candidate selection is NOT fixed at 09:20.
    The H1 candidates will be selected from the
    fresh 09:30 full-market CxV ranking.

    H1_TOP3_RANK is intentionally left empty here.
    It will be populated after the 09:30 candidates
    and refill selection are determined.
    """

    global H1_EARLY_VOLUME
    global H1_TOP3_RANK
    global H1_HYBRID_DECISION_DONE

    H1_EARLY_VOLUME = {}
    H1_TOP3_RANK = {}
    H1_HYBRID_DECISION_DONE = False

    if panel_df is None or panel_df.empty:
        print(
            "H1 hybrid WAIT prepare skipped: "
            "panel is empty."
        )
        return

    required = [
        "Code",
        "MorningVolume",
    ]

    missing = [
        col
        for col in required
        if col not in panel_df.columns
    ]

    if missing:
        raise RuntimeError(
            "H1 early-volume columns missing : "
            + ", ".join(missing)
        )

    valid_count = 0

    for _, row in panel_df.iterrows():

        code = str(
            row["Code"]
        ).strip()

        if code.endswith(".0"):
            code = code[:-2]

        if not code:
            continue

        early_volume = _safe_float(
            row.get(
                "MorningVolume"
            )
        )

        if (
            early_volume is None
            or early_volume <= 0
        ):
            continue

        H1_EARLY_VOLUME[
            code
        ] = early_volume

        valid_count += 1

    print()
    print("=" * 60)
    print(" H1 EARLY FULL-MARKET VOLUME")
    print("=" * 60)
    print(
        "09:20 valid volumes : "
        f"{valid_count}"
    )
    print(
        "Candidate selection : "
        "NOT FIXED AT 09:20"
    )


def update_h1_hybrid_wait_live():
    """
    Decide BUY / WAIT for the final refill-selected stocks.

    IMPORTANT:
    PASS / SKIP has already been decided separately.

    BUY / WAIT uses:
        09:20 early volume
        versus
        stored 09:30 volume

    BUY:
        growth < 100%

    WAIT:
        growth >= 100%
        limit = floor_to_tick(
            Price0930 * 0.995
        )
    """

    global H1_HYBRID_DECISION_DONE

    if H1_HYBRID_DECISION_DONE:
        return

    print()
    print("=" * 60)
    print(" H1 HYBRID BUY / WAIT")
    print("=" * 60)

    if not H1_CANDIDATES:
        print(
            "No H1 TOP10 candidates."
        )

        if H1_FIXED_BOARD_WRITE_ENABLED:
            update_h1_fixed_board_live(
                decision_enabled=True,
            )

        H1_HYBRID_DECISION_DONE = True
        print("=" * 60)
        return

    # BUY / WAIT is displayed for the full
    # 09:30 CxV TOP10 candidate pool.
    #
    # IMPORTANT:
    # H1_TOP3_RANK and H1_MAX_SELECTED remain
    # unchanged.  They continue to represent
    # the formal refill-selected TOP3.
    for rank, code in enumerate(
        H1_CANDIDATES,
        start=1,
    ):
        early_volume = H1_EARLY_VOLUME.get(
            code
        )

        saved = H1_0930_SNAPSHOT.get(
            code
        )

        if (
            early_volume is None
            or early_volume <= 0
        ):
            print(
                f"H1 #{rank} {code} "
                "BUY/WAIT NO DATA : "
                "early volume unavailable"
            )

            if not H1_FIXED_BOARD_WRITE_ENABLED:
                add_candidate(
                    code,
                    f"H1 #{rank} NO DATA",
                )
            continue

        if not saved:
            print(
                f"H1 #{rank} {code} "
                "BUY/WAIT NO DATA : "
                "09:30 snapshot unavailable"
            )

            if not H1_FIXED_BOARD_WRITE_ENABLED:
                add_candidate(
                    code,
                    f"H1 #{rank} NO DATA",
                )
            continue

        volume_0930 = _safe_float(
            saved.get("Volume")
        )

        price_0930 = _safe_float(
            saved.get("Price")
        )

        if (
            volume_0930 is None
            or volume_0930 <= 0
            or price_0930 is None
            or price_0930 <= 0
        ):
            print(
                f"H1 #{rank} {code} "
                "BUY/WAIT NO DATA : "
                "invalid 09:30 price/volume"
            )

            if not H1_FIXED_BOARD_WRITE_ENABLED:
                add_candidate(
                    code,
                    f"H1 #{rank} NO DATA",
                )
            continue

        growth = (
            volume_0930
            / early_volume
            - 1.0
        ) * 100.0

        if growth >= H1_WAIT_GROWTH_THRESHOLD:

            raw_limit = (
                price_0930
                * (
                    1.0
                    + H1_WAIT_PULLBACK_LEVEL
                    / 100.0
                )
            )

            limit_price = floor_to_tick(
                raw_limit
            )

            if (
                limit_price is None
                or limit_price != limit_price
            ):
                label = (
                    f"H1 #{rank} WAIT"
                )
                price_text = "N/A"

            else:
                if float(
                    limit_price
                ).is_integer():
                    price_text = str(
                        int(limit_price)
                    )
                else:
                    price_text = (
                        f"{limit_price:g}"
                    )

                label = (
                    f"H1 #{rank} "
                    f"WAIT {price_text}"
                )

            decision = "WAIT"

        else:
            label = (
                f"H1 #{rank} BUY"
            )
            decision = "BUY"
            price_text = "-"

        if not H1_FIXED_BOARD_WRITE_ENABLED:
            # Excel COM may temporarily reject a live-board
            # write while Rakuten RSS / Excel is busy.
            add_max_retries = 20
            add_retry_wait = 0.25
            add_last_error = None

            for add_attempt in range(
                1,
                add_max_retries + 1,
            ):
                try:
                    add_candidate(
                        code,
                        label,
                    )
                    add_last_error = None

                    if add_attempt > 1:
                        print(
                            "  H1 live-board write recovered "
                            f"after {add_attempt - 1} retries"
                        )

                    break

                except Exception as exc:
                    add_last_error = exc

                    if add_attempt >= add_max_retries:
                        break

                    if add_attempt == 1:
                        print(
                            "  H1 live-board COM busy "
                            "- retrying..."
                        )

                    import time
                    time.sleep(
                        add_retry_wait
                    )

            if add_last_error is not None:
                raise RuntimeError(
                    "H1 live-board write failed after "
                    f"{add_max_retries} retries : "
                    f"{add_last_error}"
                ) from add_last_error

        print(
            f"H1 #{rank} "
            f"{code} "
            f"Growth={growth:+.2f}% "
            f"Price0930={price_0930:g} "
            f"=> {decision}"
            + (
                f" {price_text}"
                if decision == "WAIT"
                else ""
            )
        )

    if H1_FIXED_BOARD_WRITE_ENABLED:
        update_h1_fixed_board_live(
            decision_enabled=True,
        )

    H1_HYBRID_DECISION_DONE = True

    print("=" * 60)


def run_h1_0932_refill_filter():
    """
    At 09:32:02:

    1. Read current Rakuten RSS values for TOP20.
    2. Check the 09:30 CxV TOP10 candidates.
    3. PASS when move from stored 09:30 price is
       between -3.00% and +1.00%, inclusive.
    4. Keep PASS stocks in original CxV rank order.
    5. Select at most three stocks.
    6. Run the separate BUY / WAIT decision using
       stored 09:20 -> 09:30 volume growth.
    """

    global H1_TOP3_RANK

    print()
    print("=" * 60)
    print(" H1 09:32 REFILL FILTER")
    print("=" * 60)

    rows = read_rss_rows()

    rss_map = {}

    for row in rows:
        code = str(
            row.get("Code", "")
        ).strip()

        if code.endswith(".0"):
            code = code[:-2]

        if code:
            rss_map[code] = row

    pass_codes = []
    filter_rows = []

    filter_now = datetime.now()
    detection_date = filter_now.strftime(
        "%Y-%m-%d"
    )
    filter_time = filter_now.strftime(
        "%H:%M:%S"
    )

    for cxv_rank, code in enumerate(
        H1_CANDIDATES,
        start=1,
    ):
        saved = H1_0930_SNAPSHOT.get(
            code
        )

        current = rss_map.get(
            code
        )

        base_price = (
            _safe_float(
                saved.get("Price")
            )
            if saved
            else None
        )

        current_price = (
            _safe_float(
                current.get("Price")
            )
            if current
            else None
        )

        if (
            base_price is None
            or base_price <= 0
            or current_price is None
            or current_price <= 0
        ):
            result = "NO DATA"
            move_pct = None

        else:
            move_pct = (
                current_price
                / base_price
                - 1.0
            ) * 100.0

            passed = (
                H1_FILTER_LOWER
                <= move_pct
                <= H1_FILTER_UPPER
            )

            result = (
                "PASS"
                if passed
                else "SKIP"
            )

        if result == "PASS":
            pass_codes.append(
                code
            )

        move_text = (
            "N/A"
            if move_pct is None
            else f"{move_pct:+.2f}%"
        )

        print(
            f"CxV #{cxv_rank:2d} "
            f"{code} "
            f"09:30={base_price} "
            f"09:32={current_price} "
            f"Move={move_text} "
            f"=> {result}"
        )

        filter_rows.append(
            {
                "DetectionDate":
                    detection_date,
                "FilterTime":
                    filter_time,
                "CxVRank":
                    cxv_rank,
                "Code":
                    code,
                "Price0930":
                    base_price,
                "Price0932":
                    current_price,
                "MovePct":
                    move_pct,
                "FilterResult":
                    result,
                "H1Rank":
                    None,
            }
        )

    selected = (
        pass_codes[
            :H1_MAX_SELECTED
        ]
    )

    H1_TOP3_RANK = {
        code: rank
        for rank, code in enumerate(
            selected,
            start=1,
        )
    }

    print()
    print("Refill selected:")

    if not selected:
        print("  NONE")

    for rank, code in enumerate(
        selected,
        start=1,
    ):
        original_rank = (
            H1_CANDIDATES.index(code)
            + 1
        )

        print(
            f"  H1 #{rank} "
            f"{code} "
            f"(CxV #{original_rank})"
        )

    # ============================================
    # Save 09:32 refill audit log.
    # ============================================

    for row in filter_rows:
        code = row["Code"]

        if code in H1_TOP3_RANK:
            row["H1Rank"] = H1_TOP3_RANK[code]

    if filter_rows:
        log_df = pd.DataFrame(filter_rows)

        H1_0932_REFILL_LOG_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if H1_0932_REFILL_LOG_FILE.exists():
            old_df = pd.read_csv(
                H1_0932_REFILL_LOG_FILE,
                dtype={"Code": str},
                low_memory=False,
            )

            log_df = pd.concat(
                [old_df, log_df],
                ignore_index=True,
            )

            log_df = log_df.drop_duplicates(
                subset=[
                    "DetectionDate",
                    "CxVRank",
                    "Code",
                ],
                keep="last",
            )

        log_df.to_csv(
            H1_0932_REFILL_LOG_FILE,
            index=False,
            encoding="utf-8-sig",
        )

        print()
        print(
            "H1 09:32 refill log : "
            f"{H1_0932_REFILL_LOG_FILE}"
        )

    # Fixed-board preview only (no Excel access).
    preview_h1_runner_board(decision_enabled=True)

    # Remove temporary candidate labels.
    # Only final selected stocks receive H1 labels.
    if not H1_FIXED_BOARD_WRITE_ENABLED:
        clear_h1_labels()

    # PASS/SKIP selection is complete.
    # BUY/WAIT is a separate decision.
    update_h1_hybrid_wait_live()


def capture_slot(
    target_time,
):

    actual_now = datetime.now()

    df = build_snapshot(
        actual_now
    )

    if df.empty:

        print(
            f"[{target_time:%H:%M}] "
            "RSSデータなし"
        )

        return

    # --------------------------------------------------------
    # Preserve the 09:30 RSS values.
    #
    # Do NOT decide BUY / WAIT here.
    # Final H1 stocks are selected by the 09:32
    # PASS / SKIP refill filter first.
    # --------------------------------------------------------

    if (
        target_time.hour == 9
        and target_time.minute == 30
    ):
        global H1_0930_SNAPSHOT

        H1_0930_SNAPSHOT = {}

        normalized_codes = (
            df["Code"]
            .astype(str)
            .str.strip()
            .str.replace(
                r"\.0$",
                "",
                regex=True,
            )
        )

        for i, row in df.iterrows():
            code = normalized_codes.loc[i]

            if code not in H1_CANDIDATES:
                continue

            price = _safe_float(
                row.get("Price")
            )

            volume = _safe_float(
                row.get("Volume")
            )

            H1_0930_SNAPSHOT[code] = {
                "Price": price,
                "Volume": volume,
            }

        print()
        print(
            "H1 09:30 candidate snapshot : "
            f"{len(H1_0930_SNAPSHOT)} / "
            f"{len(H1_CANDIDATES)}"
        )

    # 実際の取得秒が多少ずれても
    # 比較用スロットは予定時刻に固定
    df["TimeSlot"] = (
        target_time.strftime(
            "%H:%M"
        )
    )

    output_path = save_snapshot(
        df,
        actual_now,
        test_mode=False,
    )

    print(
        f"[{target_time:%H:%M}] "
        f"{len(df)}銘柄保存 "
        f"実取得={actual_now:%H:%M:%S}"
    )

    print(
        "保存先 :",
        output_path,
    )


# ================================================
# 09:30～09:35取得
# ================================================

def run_capture():

    capture_times = []

    for minute in range(
        CAPTURE_START[1],
        CAPTURE_END[1] + 1,
    ):

        capture_times.append(
            today_at(
                CAPTURE_START[0],
                minute,
                CAPTURE_SECOND,
            )
        )

    print()
    print("=" * 60)
    print(" RSS VOLUME CAPTURE")
    print("=" * 60)

    print(
        "取得予定 : "
        "09:30:05 ～ 09:35:05"
    )

    filter_done = False

    filter_target = today_at(
        H1_FILTER_HOUR,
        H1_FILTER_MINUTE,
        H1_FILTER_SECOND,
    )

    for target_time in capture_times:

        now = datetime.now()

        # Run the refill filter before the first
        # capture scheduled after 09:32:02.
        if (
            not filter_done
            and target_time >= filter_target
        ):
            now = datetime.now()

            if now < filter_target:
                wait_seconds = (
                    filter_target - now
                ).total_seconds()

                print(
                    "[09:32 FILTER] "
                    f"待機 {wait_seconds:.1f} 秒"
                )

                if wait_seconds > 0:
                    time.sleep(
                        wait_seconds
                    )

            try:
                run_h1_0932_refill_filter()

            except Exception as exc:
                print(
                    "H1 09:32 refill filter "
                    f"failed : {exc}"
                )

                if H1_FIXED_BOARD_WRITE_ENABLED:
                    raise RuntimeError(
                        "H1 FIXED BOARD FAILURE: "
                        "stop runner; inspect Excel and backup. "
                        "Do not retry automatically."
                    ) from exc

            filter_done = True

        now = datetime.now()

        if now > target_time:

            print(
                f"[{target_time:%H:%M}] "
                "取得時刻経過のためスキップ"
            )

            continue

        wait_seconds = (
            target_time - now
        ).total_seconds()

        print(
            f"[{target_time:%H:%M}] "
            f"待機 {wait_seconds:.1f} 秒"
        )

        if wait_seconds > 0:
            time.sleep(
                wait_seconds
            )

        try:
            capture_slot(
                target_time
            )

        except Exception as exc:
            print(
                f"[{target_time:%H:%M}] "
                f"取得失敗 : {exc}"
            )

            print(
                "次の取得時刻へ継続します。"
            )


# ================================================
# メイン
# ================================================

def check_rss_startup():
    """
    Check both Rakuten RSS workbooks before
    entering the morning wait.
    """

    print()
    print("=" * 60)
    print(" RSS STARTUP CHECK")
    print("=" * 60)

    # ----------------------------------------
    # H1 RSS workbook + actual RSS data
    # ----------------------------------------
    try:
        rows = read_rss_rows()

    except Exception as exc:
        print(
            "rakuten_rss_morning.xlsx / 楽天RSS_H1      : NG"
        )
        print(
            "rakuten_rss_morning.xlsx / H1ライブボード : NOT CHECKED"
        )
        print()
        print(
            "H1 RSS check failed:"
        )
        print(exc)

        raise RuntimeError(
            "RSS startup check failed."
        ) from exc

    row_count = len(rows)

    print(
        "rakuten_rss_morning.xlsx / 楽天RSS_H1      : OK"
    )
    print(
        f"RSS data rows               : {row_count}"
    )

    if row_count == 0:
        raise RuntimeError(
            "RSS startup check failed: "
            "RSS data rows = 0"
        )

    # ----------------------------------------
    # Live board workbook
    # ----------------------------------------
    try:
        _, book, sheet = get_live_board()

        # Force a real COM read.
        book_name = book.Name
        sheet_name = sheet.Name

    except Exception as exc:
        print(
            "rakuten_rss_morning.xlsx / H1ライブボード : NG"
        )
        print()
        print(
            "Live board check failed:"
        )
        print(exc)

        raise RuntimeError(
            "RSS live board startup check failed."
        ) from exc

    print(
        "rakuten_rss_morning.xlsx / H1ライブボード : OK"
    )
    print(
        f"Live board sheet            : {sheet_name}"
    )

    print(
        "Startup check               : OK"
    )
    print("=" * 60)

    return row_count


def main():

    now = datetime.now()

    print("=" * 60)
    print(
        " 楽天RSS MORNING RUNNER"
    )
    print("=" * 60)

    print(
        "Start :",
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    final_time = today_at(
        CAPTURE_END[0],
        CAPTURE_END[1],
        CAPTURE_SECOND,
    )

    if now > final_time:

        print(
            "本日のRSS朝取得時間は"
            "終了しています。"
        )

        return

    # ============================================
    # RSS startup retry
    #
    # Excel / Rakuten RSS COM may temporarily point
    # to another Excel instance or reject COM calls.
    # Do not terminate the morning runner for a
    # temporary startup failure.
    #
    # Keep retrying until the RSS workbooks become
    # available or today's capture window ends.
    # ============================================

    startup_retry_seconds = 5

    while True:

        try:
            prepare_rss_excel()
            check_rss_startup()
            break

        except Exception as exc:

            retry_now = datetime.now()

            if retry_now > final_time:
                print()
                print(
                    "RSS startup check could not "
                    "recover before the end of "
                    "today's capture window."
                )
                print(
                    "Morning Runner : END"
                )
                return

            print()
            print(
                "RSS startup check temporarily failed."
            )
            print(
                "Morning Runner will continue."
            )
            print(
                f"Retry in {startup_retry_seconds} sec..."
            )
            print(
                f"Reason : {exc}"
            )

            time.sleep(
                startup_retry_seconds
            )

    # ============================================
    # Refresh live-board volume master.
    #
    # Use the latest morning_baseline.csv so
    # VolumeRatio / CxV work for current stocks.
    # ============================================

    print()
    print("=" * 60)
    print(" LIVE BOARD VOLUME MASTER")
    print("=" * 60)

    refresh_volume_master()

    # ============================================
    # J1 NEXT_OPEN live-board stocks.
    #
    # This is display-only.
    # It does not change J1 selection or trading
    # rules.
    # ============================================

    global J1_CODES
    J1_CODES = []

    # J1 live-board loading disabled.
    # H1-only morning operation.
    # Keep load_today_j1_live_board() for rollback.
    print("J1 LIVE BOARD : DISABLED (H1-only mode)")

    # ============================================
    # Refresh today's JPX expanded price limits.
    #
    # This must never stop the Morning Runner.
    # The helper automatically falls back to the
    # normal TSE price-limit formula.
    # ============================================

    print()
    print("=" * 60)
    print(" JPX EXPANDED PRICE LIMIT")
    print("=" * 60)

    try:
        refresh_expanded_price_limits()
    except Exception as exc:
        print(
            "Expanded price-limit refresh failed."
        )
        print(
            "Morning Runner will continue."
        )
        print(
            f"Reason : {exc}"
        )

    # ============================================
    # Load the 09:20-side full-market panel.
    #
    # Candidate selection is NOT performed here.
    # We only preserve the early cumulative volume
    # for every valid stock so that stocks which
    # newly rise into the H1 ranking at 09:30 can
    # still receive the BUY / WAIT judgment.
    # ============================================

    early_scan_start = today_at(
        9,
        20,
        0,
    )

    now = datetime.now()

    if now < early_scan_start:

        wait_seconds = (
            early_scan_start - now
        ).total_seconds()

        print()
        print(
            "Rakuten RSS early full-market scan "
            "starts at 09:20:00"
        )
        print(
            f"Waiting : {wait_seconds:.1f} sec"
        )

        time.sleep(
            wait_seconds
        )

    print()
    print("=" * 60)
    print(" H1 EARLY PANEL")
    print("=" * 60)

    print(
        "Rakuten RSS 09:20 full-market "
        "scan starting..."
    )

    early_panel_path = build_morning_panel(
        output_suffix="h1_early_rss",
    )

    if early_panel_path is None:
        print(
            "09:20 Rakuten RSS morning_panel "
            "was not created."
        )
        print(
            "H1 BUY / WAIT cannot be "
            "calculated safely."
        )
        return

    print(
        "09:20 Rakuten RSS panel :",
        early_panel_path,
    )

    early_panel_df = read_panel(
        early_panel_path
    )

    prepare_h1_hybrid_wait(
        early_panel_df
    )

    # ============================================
    # Wait until 09:30 for the full-market scan
    # ============================================

    scan_start = today_at(
        9,
        30,
        0,
    )

    now = datetime.now()

    if now < scan_start:

        wait_seconds = (
            scan_start - now
        ).total_seconds()

        print()
        print(
            "Rakuten RSS full-market scan "
            "starts at 09:30:00"
        )
        print(
            f"Waiting : {wait_seconds:.1f} sec"
        )

        time.sleep(
            wait_seconds
        )


    print()
    print(
        "Rakuten RSS full-market scan starting..."
    )

    print()
    print("=" * 60)
    print(" RAKUTEN RSS FULL MARKET SCAN")
    print("=" * 60)

    panel_path = build_morning_panel()

    if panel_path is None:

        print(
            "Rakuten RSS morning_panelが"
            "見つかりませんでした。"
        )

        return

    # ============================================
    # Build CxV TOP20 from the full-market panel.
    # ============================================

    panel_df = read_panel(
        panel_path
    )

    # JPX risk filter
    # BLOCK stocks are removed before CxV ranking.
    # WARN stocks remain tradable.
    panel_df = filter_blocked_stocks(
        panel_df,
        code_column="Code",
        verbose=True,
    )

    watchlist = build_watchlist(
        panel_df
    )

    if watchlist.empty:
        print(
            "CxV TOP20 watchlist is empty."
        )
        return

    print()
    print("=" * 60)
    print(" CxV TOP20")
    print("=" * 60)

    for rank, (_, row) in enumerate(
        watchlist.iterrows(),
        start=1,
    ):
        print(
            f"{rank:2d} "
            f"{row['CodeX']} "
            f"{row['NameX']} "
            f"Change={row['ChangeX']:.2f}% "
            f"VolumeRatio={row['VolumeX']:.2f} "
            f"CxV={row['CxV']:.2f}"
        )

    print()
    print(
        "Loading CxV TOP20 into "
        "Rakuten RSS H1 workbook..."
    )

    # ============================================
    # H1 workbook : CxV TOP20
    #
    # rakuten_rss_morning.xlsx / 楽天RSS_H1 の A2:E21 を
    # TOP20 + RSS式で更新する。
    # ============================================

    write_excel(
        watchlist
    )

    print(
        "H1 TOP20 workbook update : OK"
    )

    # ============================================
    # H1 09:30 candidate pool
    #
    # Do not fix the final TOP3 yet.
    # Keep the CxV TOP10 so that skipped stocks
    # can be replaced by the next ranked stock.
    # ============================================

    h1_candidates = (
        watchlist
        .head(10)
        .copy()
    )

    global H1_CANDIDATES
    global H1_0930_SNAPSHOT

    H1_CANDIDATES = [
        str(code).strip().replace(
            ".0",
            "",
        )
        for code
        in h1_candidates["CodeX"].tolist()
    ]

    # ============================================
    # Preserve the 09:30 full-market scan values.
    #
    # The full-market Rakuten RSS scan can finish
    # after 09:30:05.  Therefore the normal capture
    # slot may already have been missed.
    #
    # Use the values already stored in the 09:30
    # morning panel as the authoritative base for
    # the later 09:32 refill filter and BUY/WAIT.
    # ============================================

    H1_0930_SNAPSHOT = {}

    panel_code_map = {}

    for _, panel_row in panel_df.iterrows():

        code = str(
            panel_row.get("Code", "")
        ).strip()

        if code.endswith(".0"):
            code = code[:-2]

        if code:
            panel_code_map[code] = panel_row

    for code in H1_CANDIDATES:

        panel_row = panel_code_map.get(
            code
        )

        if panel_row is None:
            continue

        price = _safe_float(
            panel_row.get("MorningPrice")
        )

        volume = _safe_float(
            panel_row.get("MorningVolume")
        )

        if (
            price is None
            or price <= 0
            or volume is None
            or volume < 0
        ):
            continue

        H1_0930_SNAPSHOT[code] = {
            "Price": price,
            "Volume": volume,
        }

    print()
    print(
        "H1 09:30 panel snapshot : "
        f"{len(H1_0930_SNAPSHOT)} / "
        f"{len(H1_CANDIDATES)}"
    )

    print()
    print("=" * 60)
    print(" H1 09:30 CANDIDATES TOP10")
    print("=" * 60)

    # Fixed-board preview only (no Excel access).
    preview_h1_runner_board(decision_enabled=False)

    if H1_FIXED_BOARD_WRITE_ENABLED:
        update_h1_fixed_board_live(
            decision_enabled=False,
        )
    else:
        clear_h1_labels()

    for rank, (_, row) in enumerate(
        h1_candidates.iterrows(),
        start=1,
    ):
        if not H1_FIXED_BOARD_WRITE_ENABLED:
            # Retry transient Excel COM call rejections.
            import pywintypes

            for attempt in range(1, 21):
                try:
                    add_candidate(
                        row["CodeX"],
                        f"H1 CAND #{rank}",
                    )
                    if attempt > 1:
                        print(
                            "  H1 09:30 COM recovered after "
                            f"{attempt - 1} retries"
                        )
                    break
                except pywintypes.com_error as exc:
                    hresult = exc.args[0] if exc.args else None

                    if hresult not in (-2147418111, -2147417846):
                        raise

                    if attempt == 20:
                        raise

                    if attempt == 1:
                        print(
                            "  H1 09:30 Excel COM busy "
                            "- retrying..."
                        )

                    time.sleep(0.25)

        print(
            f"{rank:2d} "
            f"{row['CodeX']} "
            f"{row['NameX']} "
            f"CxV={row['CxV']:.2f}"
        )

    print(
        "H1 TOP10 candidate live board update : OK"
    )

    # LOW-CxV: separate rows 12-14, independent of H1 TOP10.
    # Do not change the existing H1 BUY/WAIT logic.
    try:
        from intraday.h1_low_cxv_board import write_low_cxv_board

        write_low_cxv_board(
            h1_candidates,
            enabled=True,
        )
    except Exception as low_cxv_error:
        print(
            "WARNING: LOW-CxV board update failed: "
            f"{low_cxv_error}"
        )

    # LOW-CxV forward tracking (independent of H1 TOP10).
    try:
        from intraday.h1_low_cxv_recorder import record_low_cxv

        record_low_cxv(
            h1_candidates,
            H1_0930_SNAPSHOT,
            panel_path,
        )
    except Exception as low_cxv_tracking_error:
        print(
            "WARNING: LOW-CxV tracking failed: "
            f"{low_cxv_tracking_error}"
        )

    # ============================================
    # Refresh stop-high prices AFTER the TOP10
    # stocks have been written to the live board.
    #
    # Every J row is first restored to the normal
    # TSE price-limit formula.  JPX expanded-limit
    # stocks are then overwritten with the official
    # JPX stop-high price.
    # ============================================

    print()
    print("=" * 60)
    print(" LIVE BOARD PRICE LIMIT")
    print("=" * 60)

    refresh_expanded_price_limits()

    run_capture()

    print()
    print("=" * 60)
    print(
        " 楽天RSS MORNING COMPLETE"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()


