import pandas as pd
from datetime import datetime
from pathlib import Path

from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def save_result(df):

    # ==========================
    # 保存フォルダ
    # ==========================

    folder = Path("results")
    folder.mkdir(exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    csv_file = folder / f"{today}_stock_result.csv"
    excel_file = folder / f"{today}_stock_result.xlsx"
    top20_csv = folder / f"{today}_top20.csv"

    # ==========================
    # CSV保存
    # ==========================

    df.to_csv(
        csv_file,
        index=False,
        encoding="utf-8-sig"
    )

    # ==========================
    # TOP20作成
    # ==========================

    top20 = (
        df.sort_values(
            "強気度",
            ascending=False
        )
        .head(20)
    )

    buy_df = df[
        df["総合判定"] == "買い候補"
    ]

    # ==========================
    # Excel保存
    # ==========================

    try:

        with pd.ExcelWriter(
            excel_file,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                sheet_name="全銘柄",
                index=False
            )

            top20.to_excel(
                writer,
                sheet_name="TOP20",
                index=False
            )

            buy_df.to_excel(
                writer,
                sheet_name="買い候補",
                index=False
            )

            workbook = writer.book

            # ----------------------
            # 色設定
            # ----------------------

            green_fill = PatternFill(
                fill_type="solid",
                start_color="CCFFCC",
                end_color="CCFFCC"
            )

            blue_font = Font(color="0000FF")

            red_font = Font(color="FF0000")

            purple_font = Font(color="800080")

            orange_font = Font(
                color="FF6600",
                bold=True
            )

            # ======================
            # 全シート共通設定
            # ======================

            for sheet in workbook.worksheets:

                sheet.freeze_panes = "C2"

                sheet.auto_filter.ref = sheet.dimensions

                # ヘッダー

                for cell in sheet[1]:
                    cell.font = Font(bold=True)

                # 列番号取得

                headers = {}

                for cell in sheet[1]:
                    headers[cell.value] = cell.column

                # 列幅自動

                for column_cells in sheet.columns:

                    column = get_column_letter(
                        column_cells[0].column
                    )

                    max_length = 0

                    for cell in column_cells:

                        if cell.value is None:
                            continue

                        length = len(str(cell.value))

                        if length > max_length:
                            max_length = length

                    sheet.column_dimensions[column].width = min(
                        max_length + 3,
                        40
                    )

                # ------------------
                # 行ごとの色付け
                # ------------------

                for row in range(
                    2,
                    sheet.max_row + 1
                ):

                    # 買い候補

                    if "総合判定" in headers:

                        cell = sheet.cell(
                            row,
                            headers["総合判定"]
                        )

                        if cell.value == "買い候補":

                            for col in range(
                                1,
                                sheet.max_column + 1
                            ):

                                sheet.cell(
                                    row,
                                    col
                                ).fill = green_fill

                    # Aランク

                    if "監視ランク" in headers:

                        cell = sheet.cell(
                            row,
                            headers["監視ランク"]
                        )

                        if str(cell.value).startswith("A"):

                            cell.font = blue_font

                    # RSI

                    if "RSI" in headers:

                        cell = sheet.cell(
                            row,
                            headers["RSI"]
                        )

                        try:

                            if float(cell.value) >= 75:
                                cell.font = red_font

                        except Exception:
                            pass

                    # ブレイク

                    if "ブレイク" in headers:

                        cell = sheet.cell(
                            row,
                            headers["ブレイク"]
                        )

                        if cell.value:
                            cell.font = purple_font

                    # 強気度

                    if "強気度" in headers:

                        cell = sheet.cell(
                            row,
                            headers["強気度"]
                        )

                        try:

                            if int(cell.value) >= 20:
                                cell.font = orange_font

                        except Exception:
                            pass

        # ==========================
        # TOP20 CSV保存
        # ==========================

        top20.to_csv(
            top20_csv,
            index=False,
            encoding="utf-8-sig"
        )

    except PermissionError:

        print()
        print("====================================")
        print("Excelファイルを閉じてください")
        print(excel_file.name)
        print("====================================")
        return

    # ==========================
    # 保存結果表示
    # ==========================

    print()
    print("CSV保存   :", csv_file)
    print("Excel保存 :", excel_file)
    print("TOP20保存 :", top20_csv)