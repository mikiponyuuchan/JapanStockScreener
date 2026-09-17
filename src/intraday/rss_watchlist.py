# ================================================
# 楽天 MarketSpeed II RSS
# H1監視20銘柄 Excel自動セット
# ================================================

from datetime import datetime
from pathlib import Path

import pandas as pd
import win32com.client as win32


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
# Excel取得
# ================================================

def get_excel():

    try:
        return win32.GetActiveObject(
            "Excel.Application"
        )

    except Exception as exc:
        raise RuntimeError(
            "起動中のExcelを取得できません。"
        ) from exc


def get_rss_sheet():
    """
    楽天RSS専用ブック・シートを名前で取得する。

    ActiveWorkbook / ActiveSheet は使用しない。
    """

    excel = get_excel()

    try:
        book = excel.Workbooks(
            "rakuten_rss_h1.xlsx"
        )
    except Exception as exc:
        raise RuntimeError(
            "楽天RSS専用Excelが開いていません : "
            "rakuten_rss_h1.xlsx"
        ) from exc

    try:
        sheet = book.Worksheets(
            "楽天RSS_H1"
        )
    except Exception as exc:
        raise RuntimeError(
            "楽天RSSシートが見つかりません : "
            "楽天RSS_H1"
        ) from exc

    return sheet


# ================================================
# Excelへ楽天RSS式を設定
# ================================================

def write_excel(watchlist):

    sheet = get_rss_sheet()

    # 見出し
    headers = [
        "コード",
        "銘柄名",
        "現在値",
        "前日比率",
        "出来高",
        "出来高倍率",
        "C×V",
    ]

    for col, value in enumerate(
        headers,
        start=1,
    ):
        sheet.Cells(
            1,
            col,
        ).Value = value

    # 古い監視銘柄を消す
    sheet.Range(
        "A2:G21"
    ).ClearContents()

    # 新しい20銘柄を設定
    for excel_row, (_, row) in enumerate(
        watchlist.iterrows(),
        start=2,
    ):

        code = row["CodeX"]

        # A列はコードそのもの
        sheet.Cells(
            excel_row,
            1,
        ).Value = code

        # 楽天RSS関数
        ticker = f"{code}.T"

        sheet.Cells(
            excel_row,
            2,
        ).Formula = (
            f'=RssMarket('
            f'"{ticker}",'
            f'"銘柄名称")'
        )

        sheet.Cells(
            excel_row,
            3,
        ).Formula = (
            f'=RssMarket('
            f'"{ticker}",'
            f'"現在値")'
        )

        sheet.Cells(
            excel_row,
            4,
        ).Formula = (
            f'=RssMarket('
            f'"{ticker}",'
            f'"前日比率")'
        )

        sheet.Cells(
            excel_row,
            5,
        ).Formula = (
            f'=RssMarket('
            f'"{ticker}",'
            f'"出来高")'
        )

    # ------------------------------------------------
    # 書き込み後検証
    # ------------------------------------------------

    expected_codes = [
        str(code)
        for code in watchlist[
            "CodeX"
        ].tolist()
    ]

    actual_values = sheet.Range(
        "A2:A21"
    ).Value

    actual_codes = []

    for item in actual_values:

        value = item[0]

        if value is None:
            continue

        try:
            value = str(int(value))
        except (TypeError, ValueError):
            value = str(value).strip()

        actual_codes.append(
            value
        )

    if actual_codes != expected_codes:
        raise RuntimeError(
            "楽天RSS Excelへの銘柄設定検証に失敗しました。\n"
            f"expected={expected_codes}\n"
            f"actual={actual_codes}"
        )

    print(
        "RSS Excel target : "
        "rakuten_rss_h1.xlsx / 楽天RSS_H1"
    )

    print(
        "RSS watchlist verify : OK "
        f"({len(actual_codes)} stocks)"
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
