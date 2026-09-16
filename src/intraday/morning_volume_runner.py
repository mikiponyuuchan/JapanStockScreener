# ================================================
# 楽天 MarketSpeed II RSS
# 09:30～09:35 朝出来高 自動取得ランナー
# ================================================

import time
from datetime import datetime, timedelta

from volume_tracker import build_snapshot, save_snapshot


# ================================================
# 設定
# ================================================

START_HOUR = 9
START_MINUTE = 30
END_MINUTE = 35

# 各分の何秒に取得するか
CAPTURE_SECOND = 5


# ================================================
# 次回取得時刻
# ================================================

def build_capture_times(now):
    """
    当日の09:30:05～09:35:05を作成する。
    """

    times = []

    for minute in range(START_MINUTE, END_MINUTE + 1):

        capture_time = now.replace(
            hour=START_HOUR,
            minute=minute,
            second=CAPTURE_SECOND,
            microsecond=0,
        )

        times.append(capture_time)

    return times


# ================================================
# 1回取得
# ================================================

def capture(target_time):
    """
    RSSからTOP20を読み取り、
    target_timeのTimeSlotとして保存する。
    """

    actual_now = datetime.now()

    df = build_snapshot(actual_now)

    if df.empty:
        print(
            f"[{target_time:%H:%M}] "
            "RSSデータなし"
        )
        return

    # 比較用TimeSlotは予定時刻に固定
    df["TimeSlot"] = target_time.strftime("%H:%M")

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

    print(f"保存先 : {output_path}")


# ================================================
# メイン
# ================================================

def main():

    now = datetime.now()

    print("================================")
    print(" 楽天RSS 朝出来高 自動取得")
    print("================================")
    print(f"起動時刻 : {now:%Y-%m-%d %H:%M:%S}")
    print("取得予定 : 09:30～09:35（毎分05秒）")
    print("--------------------------------")

    capture_times = build_capture_times(now)

    # 09:35:05を過ぎていたら終了
    if now > capture_times[-1]:

        print("本日の取得時間は終了しています。")
        return

    for target_time in capture_times:

        now = datetime.now()

        # すでに過ぎた時刻はスキップ
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
            time.sleep(wait_seconds)

        capture(target_time)

    print("--------------------------------")
    print("09:30～09:35 取得完了")


if __name__ == "__main__":
    main()
