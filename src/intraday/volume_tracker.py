# ================================================
# 楽天 MarketSpeed II RSS
# 朝出来高スナップショット保存
# ================================================

import argparse
from datetime import datetime, time
from pathlib import Path

import pandas as pd

from rss_reader import read_rss_rows


# ================================================
# 設定
# ================================================

LIVE_START = time(9, 30)
LIVE_END = time(9, 35)

BASE_DIR = Path("data/intraday/volume_history")
TEST_DIR = Path("data/intraday/test_volume_history")


# ================================================
# 保存可能時間判定
# ================================================

def is_live_window(now):
    """
    本番保存可能時間か判定する。

    09:30:00 ～ 09:35:59 を許可。
    """
    current = now.time()

    start = LIVE_START
    end = time(9, 35, 59)

    return start <= current <= end


# ================================================
# RSSデータ取得
# ================================================

def build_snapshot(now):
    """
    Excel上の楽天RSSデータを取得し、
    CSV保存用DataFrameを作成する。
    """

    rows = read_rss_rows()

    records = []

    for row in rows:

        records.append(
            {
                "Timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "TimeSlot": now.strftime("%H:%M"),
                "Code": row["Code"],
                "Name": row["Name"],
                "ChangePercent": row["ChangePercent"],
                "Volume": row["Volume"],
            }
        )

    return pd.DataFrame(records)


# ================================================
# CSV保存
# ================================================

def save_snapshot(df, now, test_mode=False):
    """
    スナップショットを日別CSVへ保存する。

    同一 Timestamp + Code は重複保存しない。
    """

    output_dir = TEST_DIR if test_mode else BASE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{now:%Y-%m-%d}.csv"
    output_path = output_dir / filename

    if output_path.exists():

        old_df = pd.read_csv(
            output_path,
            dtype={"Code": str},
        )

        combined = pd.concat(
            [old_df, df],
            ignore_index=True,
        )

        combined = combined.drop_duplicates(
            subset=["Timestamp", "Code"],
            keep="last",
        )

    else:

        combined = df

    combined.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    return output_path


# ================================================
# メイン
# ================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--test",
        action="store_true",
        help="時間外でもテスト用CSVへ保存する",
    )

    args = parser.parse_args()

    now = datetime.now()

    print("==============================")
    print(" 楽天RSS 朝出来高トラッカー")
    print("==============================")
    print(f"現在時刻 : {now:%Y-%m-%d %H:%M:%S}")

    # --------------------------------------------
    # 本番時間チェック
    # --------------------------------------------

    if not args.test and not is_live_window(now):

        print(
            "保存対象時間外です "
            "(本番保存は09:30～09:35のみ)"
        )
        return

    # --------------------------------------------
    # RSS取得
    # --------------------------------------------

    df = build_snapshot(now)

    if df.empty:

        print("RSSデータがありません。")
        return

    # --------------------------------------------
    # 保存
    # --------------------------------------------

    output_path = save_snapshot(
        df,
        now,
        test_mode=args.test,
    )

    mode = "TEST" if args.test else "LIVE"

    print(f"モード     : {mode}")
    print(f"取得銘柄数 : {len(df)}")
    print(f"保存先     : {output_path}")

    print("------------------------------")

    for _, row in df.iterrows():

        print(
            f"{row['Code']} "
            f"{row['Name']} "
            f"前日比={row['ChangePercent']}% "
            f"出来高={row['Volume']}"
        )


if __name__ == "__main__":
    main()
