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

import time
from datetime import datetime
from pathlib import Path

from rss_watchlist import (
    read_panel,
    build_watchlist,
    write_excel,
)
from volume_tracker import (
    build_snapshot,
    save_snapshot,
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
# Excel監視20銘柄セット
# ================================================

def setup_watchlist(
    panel_path,
):

    print()
    print("=" * 60)
    print(" RSS WATCHLIST SETUP")
    print("=" * 60)

    print(
        "Panel :",
        panel_path,
    )

    df = read_panel(
        panel_path
    )

    if df is None:
        raise RuntimeError(
            "morning_panelを読み込めません。"
        )

    watchlist = build_watchlist(
        df
    )

    if watchlist.empty:
        raise RuntimeError(
            "RSS監視候補がありません。"
        )

    write_excel(
        watchlist
    )

    print(
        f"Excel設定銘柄数 : "
        f"{len(watchlist)}"
    )

    print()

    for rank, (_, row) in enumerate(
        watchlist.iterrows(),
        start=1,
    ):

        print(
            f"{rank:2d} "
            f"{row['CodeX']} "
            f"{row['NameX']} "
            f"CxV={row['CxV']:.2f}"
        )

    return watchlist


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

    print()
    print(
        "09:20 morning_panelを待機します。"
    )

    panel_path = wait_for_panel()

    if panel_path is None:

        print(
            "09:20～09:25 morning_panelが"
            "見つかりませんでした。"
        )

        return

    # 09:20 watchlist is used for validation only.
    # Do not overwrite the compact RSS live board.
    print()
    print(
        "09:20 watchlist : "
        "Excel update skipped"
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
