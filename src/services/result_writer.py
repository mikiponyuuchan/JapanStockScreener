import pandas as pd
from datetime import datetime
from pathlib import Path

from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment,
)
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image

from services.chart_service import save_chart

from services.news_service import (
    get_top20_news,
    analyze_news_reason,
)

from services.tracking_service import (
    record_initial_move,
)


def save_result(df):

    # ==========================
    # 保存フォルダ
    # ==========================

    folder = Path("results")
    folder.mkdir(exist_ok=True)

    chart_folder = folder / "charts"
    chart_folder.mkdir(exist_ok=True)

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
    # 強気度TOP20
    # ==========================

    top20 = (
        df.sort_values(
            "強気度",
            ascending=False
        )
        .head(20)
        .copy()
    )

    # ==========================
    # 初動スコアTOP20
    # ==========================

    initial_move_score = pd.to_numeric(
        df["初動スコア"],
        errors="coerce"
    )

    # 初動シグナルがある銘柄だけを対象にする
    initial_move_signal = (
        df["初動シグナル"]
        .astype(str)
        .str.strip()
        .ne("")
    )

    initial_move_top20 = (
        df.loc[
            initial_move_signal
            & initial_move_score.notna()
        ]
        .copy()
    )

    initial_move_top20["_initial_move_score_numeric"] = (
        initial_move_score.loc[
            initial_move_top20.index
        ]
    )

    initial_move_top20 = (
        initial_move_top20
        .sort_values(
            "_initial_move_score_numeric",
            ascending=False,
            kind="mergesort"
        )
        .head(20)
        .copy()
    )

    initial_move_top20.drop(
        columns=[
            "_initial_move_score_numeric"
        ],
        inplace=True
    )

    # ==========================
    # 初動TOP20を追跡対象として登録
    # ==========================

    record_initial_move(
        initial_move_top20
    )


    # ==========================
    # TOP20ニュース取得
    # ==========================

    print()
    print("TOP20ニュース取得中...")

    news_data = get_top20_news(top20)

    print("TOP20ニュース取得完了")

    # ==========================
    # 初動スコアTOP20ニュース取得
    # ==========================

    print()
    print("初動スコアTOP20ニュース取得中...")

    initial_move_news_data = get_top20_news(
        initial_move_top20
    )

    print("初動スコアTOP20ニュース取得完了")

    # ==========================
    # TOP20急騰理由分析
    # ==========================

    print()
    print("TOP20急騰理由分析中...")

    reason_data_all = {}

    for _, row in top20.iterrows():

        code = str(
            row["コード"]
        )

        news_list = news_data.get(
            code,
            []
        )

        reason_data_all[code] = (
            analyze_news_reason(
                news_list
            )
        )

    print("TOP20急騰理由分析完了")

    # ==========================
    # 初動スコアTOP20急騰理由分析
    # ==========================

    print()
    print(
        "初動スコアTOP20急騰理由分析中..."
    )

    initial_move_reason_data_all = {}

    for _, row in initial_move_top20.iterrows():

        code = str(
            row["コード"]
        )

        news_list = (
            initial_move_news_data.get(
                code,
                []
            )
        )

        initial_move_reason_data_all[code] = (
            analyze_news_reason(
                news_list
            )
        )

    print(
        "初動スコアTOP20急騰理由分析完了"
    )

    # ==========================
    # 日足チャート作成
    # ==========================

    chart_files = {}

    print()
    print("日足チャート作成中...")

    # --------------------------
    # 強気度TOP20
    # --------------------------

    for _, row in top20.iterrows():

        code = str(
            row["コード"]
        )

        if code in chart_files:
            continue

        chart = save_chart(code)

        if chart:
            chart_files[code] = chart

    # --------------------------
    # 初動スコアTOP20
    # --------------------------

    for _, row in initial_move_top20.iterrows():

        code = str(
            row["コード"]
        )

        if code in chart_files:
            continue

        chart = save_chart(code)

        if chart:
            chart_files[code] = chart

    print(
        f"日足チャート作成完了 ({len(chart_files)}銘柄)"
    )

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

            # ==================================================
            # 全銘柄
            # ==================================================

            df.to_excel(
                writer,
                sheet_name="全銘柄",
                index=False
            )

            # ==================================================
            # TOP20表示用
            # ==================================================

            top20_rows = []

            for _, row in top20.iterrows():

                code = str(
                    row["コード"]
                )

                reason_data = (
                    reason_data_all.get(
                        code,
                        {}
                    )
                )

                # ----------------------
                # 分析コメント整理
                # ----------------------

                comment = str(
                    row["分析コメント"]
                )

                parts = comment.split(
                    " / "
                )

                parts = [
                    part
                    for part in parts
                    if not part.startswith(
                        "Aランク"
                    )
                    and not part.startswith(
                        "買い候補"
                    )
                    and not part.startswith(
                        "強気度"
                    )
                ]

                clean_comment = "\n".join(
                    parts
                )

                # ----------------------
                # TOP20表示データ
                # ----------------------

                top20_rows.append(
                    {
                        "コード":
                            code,

                        "銘柄名":
                            row["銘柄名"],

                        "株価":
                            row["終値"],

                        "強気度":
                            row["強気度"],

                        "分析コメント":
                            clean_comment,

                        "急騰理由":
                            reason_data.get(
                                "reason",
                                "明確な材料を確認できず"
                            ),

                        "主な材料":
                            reason_data.get(
                                "main_title",
                                ""
                            ),

                        "ニュース日時":
                            reason_data.get(
                                "main_published",
                                ""
                            ),
                    }
                )

            top20_display = pd.DataFrame(
                top20_rows
            )

            top20_display.to_excel(
                writer,
                sheet_name="TOP20",
                index=False
            )

            # ==================================================
            # 初動スコアTOP20
            # ==================================================

            initial_move_rows = []

            for _, row in initial_move_top20.iterrows():

                code = str(
                    row["コード"]
                )

                reason_data = (
                    initial_move_reason_data_all.get(
                        code,
                        {}
                    )
                )

                # ----------------------
                # 分析コメント整理
                # ----------------------

                comment = str(
                    row["分析コメント"]
                )

                parts = comment.split(
                    " / "
                )

                parts = [
                    part
                    for part in parts
                    if not part.startswith(
                        "Aランク"
                    )
                    and not part.startswith(
                        "買い候補"
                    )
                    and not part.startswith(
                        "強気度"
                    )
                ]

                clean_comment = "\n".join(
                    parts
                )

                # ----------------------
                # 初動スコアTOP20表示
                # ----------------------

                initial_move_rows.append(
                    {
                        "コード":
                            code,

                        "銘柄名":
                            row["銘柄名"],

                        "株価":
                            row["終値"],

                        "強気度":
                            row["強気度"],

                        "初動スコア":
                            row["初動スコア"],

                        "分析コメント":
                            clean_comment,

                        "急騰理由":
                            reason_data.get(
                                "reason",
                                "明確な材料を確認できず"
                            ),

                        "主な材料":
                            reason_data.get(
                                "main_title",
                                ""
                            ),

                        "ニュース日時":
                            reason_data.get(
                                "main_published",
                                ""
                            ),
                    }
                )

            initial_move_display = pd.DataFrame(
                initial_move_rows
            )

            initial_move_display.to_excel(
                writer,
                sheet_name="初動スコアTOP20",
                index=False
            )

            # ==================================================
            # TOP20ニュース
            # ==================================================

            news_rows = []

            for _, row in top20.iterrows():

                code = str(
                    row["コード"]
                )

                name = str(
                    row["銘柄名"]
                )

                news_list = news_data.get(
                    code,
                    []
                )

                reason_data = (
                    reason_data_all.get(
                        code,
                        {}
                    )
                )

                reason = reason_data.get(
                    "reason",
                    "明確な材料を確認できず"
                )

                main_title = reason_data.get(
                    "main_title",
                    ""
                )

                main_source = reason_data.get(
                    "main_source",
                    ""
                )

                main_published = reason_data.get(
                    "main_published",
                    ""
                )

                main_link = reason_data.get(
                    "main_link",
                    ""
                )

                # ------------------
                # ニュースなし
                # ------------------

                if not news_list:

                    news_rows.append(
                        {
                            "コード":
                                code,

                            "銘柄名":
                                name,

                            "強気度":
                                row["強気度"],

                            "前日比%":
                                row["前日比%"],

                            "急騰理由":
                                reason,

                            "主な材料":
                                "",

                            "情報元":
                                "",

                            "ニュース日時":
                                "",

                            "ニュースタイトル":
                                "ニュースなし",

                            "ニュースリンク":
                                "",
                        }
                    )

                else:

                    # ------------------
                    # 主材料
                    # ------------------

                    news_rows.append(
                        {
                            "コード":
                                code,

                            "銘柄名":
                                name,

                            "強気度":
                                row["強気度"],

                            "前日比%":
                                row["前日比%"],

                            "急騰理由":
                                reason,

                            "主な材料":
                                main_title,

                            "情報元":
                                main_source,

                            "ニュース日時":
                                main_published,

                            "ニュースタイトル":
                                main_title,

                            "ニュースリンク":
                                main_link,
                        }
                    )

                    # ------------------
                    # その他ニュース
                    # ------------------

                    for news in news_list:

                        if (
                            news.get(
                                "title",
                                ""
                            )
                            == main_title
                        ):
                            continue

                        news_rows.append(
                            {
                                "コード":
                                    code,

                                "銘柄名":
                                    name,

                                "強気度":
                                    row["強気度"],

                                "前日比%":
                                    row["前日比%"],

                                "急騰理由":
                                    "",

                                "主な材料":
                                    "",

                                "情報元":
                                    news.get(
                                        "source",
                                        ""
                                    ),

                                "ニュース日時":
                                    news.get(
                                        "published",
                                        ""
                                    ),

                                "ニュースタイトル":
                                    news.get(
                                        "title",
                                        ""
                                    ),

                                "ニュースリンク":
                                    news.get(
                                        "link",
                                        ""
                                    ),
                            }
                        )

            news_df = pd.DataFrame(
                news_rows
            )

            news_df.to_excel(
                writer,
                sheet_name="TOP20ニュース",
                index=False
            )

            # ==================================================
            # 買い候補
            # ==================================================

            buy_df.to_excel(
                writer,
                sheet_name="買い候補",
                index=False
            )

            workbook = writer.book

            # ==================================================
            # 色設定
            # ==================================================

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

            # ==================================================
            # 各シート基本整形
            # ==================================================

            for sheet in workbook.worksheets:

                sheet.freeze_panes = "C2"

                sheet.auto_filter.ref = (
                    sheet.dimensions
                )

                # ----------------------
                # ヘッダー太字
                # ----------------------

                for cell in sheet[1]:

                    cell.font = Font(
                        bold=True
                    )

                # ----------------------
                # ヘッダー取得
                # ----------------------

                headers = {}

                for cell in sheet[1]:

                    headers[cell.value] = (
                        cell.column
                    )

                # ----------------------
                # 分析コメント
                # ----------------------

                if "分析コメント" in headers:

                    comment_col = headers[
                        "分析コメント"
                    ]

                    for row in range(
                        2,
                        sheet.max_row + 1
                    ):

                        cell = sheet.cell(
                            row,
                            comment_col
                        )

                        cell.alignment = Alignment(
                            wrap_text=True,
                            vertical="top"
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

                        values = str(
                            cell.value
                        ).split("\n")

                        length = max(
                            len(value)
                            for value in values
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

                    # ------------------
                    # 買い候補
                    # ------------------

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

                    # ------------------
                    # 監視ランク
                    # ------------------

                    if "監視ランク" in headers:

                        cell = sheet.cell(
                            row,
                            headers["監視ランク"]
                        )

                        if str(
                            cell.value
                        ).startswith("A"):

                            cell.font = blue_font

                    # ------------------
                    # RSI
                    # ------------------

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

                    # ------------------
                    # ブレイク
                    # ------------------

                    if "ブレイク" in headers:

                        cell = sheet.cell(
                            row,
                            headers["ブレイク"]
                        )

                        if cell.value:

                            cell.font = purple_font

                # ----------------------
                # 強気度グラデーション
                # ----------------------

                if "強気度" in headers:

                    col = get_column_letter(
                        headers["強気度"]
                    )

                    sheet.conditional_formatting.add(
                        f"{col}2:{col}{sheet.max_row}",
                        ColorScaleRule(
                            start_type="min",
                            start_color="63BE7B",
                            mid_type="percentile",
                            mid_value=50,
                            mid_color="FFEB84",
                            end_type="max",
                            end_color="F8696B",
                        )
                    )

            # ==================================================
            # TOP20シート
            # ==================================================

            sheet = workbook["TOP20"]

            headers = {}

            for cell in sheet[1]:

                headers[cell.value] = (
                    cell.column
                )

            # ----------------------
            # 列幅
            # ----------------------

            sheet.column_dimensions["A"].width = 7    # コード
            sheet.column_dimensions["B"].width = 16   # 銘柄名
            sheet.column_dimensions["C"].width = 8    # 株価
            sheet.column_dimensions["D"].width = 7    # 強気度
            sheet.column_dimensions["E"].width = 10   # 分析コメント
            sheet.column_dimensions["F"].width = 14   # 急騰理由
            sheet.column_dimensions["G"].width = 18   # 主な材料
            sheet.column_dimensions["H"].width = 11   # ニュース日時

            # ----------------------
            # 強気度グラデーション
            # ----------------------

            score_col = headers["強気度"]

            scores = []

            for row in range(
                2,
                sheet.max_row + 1
            ):

                value = sheet.cell(
                    row,
                    score_col
                ).value

                if value is not None:

                    try:

                        scores.append(
                            int(value)
                        )

                    except Exception:

                        pass

            if scores:

                min_score = min(scores)
                max_score = max(scores)

                for row in range(
                    2,
                    sheet.max_row + 1
                ):

                    cell = sheet.cell(
                        row,
                        score_col
                    )

                    try:

                        score = int(
                            cell.value
                        )

                    except Exception:

                        continue

                    if max_score == min_score:

                        ratio = 1

                    else:

                        ratio = (
                            score - min_score
                        ) / (
                            max_score - min_score
                        )

                    red = 255

                    green = int(
                        255 * (1 - ratio)
                    )

                    color = (
                        f"FF{green:02X}00"
                    )

                    cell.fill = PatternFill(
                        fill_type="solid",
                        start_color=color,
                        end_color=color,
                    )

            # ----------------------
            # TOP20文字整形
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                for col in range(
                    1,
                    sheet.max_column + 1
                ):

                    cell = sheet.cell(
                        row,
                        col
                    )

                    cell.alignment = Alignment(
                        horizontal="left",
                        vertical="top",
                        wrap_text=True
                    )

            # ----------------------
            # 主な材料をリンク化
            # ----------------------

            for index, (_, row) in enumerate(
                top20.iterrows(),
                start=2
            ):

                code = str(
                    row["コード"]
                )

                reason_data = (
                    reason_data_all.get(
                        code,
                        {}
                    )
                )

                link = reason_data.get(
                    "main_link",
                    ""
                )

                if link:

                    material_cell = sheet.cell(
                        index,
                        headers["主な材料"]
                    )

                    material_cell.hyperlink = link
                    material_cell.style = "Hyperlink"

            # ----------------------
            # 行の高さ
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                sheet.row_dimensions[
                    row
                ].height = 120

            # ----------------------
            # 日足チャート
            # ----------------------

            chart_column = (
                sheet.max_column + 1
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
                        + str(index)
                    )

                    sheet.add_image(
                        img,
                        cell
                    )

            sheet.column_dimensions[
                get_column_letter(
                    chart_column
                )
            ].width = 30

            # ----------------------
            # TOP20最終整形
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                for col in range(
                    1,
                    sheet.max_column + 1
                ):

                    cell = sheet.cell(
                        row,
                        col
                    )

                    cell.alignment = Alignment(
                        horizontal="left",
                        vertical="top",
                        wrap_text=True
                    )

            # ----------------------
            # TOP20最終列幅
            # ----------------------

            sheet.column_dimensions["A"].width = 7
            sheet.column_dimensions["B"].width = 16
            sheet.column_dimensions["C"].width = 8
            sheet.column_dimensions["D"].width = 7
            sheet.column_dimensions["E"].width = 10
            sheet.column_dimensions["F"].width = 14
            sheet.column_dimensions["G"].width = 18
            sheet.column_dimensions["H"].width = 11

            # ----------------------
            # 主な材料を確実に
            # 折り返し・上詰め
            # ----------------------

            if "主な材料" in headers:

                material_col = headers[
                    "主な材料"
                ]

                for row in range(
                    2,
                    sheet.max_row + 1
                ):

                    sheet.cell(
                        row,
                        material_col
                    ).alignment = Alignment(
                        horizontal="left",
                        vertical="top",
                        wrap_text=True
                    )

            # ----------------------
            # チャート列ヘッダー
            # ----------------------

            sheet.cell(
                1,
                chart_column
            ).alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True
            )

            # ==================================================
            # 初動スコアTOP20シート
            # ==================================================

            sheet = workbook[
                "初動スコアTOP20"
            ]

            headers = {}

            for cell in sheet[1]:

                headers[cell.value] = (
                    cell.column
                )

            # ----------------------
            # 列幅
            # ----------------------

            sheet.column_dimensions["A"].width = 7
            sheet.column_dimensions["B"].width = 16
            sheet.column_dimensions["C"].width = 8
            sheet.column_dimensions["D"].width = 7
            sheet.column_dimensions["E"].width = 7
            sheet.column_dimensions["F"].width = 10
            sheet.column_dimensions["G"].width = 14
            sheet.column_dimensions["H"].width = 18
            sheet.column_dimensions["I"].width = 11

            # ----------------------
            # 初動スコア
            # グラデーション
            # ----------------------

            score_col = headers[
                "初動スコア"
            ]

            scores = []

            for row in range(
                2,
                sheet.max_row + 1
            ):

                value = sheet.cell(
                    row,
                    score_col
                ).value

                if value is not None:

                    try:

                        scores.append(
                            float(value)
                        )

                    except Exception:

                        pass

            if scores:

                min_score = min(scores)
                max_score = max(scores)

                for row in range(
                    2,
                    sheet.max_row + 1
                ):

                    cell = sheet.cell(
                        row,
                        score_col
                    )

                    try:

                        score = float(
                            cell.value
                        )

                    except Exception:

                        continue

                    if max_score == min_score:

                        ratio = 1

                    else:

                        ratio = (
                            score - min_score
                        ) / (
                            max_score - min_score
                        )

                    red = 255

                    green = int(
                        255 * (1 - ratio)
                    )

                    color = (
                        f"FF{green:02X}00"
                    )

                    cell.fill = PatternFill(
                        fill_type="solid",
                        start_color=color,
                        end_color=color,
                    )

            # ----------------------
            # 初動TOP20文字整形
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                for col in range(
                    1,
                    sheet.max_column + 1
                ):

                    cell = sheet.cell(
                        row,
                        col
                    )

                    cell.alignment = Alignment(
                        horizontal="left",
                        vertical="top",
                        wrap_text=True
                    )

            # ----------------------
            # 主な材料・急騰理由などを上詰め
            # ----------------------

            for header_name in [
                "分析コメント",
                "急騰理由",
                "主な材料",
                "ニュース日時",
            ]:

                if header_name not in headers:
                    continue

                col = headers[header_name]

                for row in range(
                    2,
                    sheet.max_row + 1
                ):

                    sheet.cell(
                        row,
                        col
                    ).alignment = Alignment(
                        horizontal="left",
                        vertical="top",
                        wrap_text=True
                    )

            # ----------------------
            # 主な材料をリンク化
            # ----------------------

            for index, (_, row) in enumerate(
                initial_move_top20.iterrows(),
                start=2
            ):

                code = str(
                    row["コード"]
                )

                reason_data = (
                    initial_move_reason_data_all.get(
                        code,
                        {}
                    )
                )

                link = reason_data.get(
                    "main_link",
                    ""
                )

                if link:

                    material_cell = sheet.cell(
                        index,
                        headers["主な材料"]
                    )

                    material_cell.hyperlink = link
                    material_cell.style = "Hyperlink"

            # ----------------------
            # 行の高さ
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                sheet.row_dimensions[
                    row
                ].height = 120

            # ----------------------
            # 日足チャート
            # ----------------------

            chart_column = (
                sheet.max_column + 1
            )

            sheet.cell(
                1,
                chart_column
            ).value = "日足チャート"

            for index, (_, row) in enumerate(
                initial_move_top20.iterrows(),
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
                        + str(index)
                    )

                    sheet.add_image(
                        img,
                        cell
                    )

            sheet.column_dimensions[
                get_column_letter(
                    chart_column
                )
            ].width = 30

            # ----------------------
            # 初動TOP20最終整形
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                for col in range(
                    1,
                    sheet.max_column + 1
                ):

                    cell = sheet.cell(
                        row,
                        col
                    )

                    cell.alignment = Alignment(
                        horizontal="left",
                        vertical="top",
                        wrap_text=True
                    )

            # ----------------------
            # 初動TOP20最終列幅
            # ----------------------

            sheet.column_dimensions["A"].width = 7
            sheet.column_dimensions["B"].width = 16
            sheet.column_dimensions["C"].width = 8
            sheet.column_dimensions["D"].width = 7
            sheet.column_dimensions["E"].width = 7
            sheet.column_dimensions["F"].width = 10
            sheet.column_dimensions["G"].width = 14
            sheet.column_dimensions["H"].width = 18
            sheet.column_dimensions["I"].width = 11

            # ----------------------
            # 主な材料を確実に
            # 折り返し・上詰め
            # ----------------------

            if "主な材料" in headers:

                material_col = headers[
                    "主な材料"
                ]

                for row in range(
                    2,
                    sheet.max_row + 1
                ):

                    sheet.cell(
                        row,
                        material_col
                    ).alignment = Alignment(
                        horizontal="left",
                        vertical="top",
                        wrap_text=True
                    )

            # ----------------------
            # チャート列ヘッダー
            # ----------------------

            sheet.cell(
                1,
                chart_column
            ).alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True
            )

            # ==================================================
            # TOP20を最初に開く
            # ==================================================

            workbook.active = workbook.index(
                workbook["TOP20"]
            )

            # ==================================================
            # TOP20ニュース整形
            # ==================================================

            sheet = workbook[
                "TOP20ニュース"
            ]

            sheet.freeze_panes = "A2"

            sheet.auto_filter.ref = (
                sheet.dimensions
            )

            # ----------------------
            # ヘッダー
            # ----------------------

            for cell in sheet[1]:

                cell.font = Font(
                    bold=True
                )

                cell.alignment = Alignment(
                    wrap_text=True,
                    vertical="center",
                    horizontal="center"
                )

            # ----------------------
            # 列幅
            # ----------------------

            news_widths = {
                "A": 8,
                "B": 16,
                "C": 8,
                "D": 9,
                "E": 20,
                "F": 25,
                "G": 12,
                "H": 12,
                "I": 40,
                "J": 10,
            }

            for column, width in news_widths.items():

                sheet.column_dimensions[
                    column
                ].width = width

            # ----------------------
            # セル折り返し
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                for col in range(
                    5,
                    10
                ):

                    sheet.cell(
                        row,
                        col
                    ).alignment = Alignment(
                        wrap_text=True,
                        vertical="top"
                    )

            # ----------------------
            # ニュースリンク
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                cell = sheet.cell(
                    row,
                    10
                )

                if cell.value:

                    cell.hyperlink = (
                        cell.value
                    )

                    cell.style = "Hyperlink"

            # ----------------------
            # 行の高さ
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                sheet.row_dimensions[
                    row
                ].height = 60

            # ----------------------
            # TOP20ニュース全セル
            # ----------------------

            for row in range(
                2,
                sheet.max_row + 1
            ):

                for col in range(
                    1,
                    sheet.max_column + 1
                ):

                    cell = sheet.cell(
                        row,
                        col
                    )

                    cell.alignment = Alignment(
                        wrap_text=True,
                        vertical="top"
                    )

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

    # ==========================
    # 保存完了表示
    # ==========================

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