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

    # ==========================
    # CSV保存
    # ==========================

    df.to_csv(
        csv_file,
        index=False,
        encoding="utf-8-sig"
    )

    # ==========================
    # Excel保存
    # ==========================

    try:

        with pd.ExcelWriter(
            excel_file,
            engine="openpyxl"
        ) as writer:

            # ----------------------
            # 全銘柄
            # ----------------------

            df.to_excel(
                writer,
                sheet_name="全銘柄",
                index=False
            )

            # ----------------------
            # TOP20
            # ----------------------

            top20 = (
                df.sort_values(
                    "強気度",
                    ascending=False
                )
                .head(20)
            )

            top20.to_excel(
                writer,
                sheet_name="TOP20",
                index=False
            )

            # ----------------------
            # 買い候補
            # ----------------------

            buy_df = df[
                df["総合判定"] == "買い候補"
            ]

            buy_df.to_excel(
                writer,
                sheet_name="買い候補",
                index=False
            )
                        # ==========================
            # Excel見やすさ改善
            # ==========================

            workbook = writer.book

            # 色定義
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

            for sheet in workbook.worksheets:

                # ----------------------
                # 先頭行固定
                # ----------------------

                sheet.freeze_panes = "A2"

                # ----------------------
                # フィルター
                # ----------------------

                sheet.auto_filter.ref = sheet.dimensions

                # ----------------------
                # ヘッダー太字
                # ----------------------

                for cell in sheet[1]:
                    cell.font = Font(bold=True)

                # ----------------------
                # 列幅自動調整
                # ----------------------

                headers = {}

                for cell in sheet[1]:

                    headers[cell.value] = cell.column

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

                # ----------------------
                # 色付け
                # ----------------------

                for row in range(2, sheet.max_row + 1):

                    # 買い候補 → 行全体を薄緑
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

                    # Aランク → 青文字
                    if "監視ランク" in headers:

                        cell = sheet.cell(
                            row,
                            headers["監視ランク"]
                        )

                        if str(cell.value).startswith("A"):

                            cell.font = blue_font

                    # RSI75以上 → 赤文字
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

                    # ブレイクアウト → 紫文字
                    if "ブレイクアウト" in headers:

                        cell = sheet.cell(
                            row,
                            headers["ブレイクアウト"]
                        )

                        if cell.value:

                            cell.font = purple_font

                    # 強気度20以上 → オレンジ太字
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

    except PermissionError:

        print()
        print("==============================================")
        print(f"保存できません：{excel_file.name}")
        print("Excelで開いている可能性があります。")
        print("閉じてからもう一度実行してください。")
        print("==============================================")
        return

    print()
    print("CSV保存 :", csv_file)
    print("Excel保存 :", excel_file)