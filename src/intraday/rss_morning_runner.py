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


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from rss_watchlist import (
    read_panel,
    build_watchlist,
)
from volume_tracker import (
    build_snapshot,
    save_snapshot,
)
from rss_reader import read_rss_rows
from rss_live_board import (
    get_live_board,
    clear_h1_labels,
    add_candidate,
)
from run_morning_screener_rss import build_morning_panel


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

    for target_time in capture_times:

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

        capture_slot(
            target_time
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
            "rakuten_rss_h1.xlsx         : NG"
        )
        print(
            "rakuten_rss_live_board.xlsx : NOT CHECKED"
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
        "rakuten_rss_h1.xlsx         : OK"
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
            "rakuten_rss_live_board.xlsx : NG"
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
        "rakuten_rss_live_board.xlsx : OK"
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

    check_rss_startup()

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
    # Live board : H1 TOP3 only
    #
    # Do NOT overwrite A2:A21.
    # Existing SSR/manual stocks must be preserved.
    # ============================================

    h1_top3 = (
        watchlist
        .head(3)
        .copy()
    )

    clear_h1_labels()

    for rank, (_, row) in enumerate(
        h1_top3.iterrows(),
        start=1,
    ):
        add_candidate(
            row["CodeX"],
            f"H1 #{rank}",
        )

    print(
        "H1 TOP3 live board update : OK"
    )

    run_capture()

    print()
    print("=" * 60)
    print(
        " 楽天RSS MORNING COMPLETE"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()

