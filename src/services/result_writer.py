import pandas as pd
from datetime import datetime
from pathlib import Path

from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image

from services.chart_service import save_chart


def save_result(df):

    # ==========================
    # 保存フォルダ
    # ==========================

    folder = Path("results")
    folder.mkdir(
        exist_ok=True
    )

    chart_folder = folder / "charts"
    chart_folder.mkdir(
        exist_ok=True
    )

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    csv_file = (
        folder /
        f"{today}_stock_result.csv"
    )

    excel_file = (
        folder /
        f"{today}_stock_result.xlsx"
    )

    top20_csv = (
        folder /
        f"{today}_top20.csv"
    )


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


    # ==========================
    # TOP20チャート作成
    # ==========================

    # ==========================
    # TOP20チャート作成
    # ==========================

    chart_files = {}

    print()
    print("TOP20チャート作成開始")

    for _, row in top20.iterrows():

        code = str(
            row["コード"]
        )

        print(f"チャート保存 : {code}")

        chart = save_chart(
        code
        )

        if chart:

            chart_files[code] = chart

            print(f"保存OK : {code}")

        else:

            print(f"保存失敗 : {code}")



    # ==========================
    # 買い候補
    # ==========================

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

            top20.to_excel(
                writer,
                sheet_name="TOP20",
                index=False
            )


            # ----------------------
            # 買い候補
            # ----------------------

            buy_df.to_excel(
                writer,
                sheet_name="買い候補",
                index=False
            )


            workbook = writer.book

            # ==========================
            # 色設定
            # ==========================

            green_fill = PatternFill(
                fill_type="solid",
                start_color="CCFFCC",
                end_color="CCFFCC"
            )

            blue_font = Font(
                color="0000FF"
            )

            red_font = Font(
                color="FF0000"
            )

            purple_font = Font(
                color="800080"
            )

            orange_font = Font(
                color="FF6600",
                bold=True
            )


            # ==========================
            # シート整形
            # ==========================

            for sheet in workbook.worksheets:


                sheet.freeze_panes = "C2"


                sheet.auto_filter.ref = (
                    sheet.dimensions
                )


                for cell in sheet[1]:

                    cell.font = Font(
                        bold=True
                    )


                headers = {}

                for cell in sheet[1]:

                    headers[cell.value] = (
                        cell.column
                    )


                # ----------------------
                # 列幅調整
                # ----------------------

                for column_cells in sheet.columns:

                    column = get_column_letter(
                        column_cells[0].column
                    )

                    max_length = 0


                    for cell in column_cells:

                        if cell.value is None:
                            continue


                        length = len(
                            str(cell.value)
                        )


                        if length > max_length:

                            max_length = length


                    sheet.column_dimensions[
                        column
                    ].width = min(
                        max_length + 3,
                        40
                    )


                # ----------------------
                # 色付け
                # ----------------------

                for row in range(
                    2,
                    sheet.max_row + 1
                ):


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



                    if "監視ランク" in headers:

                        cell = sheet.cell(
                            row,
                            headers["監視ランク"]
                        )


                        if str(
                            cell.value
                        ).startswith("A"):

                            cell.font = blue_font



                    if "RSI" in headers:

                        cell = sheet.cell(
                            row,
                            headers["RSI"]
                        )


                        try:

                            if float(
                                cell.value
                            ) >= 75:

                                cell.font = red_font

                        except Exception:

                            pass



                    if "ブレイク" in headers:

                        cell = sheet.cell(
                            row,
                            headers["ブレイク"]
                        )


                        if cell.value:

                            cell.font = purple_font



                    if "強気度" in headers:

                        cell = sheet.cell(
                            row,
                            headers["強気度"]
                        )


                        try:

                            if int(
                                cell.value
                            ) >= 20:

                                cell.font = orange_font


                        except Exception:

                            pass



            # ==========================
            # TOP20チャート貼付
            # ==========================

            sheet = workbook[
                "TOP20"
            ]


            chart_column = (
                sheet.max_column + 2
            )


            sheet.cell(
                1,
                chart_column
            ).value = "日足チャート"



            for index, (_, row) in enumerate(
                top20.iterrows(),
                start=2
            ):


                code = str(
                    row["コード"]
                )


                if code in chart_files:


                    img = Image(
                        str(
                            chart_files[code]
                        )
                    )


                    img.width = 320
                    img.height = 160


                    cell = (
                        get_column_letter(
                            chart_column
                        )
                        +
                        str(index)
                    )


                    sheet.add_image(
                        img,
                        cell
                    )


                    sheet.row_dimensions[
                        index
                    ].height = 125



            sheet.column_dimensions[
                get_column_letter(chart_column)
            ].width = 45



        # ==========================
        # TOP20 CSV
        # ==========================

        top20.to_csv(
            top20_csv,
            index=False,
            encoding="utf-8-sig"
        )


    except PermissionError:

        print()
        print(
            "=============================================="
        )
        print(
            f"保存できません：{excel_file.name}"
        )
        print(
            "Excelで開いている可能性があります。"
        )
        print(
            "閉じてから再実行してください。"
        )
        print(
            "=============================================="
        )

        return



    print()
    print(
        "CSV保存   :",
        csv_file
    )

    print(
        "Excel保存 :",
        excel_file
    )

    print(
        "TOP20保存 :",
        top20_csv
    )