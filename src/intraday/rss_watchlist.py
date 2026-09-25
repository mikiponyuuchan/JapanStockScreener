# ================================================
# 楽天 MarketSpeed II RSS
# H1監視20銘柄 Excel自動セット
# ================================================

from datetime import datetime
from pathlib import Path

import pandas as pd
import win32com.client as win32

from rss_reader import get_rss_sheet


MORNING_DIR = Path("data/analysis/morning")

TARGET_START_MIN = 9 * 60 + 20
TARGET_END_MIN = 9 * 60 + 25

WATCH_N = 20


# ================================================
# morning panel 読み込み
# ================================================

def read_panel(path):

    try:
        df = pd.read_csv(
            path,
            dtype={"Code": str},
            low_memory=False,
        )

    except Exception as exc:
        print(
            f"READ ERROR : {path} : {exc}"
        )
        return None

    required = [
        "Code",
        "Name",
        "MorningPrice",
        "PrevClose",
        "MorningChangePct",
        "MorningVolumeVsPrev5",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if df.empty or missing:
        return None

    return df


# ================================================
# 当日の09:20～09:25パネル取得
# ================================================

def find_target_panel():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    candidates = []

    for path in sorted(
        MORNING_DIR.glob(
            f"{today}_*_morning_panel.csv"
        )
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

        hour = int(hhmm[:2])
        minute_only = int(hhmm[2:])

        minute = (
            hour * 60
            + minute_only
        )

        if not (
            TARGET_START_MIN
            <= minute
            <= TARGET_END_MIN
        ):
            continue

        candidates.append(
            (
                minute,
                path,
            )
        )

    if not candidates:
        return None

    # H1-Early20と同じく
    # 対象時間内の最も早いパネルを使用
    candidates.sort(
        key=lambda x: (
            x[0],
            str(x[1]),
        )
    )

    return candidates[0][1]


# ================================================
# CxV上位20
# ================================================

def build_watchlist(df):

    work = df.copy()

    work["CodeX"] = (
        work["Code"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    work["NameX"] = (
        work["Name"]
        .astype(str)
    )

    work["ChangeX"] = pd.to_numeric(
        work["MorningChangePct"],
        errors="coerce",
    )

    work["VolumeX"] = pd.to_numeric(
        work["MorningVolumeVsPrev5"],
        errors="coerce",
    )

    work["CxV"] = (
        work["ChangeX"]
        * work["VolumeX"]
    )

    valid = work[
        work["CodeX"].ne("")
        & work["ChangeX"].notna()
        & work["VolumeX"].notna()
        & work["CxV"].notna()
    ].copy()

    watchlist = (
        valid
        .sort_values(
            ["CxV", "ChangeX"],
            ascending=[
                False,
                False,
            ],
        )
        .head(WATCH_N)
        .copy()
    )

    return watchlist


# ================================================
# Excelへ楽天RSS式を設定
# ================================================

def write_excel(watchlist):
    """
    H1監視ブックのA2:E21を更新する。

    A : コード
    B : 銘柄名称
    C : 現在値
    D : 前日比率
    E : 出来高

    TOP20のコード変更時にRSS式も同時更新し、
    コードとRSSデータのずれを防止する。
    """

    sheet = get_rss_sheet()

    expected_codes = [
        str(code)
        for code in watchlist["CodeX"].tolist()
    ]

    # 楽天RSSフィールド名
    # Unicode escapeにしてPowerShellの
    # 文字コード問題を避ける。
    rss_name = "\u9298\u67c4\u540d\u79f0"
    rss_price = "\u73fe\u5728\u5024"
    rss_change = "\u524d\u65e5\u6bd4\u7387"
    rss_volume = "\u51fa\u6765\u9ad8"

    values = []

    for code in expected_codes:
        values.append(
            (
                code,
                f'=RssMarket("{code}.T","{rss_name}")',
                f'=RssMarket("{code}.T","{rss_price}")',
                f'=RssMarket("{code}.T","{rss_change}")',
                f'=RssMarket("{code}.T","{rss_volume}")',
            )
        )

    # 20行未満の場合にも対応
    while len(values) < WATCH_N:
        values.append(
            ("", "", "", "", "")
        )

    # コードとRSS式を一括更新
    sheet.Range(
        "A2:E21"
    ).Formula = tuple(values)

    # Excel再計算
    sheet.Application.Calculate()

    # ------------------------------------------------
    # 書き込み後検証
    # ------------------------------------------------

    actual_values = sheet.Range(
        "A2:A21"
    ).Value

    actual_codes = []

    for item in actual_values:

        value = item[0]

        if value is None or value == "":
            continue

        try:
            value = str(int(value))
        except (TypeError, ValueError):
            value = str(value).strip()

        actual_codes.append(value)

    if actual_codes != expected_codes:
        raise RuntimeError(
            "楽天RSS H1監視ブックへの"
            "銘柄設定検証に失敗しました。\n"
            f"expected={expected_codes}\n"
            f"actual={actual_codes}"
        )

    print(
        "RSS Excel target : "
        "rakuten_rss_h1.xlsx / "
        "楽天RSS_H1"
    )

    print(
        "RSS watchlist verify : OK "
        f"({len(actual_codes)} stocks)"
    )

    print(
        "更新範囲 : A2:E21 "
        "(Code + RSS formulas)"
    )

    return sheet


# ================================================
# メイン
# ================================================

def main():

    print("=" * 60)
    print(
        " 楽天RSS H1 監視20銘柄セット"
    )
    print("=" * 60)

    panel_path = find_target_panel()

    if panel_path is None:
        print(
            "本日の09:20～09:25 "
            "morning_panelがありません。"
        )
        return

    print(
        "Panel :",
        panel_path,
    )

    df = read_panel(
        panel_path
    )

    if df is None:
        print(
            "morning_panelを読み込めません。"
        )
        return

    watchlist = build_watchlist(
        df
    )

    if watchlist.empty:
        print(
            "監視候補がありません。"
        )
        return

    write_excel(
        watchlist
    )

    print()
    print(
        f"Excel設定銘柄数 : "
        f"{len(watchlist)}"
    )

    print("------------------------------")

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

    print("------------------------------")
    print(
        "楽天RSS Excelへの設定完了"
    )


if __name__ == "__main__":
    main()
