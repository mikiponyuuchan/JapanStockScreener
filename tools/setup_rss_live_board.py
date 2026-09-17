from pathlib import Path

import pandas as pd
import win32com.client as win32


ROOT = Path(__file__).resolve().parents[1]

BASELINE_FILE = (
    ROOT
    / "data"
    / "cache"
    / "morning_baseline.csv"
)

WORKBOOK_NAME = "rakuten_rss_live_board.xlsx"
SHEET_NAME = "H1ライブボード"

START_ROW = 2
END_ROW = 21


def normalize_code(value):
    if value is None:
        return ""

    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))

    except (TypeError, ValueError):
        pass

    return (
        str(value)
        .strip()
        .replace(".0", "")
    )


def get_live_board():
    try:
        excel = win32.GetActiveObject(
            "Excel.Application"
        )
    except Exception as exc:
        raise RuntimeError(
            "起動中のExcelを取得できません。"
        ) from exc

    try:
        book = excel.Workbooks(
            WORKBOOK_NAME
        )
    except Exception as exc:
        raise RuntimeError(
            f"{WORKBOOK_NAME} が開いていません。"
        ) from exc

    try:
        sheet = book.Worksheets(
            SHEET_NAME
        )
    except Exception as exc:
        raise RuntimeError(
            f"{SHEET_NAME} がありません。"
        ) from exc

    return excel, book, sheet


def load_baseline():
    if not BASELINE_FILE.exists():
        raise RuntimeError(
            "morning_baseline.csv がありません。"
        )

    df = pd.read_csv(
        BASELINE_FILE,
        dtype={"Code": str},
        low_memory=False,
    )

    required = [
        "Code",
        "Prev5AvgVolume",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "Baseline columns missing : "
            + ", ".join(missing)
        )

    df["CodeX"] = (
        df["Code"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    df["Prev5AvgVolumeX"] = (
        pd.to_numeric(
            df["Prev5AvgVolume"],
            errors="coerce",
        )
    )

    return (
        df
        .drop_duplicates(
            subset=["CodeX"],
            keep="last",
        )
        .set_index("CodeX")
    )


def main():
    print("=" * 60)
    print(" 楽天RSS H1 ライブボード設定")
    print("=" * 60)

    baseline = load_baseline()

    excel, book, sheet = get_live_board()

    print(
        "Workbook :",
        book.Name,
    )
    print(
        "Sheet    :",
        sheet.Name,
    )
    print()

    # ============================================
    # 全銘柄の基準出来高マスター
    #
    # AA列 : Code
    # AB列 : Prev5AvgVolume
    #
    # A列を貼り替えてもZ列がコードで検索するため、
    # 出来高倍率・CxVが自動追従する。
    # ============================================

    sheet.Cells(1, 27).Value = "CodeMaster"
    sheet.Cells(1, 28).Value = "Prev5AvgVolumeMaster"

    # COMへの1セルずつの書き込みは行わず、
    # 全銘柄をAA:ABへ一括書き込みする。
    master_values = []

    for code, base_row in baseline.iterrows():

        avg_volume = base_row["Prev5AvgVolumeX"]

        if (
            pd.isna(avg_volume)
            or float(avg_volume) <= 0
        ):
            continue

        master_values.append(
            (
                str(code),
                float(avg_volume),
            )
        )

    if not master_values:
        raise RuntimeError(
            "基準出来高マスターが空です。"
        )

    master_end_row = (
        len(master_values) + 1
    )

    # 前回途中まで書かれたデータも含めて消去
    sheet.Range(
        "AA2:AB10000"
    ).ClearContents()

    # AA2:AB最終行へ一括書き込み
    sheet.Range(
        sheet.Cells(2, 27),
        sheet.Cells(master_end_row, 28),
    ).Value = tuple(master_values)

    # Z列：A列コードから基準出来高を自動検索
    sheet.Cells(1, 26).Value = "Prev5AvgVolume"

    for row_number in range(
        START_ROW,
        END_ROW + 1,
    ):

        sheet.Cells(
            row_number,
            26,
        ).Formula = (
            f'=IFERROR(XLOOKUP('
            f'A{row_number},'
            f'$AA$2:$AA${master_end_row},'
            f'$AB$2:$AB${master_end_row}'
            f'),"")'
        )

        # F列：現在出来高 ÷ 5日平均出来高
        sheet.Cells(
            row_number,
            6,
        ).Formula = (
            f'=IFERROR(E{row_number}'
            f'/Z{row_number},"")'
        )

        # G列：前日比率 × 出来高倍率
        sheet.Cells(
            row_number,
            7,
        ).Formula = (
            f'=IFERROR(D{row_number}'
            f'*F{row_number},"")'
        )

    success = END_ROW - START_ROW + 1
    missing = []

    # 表示を見やすくする
    sheet.Range(
        f"F{START_ROW}:G{END_ROW}"
    ).NumberFormat = "0.00"

    # 基準出来高とマスター表は裏側へ隠す
    sheet.Columns("Z:AB").Hidden = True

    # Excel再計算
    excel.Calculate()

    book.Save()

    print(
        f"設定成功 : {success}"
    )

    if missing:
        print(
            "Baseline未取得 : "
            + ", ".join(missing)
        )

    print()
    print(
        "F列 : ライブ出来高倍率"
    )
    print(
        "G列 : ライブ C×V"
    )
    print(
        "Z列 : Prev5AvgVolume（非表示）"
    )
    print()
    print(
        "ライブボード設定完了"
    )


if __name__ == "__main__":
    main()
