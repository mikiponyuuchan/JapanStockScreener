import pandas as pd
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment,
)
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter

from services.chart_service import save_chart

from services.news_service import (
    get_top20_news,
    analyze_news_reason,
)

from services.tracking_service import (
    record_initial_move,
)


# ==========================================================
# 共通設定
# ==========================================================

RESULT_DIR = Path("results")
CHART_DIR = RESULT_DIR / "charts"


# ==========================================================
# 安全な値取得
# ==========================================================

def get_value(row, column, default=""):
    """
    DataFrameの列が存在しない場合でも落ちない安全な値取得。
    """

    if row is None:
        return default

    if column not in row.index:
        return default

    value = row[column]

    if pd.isna(value):
        return default

    return value


# ==========================================================
# Excel列幅
# ==========================================================

def set_column_widths(sheet, widths):
    """
    Excel列幅を設定。
    """

    for column, width in widths.items():
        sheet.column_dimensions[column].width = width


# ==========================================================
# ヘッダー書式
# ==========================================================

def format_header(sheet):
    """
    1行目をヘッダーとして整形。
    """

    for cell in sheet[1]:

        cell.font = Font(
            bold=True
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )


# ==========================================================
# 本文書式
# ==========================================================

def format_body(sheet):
    """
    本文セルを整形。
    """

    for row in sheet.iter_rows(
        min_row=2
    ):

        for cell in row:

            cell.alignment = Alignment(
                horizontal="left",
                vertical="top",
                wrap_text=True,
            )


# ==========================================================
# 初動スコア色付け
# ==========================================================

def apply_score_color(
    sheet,
    header_name,
):
    """
    初動スコアを低→高で色付けする。
    """

    headers = {}

    for cell in sheet[1]:
        headers[cell.value] = cell.column

    if header_name not in headers:
        return

    score_col = headers[
        header_name
    ]

    scores = []

    for row_number in range(
        2,
        sheet.max_row + 1
    ):

        value = sheet.cell(
            row_number,
            score_col
        ).value

        try:

            score = float(value)

            if pd.notna(score):
                scores.append(score)

        except Exception:

            continue

    if not scores:
        return

    min_score = min(scores)
    max_score = max(scores)

    for row_number in range(
        2,
        sheet.max_row + 1
    ):

        cell = sheet.cell(
            row_number,
            score_col
        )

        try:

            score = float(
                cell.value
            )

        except Exception:

            continue

        if max_score == min_score:

            ratio = 1.0

        else:

            ratio = (
                score - min_score
            ) / (
                max_score - min_score
            )

        ratio = max(
            0.0,
            min(
                1.0,
                ratio
            )
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

        cell.font = Font(
            bold=True
        )


# ==========================================================
# 初動スコアTOP20作成
# ==========================================================

def make_initial_move_top20(df):
    """
    初動スコアだけでTOP20を作成。

    強気度はランキングに使用しない。
    """

    if df is None:
        return pd.DataFrame()

    if df.empty:
        return df.copy()

    if "初動スコア" not in df.columns:

        print(
            "初動スコア列が存在しません。"
        )

        return pd.DataFrame()

    score = pd.to_numeric(
        df["初動スコア"],
        errors="coerce"
    )

    result = (
        df.loc[
            score.notna()
        ]
        .copy()
    )

    if result.empty:
        return result

    result["_score_numeric"] = (
        pd.to_numeric(
            result["初動スコア"],
            errors="coerce"
        )
    )

    result = (
        result
        .sort_values(
            "_score_numeric",
            ascending=False,
            kind="mergesort",
        )
        .head(20)
        .copy()
    )

    result.drop(
        columns=[
            "_score_numeric"
        ],
        inplace=True,
        errors="ignore",
    )

    return result


# ==========================================================
# ニュース理由から安全に値を取得
# ==========================================================

def get_reason_value(
    reason,
    keys,
    default="",
):
    """
    analyze_news_reason() の戻り値について
    キー名の違いを吸収する。
    """

    if not isinstance(
        reason,
        dict
    ):
        return default

    for key in keys:

        value = reason.get(
            key,
            ""
        )

        if value is None:
            continue

        if isinstance(
            value,
            float
        ) and pd.isna(value):

            continue

        text = str(value).strip()

        if text:
            return value

    return default


# ==========================================================
# ニュースから最初のURLを取得
# ==========================================================

def get_first_news_url(
    news_list,
):
    """
    ニュース一覧から最初のURLを取得。
    """

    if not isinstance(
        news_list,
        list
    ):
        return ""

    for news in news_list:

        if not isinstance(
            news,
            dict
        ):
            continue

        url = news.get(
            "url",
            news.get(
                "link",
                ""
            )
        )

        if url:
            return str(url)

    return ""


# ==========================================================
# ニュースからタイトルを取得
# ==========================================================

def get_first_news_title(
    news_list,
):
    """
    ニュース一覧から最初のタイトル。
    """

    if not isinstance(
        news_list,
        list
    ):
        return ""

    for news in news_list:

        if not isinstance(
            news,
            dict
        ):
            continue

        title = news.get(
            "title",
            ""
        )

        if title:
            return str(title)

    return ""


# ==========================================================
# ニュースから概要を取得
# ==========================================================

def get_first_news_summary(
    news_list,
):
    """
    ニュース一覧から最初の概要。
    """

    if not isinstance(
        news_list,
        list
    ):
        return ""

    for news in news_list:

        if not isinstance(
            news,
            dict
        ):
            continue

        summary = news.get(
            "summary",
            news.get(
                "description",
                ""
            )
        )

        if summary:
            return str(summary)

    return ""


# ==========================================================
# ニュースから日時を取得
# ==========================================================

def get_first_news_date(
    news_list,
):
    """
    ニュース一覧から最初の日時。
    """

    if not isinstance(
        news_list,
        list
    ):
        return ""

    for news in news_list:

        if not isinstance(
            news,
            dict
        ):
            continue

        published = news.get(
            "published",
            news.get(
                "date",
                ""
            )
        )

        if published:
            return str(
                published
            )

    return ""


# ==========================================================
# チャート作成
# ==========================================================

def create_charts(
    initial_move_top20,
):
    """
    初動スコアTOP20の日足チャートを作成。
    """

    chart_files = {}

    if initial_move_top20.empty:
        return chart_files

    for _, row in initial_move_top20.iterrows():

        code = str(
            get_value(
                row,
                "コード",
                ""
            )
        ).replace(".0", "")

        if not code:
            continue

        try:

            chart = save_chart(
                code
            )

        except Exception as e:

            print(
                f"チャート作成ERROR {code} : {e}"
            )

            continue

        if chart:

            chart_files[
                code
            ] = Path(
                chart
            )

    print(
        f"日足チャート作成完了 ({len(chart_files)}銘柄)"
    )

    return chart_files


# ==========================================================
# DataFrame → Excel
# ==========================================================

def dataframe_to_sheet(
    workbook,
    sheet_name,
    dataframe,
):
    """
    DataFrameをExcelシートに出力。
    """

    if sheet_name in workbook.sheetnames:

        del workbook[
            sheet_name
        ]

    sheet = workbook.create_sheet(
        sheet_name
    )

    if dataframe is None:
        dataframe = pd.DataFrame()

    if dataframe.empty:
        return sheet

    # ヘッダー
    for col_index, column in enumerate(
        dataframe.columns,
        start=1
    ):

        sheet.cell(
            1,
            col_index
        ).value = column

    # データ
    for row_index, (_, row) in enumerate(
        dataframe.iterrows(),
        start=2
    ):

        for col_index, column in enumerate(
            dataframe.columns,
            start=1
        ):

            value = row[column]

            if pd.isna(value):
                value = ""

            sheet.cell(
                row_index,
                col_index
            ).value = value

    format_header(
        sheet
    )

    format_body(
        sheet
    )

    sheet.freeze_panes = "A2"

    sheet.auto_filter.ref = (
        sheet.dimensions
    )

    return sheet


# ==========================================================
# 初動スコアTOP20 Excel
# ==========================================================

# ==========================================================
# 初動スコアTOP20 Excel
# ==========================================================

def create_top20_sheet(
    workbook,
    initial_move_top20,
    chart_files,
    reason_data_all,
    news_data,
):
    """
    初動スコアTOP20をコンパクトに1枚へまとめる。

    表示項目：
        コード
        銘柄名
        終値
        初動スコア
        高騰理由
        ニュース
        ニュース日時
        日足チャート
    """

    # ======================================================
    # TOP20の列
    # ======================================================

    columns = [
        "コード",
        "銘柄名",
        "終値",
        "初動スコア",
        "高騰理由",
        "ニュース",
        "ニュース日時",
        "日足チャート",
    ]

    rows = []

    # ======================================================
    # データ作成
    # ======================================================

    if not initial_move_top20.empty:

        for _, row in initial_move_top20.iterrows():

            # ------------------------------------------------
            # コード
            # ------------------------------------------------

            code = str(
                get_value(
                    row,
                    "コード",
                    ""
                )
            ).replace(
                ".0",
                ""
            )

            # ------------------------------------------------
            # ニュース情報
            # ------------------------------------------------

            reason = reason_data_all.get(
                code,
                {}
            )

            news_list = news_data.get(
                code,
                []
            )

            # ------------------------------------------------
            # 高騰理由
            # ------------------------------------------------

            main_reason = get_reason_value(
                reason,
                [
                    "main_reason",
                    "reason",
                    "summary",
                    "main_material",
                    "material",
                    "headline",
                ],
                "",
            )

            # ------------------------------------------------
            # ニュースタイトル
            # ------------------------------------------------

            news_title = get_reason_value(
                reason,
                [
                    "main_title",
                    "news_title",
                    "title",
                ],
                "",
            )

            if not news_title:

                news_title = get_first_news_title(
                    news_list
                )

            # ------------------------------------------------
            # ニュース日時
            # ------------------------------------------------

            news_date = get_reason_value(
                reason,
                [
                    "published",
                    "date",
                    "news_date",
                ],
                "",
            )

            if not news_date:

                news_date = get_first_news_date(
                    news_list
                )

            # ------------------------------------------------
            # ニュースURL
            # ------------------------------------------------

            news_link = get_reason_value(
                reason,
                [
                    "main_link",
                    "news_url",
                    "url",
                    "link",
                ],
                "",
            )

            if not news_link:

                news_link = get_first_news_url(
                    news_list
                )

            # ------------------------------------------------
            # ニュース表示
            #
            # URLがあれば「ニュースを見る」と表示。
            # URLが無ければニュースタイトルを表示。
            # ------------------------------------------------

            if news_link:

                news_display = (
                    news_title
                    if news_title
                    else "ニュースを見る"
                )

            else:

                news_display = news_title

            # ------------------------------------------------
            # 高騰理由のフォールバック
            #
            # ニュース理由分析が空だった場合でも、
            # 初動スコアの主要な根拠を表示する。
            # ------------------------------------------------

            if not main_reason:

                reasons = []

                if get_value(
                    row,
                    "InitialMoveSignal",
                    False
                ) is True:

                    reasons.append(
                        "初動シグナル"
                    )

                if get_value(
                    row,
                    "BreakoutSignal",
                    False
                ) is True:

                    reasons.append(
                        "ブレイクアウト"
                    )

                if get_value(
                    row,
                    "New30High",
                    False
                ) is True:

                    reasons.append(
                        "30日高値更新"
                    )

                if get_value(
                    row,
                    "MACD_GC",
                    False
                ) is True:

                    reasons.append(
                        "MACD GC"
                    )

                volume_ratio = get_value(
                    row,
                    "VolumeRatio",
                    ""
                )

                try:

                    volume_ratio_float = float(
                        volume_ratio
                    )

                    if volume_ratio_float >= 1.5:

                        reasons.append(
                            f"出来高{volume_ratio_float:.1f}倍"
                        )

                except Exception:

                    pass

                price_change = get_value(
                    row,
                    "前日比",
                    ""
                )

                try:

                    price_change_float = float(
                        price_change
                    )

                    if price_change_float > 0:

                        reasons.append(
                            f"当日+{price_change_float:.1f}%"
                        )

                except Exception:

                    pass

                if reasons:

                    main_reason = " / ".join(
                        reasons
                    )

                else:

                    main_reason = (
                        "初動スコアによる抽出"
                    )

            # ------------------------------------------------
            # 1行追加
            # ------------------------------------------------

            rows.append(
                {
                    "コード": code,

                    "銘柄名": get_value(
                        row,
                        "銘柄名",
                        ""
                    ),

                    "終値": get_value(
                        row,
                        "終値",
                        ""
                    ),

                    "初動スコア": get_value(
                        row,
                        "初動スコア",
                        ""
                    ),

                    "高騰理由": main_reason,

                    "ニュース": news_display,

                    "ニュース日時": news_date,

                    # Excel上では空欄。
                    # 下で画像を直接貼り付ける。
                    "日足チャート": "",
                }
            )

    # ======================================================
    # DataFrame作成
    # ======================================================

    output = pd.DataFrame(
        rows,
        columns=columns
    )

    # ======================================================
    # シート作成
    # ======================================================

    sheet = dataframe_to_sheet(
        workbook,
        "TOP20",
        output,
    )

    # ======================================================
    # 列幅
    # ======================================================

    set_column_widths(
        sheet,
        {
            "A": 7,    # コード
            "B": 15,   # 銘柄名
            "C": 9,    # 終値
            "D": 7,    # 初動スコア
            "E": 22,   # 高騰理由
            "F": 22,   # ニュース
            "G": 11,   # ニュース日時
            "H": 25,   # 日足チャート
        }
    )

    # ======================================================
    # 固定
    # ======================================================

    sheet.freeze_panes = "A2"

    # ======================================================
    # オートフィルター
    # ======================================================

    if sheet.max_row >= 1:

        sheet.auto_filter.ref = (
            sheet.dimensions
        )

    # ======================================================
    # 行高
    # ======================================================

    for row_number in range(
        2,
        sheet.max_row + 1
    ):

        sheet.row_dimensions[
            row_number
        ].height = 105

    # ======================================================
    # 初動スコア色付け
    # ======================================================

    apply_score_color(
        sheet,
        "初動スコア"
    )

    # ======================================================
    # ヘッダー位置取得
    # ======================================================

    headers = {}

    for cell in sheet[1]:

        headers[
            cell.value
        ] = cell.column

    # ======================================================
    # ニュースリンク
    #
    # 「ニュース」セルそのものをクリック可能にする。
    # ======================================================

    news_col = headers.get(
        "ニュース"
    )

    if (
        news_col is not None
        and not initial_move_top20.empty
    ):

        for row_number, (
            _,
            row
        ) in enumerate(
            initial_move_top20.iterrows(),
            start=2
        ):

            code = str(
                get_value(
                    row,
                    "コード",
                    ""
                )
            ).replace(
                ".0",
                ""
            )

            reason = reason_data_all.get(
                code,
                {}
            )

            news_list = news_data.get(
                code,
                []
            )

            # ----------------------------------------------
            # URL
            # ----------------------------------------------

            news_link = get_reason_value(
                reason,
                [
                    "main_link",
                    "news_url",
                    "url",
                    "link",
                ],
                "",
            )

            if not news_link:

                news_link = get_first_news_url(
                    news_list
                )

            if not news_link:

                continue

            news_link = str(
                news_link
            ).strip()

            if not (
                news_link.startswith(
                    "http://"
                )
                or
                news_link.startswith(
                    "https://"
                )
            ):

                continue

            # ----------------------------------------------
            # ニュースタイトル
            # ----------------------------------------------

            news_title = get_reason_value(
                reason,
                [
                    "main_title",
                    "news_title",
                    "title",
                ],
                "",
            )

            if not news_title:

                news_title = get_first_news_title(
                    news_list
                )

            cell = sheet.cell(
                row_number,
                news_col
            )

            # タイトルがあればタイトル表示
            # なければ「ニュースを見る」
            if news_title:

                cell.value = news_title

            else:

                cell.value = "ニュースを見る"

            cell.hyperlink = news_link
            cell.style = "Hyperlink"

            cell.alignment = Alignment(
                horizontal="left",
                vertical="top",
                wrap_text=True,
            )

    # ======================================================
    # 日足チャート
    #
    # chart_files:
    #     {
    #         "3994": Path(...),
    #         "7936": Path(...),
    #         ...
    #     }
    #
    # TOP20のコードと照合して画像を直接貼り付ける。
    # ======================================================

    chart_col = headers.get(
        "日足チャート"
    )

    if (
        chart_col is not None
        and not initial_move_top20.empty
    ):

        for row_number, (
            _,
            row
        ) in enumerate(
            initial_move_top20.iterrows(),
            start=2
        ):

            code = str(
                get_value(
                    row,
                    "コード",
                    ""
                )
            ).replace(
                ".0",
                ""
            )

            chart_path = chart_files.get(
                code
            )

            if not chart_path:

                continue

            chart_path = Path(
                chart_path
            )

            if not chart_path.exists():

                continue

            try:

                image = Image(
                    str(chart_path)
                )

                # コンパクトTOP20用
                image.width = 300
                image.height = 150

                cell = (
                    get_column_letter(
                        chart_col
                    )
                    + str(row_number)
                )

                sheet.add_image(
                    image,
                    cell
                )

            except Exception as e:

                print(
                    f"画像貼付ERROR {code} : {e}"
                )

    # ======================================================
    # チャート列の中央配置
    # ======================================================

    if chart_col is not None:

        for row_number in range(
            2,
            sheet.max_row + 1
        ):

            cell = sheet.cell(
                row_number,
                chart_col
            )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

    # ======================================================
    # 完了
    # ======================================================

    return sheet

# ==========================================================
# ニュースシート
# ==========================================================

def create_news_sheet(
    workbook,
    initial_move_top20,
    news_data,
):
    """
    初動TOP20の詳細ニュース。

    TOP20本体とは別の補助シート。
    """

    rows = []

    if not initial_move_top20.empty:

        for _, row in initial_move_top20.iterrows():

            code = str(
                get_value(
                    row,
                    "コード",
                    ""
                )
            ).replace(".0", "")
            name = get_value(
                row,
                "銘柄名",
                ""
            )

            score = get_value(
                row,
                "初動スコア",
                ""
            )

            news_list = news_data.get(
                code,
                []
            )

            if not news_list:

                rows.append(
                    {
                        "コード": code,
                        "銘柄名": name,
                        "初動スコア": score,
                        "ニュースタイトル": "",
                        "ニュース概要": "",
                        "ニュース日時": "",
                        "ニュースURL": "",
                    }
                )

                continue

            for news in news_list:

                if not isinstance(
                    news,
                    dict
                ):
                    continue

                rows.append(
                    {
                        "コード": code,
                        "銘柄名": name,
                        "初動スコア": score,
                        "ニュースタイトル": news.get(
                            "title",
                            ""
                        ),
                        "ニュース概要": news.get(
                            "summary",
                            news.get(
                                "description",
                                ""
                            )
                        ),
                        "ニュース日時": news.get(
                            "published",
                            news.get(
                                "date",
                                ""
                            )
                        ),
                        "ニュースURL": news.get(
                            "url",
                            news.get(
                                "link",
                                ""
                            )
                        ),
                    }
                )

    news_df = pd.DataFrame(
        rows
    )

    sheet = dataframe_to_sheet(
        workbook,
        "TOP20ニュース",
        news_df,
    )

    set_column_widths(
        sheet,
        {
            "A": 7,    # コード
            "B": 15,   # 銘柄名
            "C": 9,    # 終値
            "D": 7,    # 初動スコア
            "E": 22,   # 高騰理由
            "F": 22,   # ニュース
            "G": 11,   # ニュース日時
            "H": 25,   # 日足チャート
        }
    )

    if not news_df.empty:

        headers = {}

        for cell in sheet[1]:
            headers[
                cell.value
            ] = cell.column

        if "ニュースURL" in headers:

            url_col = headers[
                "ニュースURL"
            ]

            for row_number in range(
                2,
                sheet.max_row + 1
            ):

                cell = sheet.cell(
                    row_number,
                    url_col
                )

                if not cell.value:
                    continue

                url = str(
                    cell.value
                )

                if (
                    url.startswith(
                        "http://"
                    )
                    or
                    url.startswith(
                        "https://"
                    )
                ):

                    cell.hyperlink = url
                    cell.style = "Hyperlink"

                    cell.value = (
                        "ニュースを見る"
                    )

    for row_number in range(
        2,
        sheet.max_row + 1
    ):

        sheet.row_dimensions[
            row_number
        ].height = 105

    return sheet


# ==========================================================
# ニュース理由分析
# ==========================================================

def analyze_top20_news(
    initial_move_top20,
    news_data,
):
    """
    初動TOP20のニュースから
    高騰理由を分析する。
    """

    reason_data_all = {}

    if initial_move_top20.empty:
        return reason_data_all

    for _, row in initial_move_top20.iterrows():

        code = str(
            get_value(
                row,
                "コード",
                ""
            )
        ).replace(".0", "")

        news_list = news_data.get(
            code,
            []
        )

        try:

            reason = analyze_news_reason(
                news_list
            )

        except Exception as e:

            print(
                f"ニュース理由分析ERROR {code} : {e}"
            )

            reason = {}

        if not isinstance(
            reason,
            dict
        ):

            reason = {}

        reason_data_all[
            code
        ] = reason

    return reason_data_all


# ==========================================================
# TOP20 CSV
# ==========================================================

def save_top20_csv(
    initial_move_top20,
    top20_csv,
):
    """
    初動スコアTOP20 CSV保存。
    """

    initial_move_top20.to_csv(
        top20_csv,
        index=False,
        encoding="utf-8-sig",
    )


# ==========================================================
# メイン
# ==========================================================

def save_result(df):

    # ======================================================
    # フォルダ
    # ======================================================

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    CHART_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    csv_file = (
        RESULT_DIR
        / f"{today}_stock_result.csv"
    )

    excel_file = (
        RESULT_DIR
        / f"{today}_stock_result.xlsx"
    )

    top20_csv = (
        RESULT_DIR
        / f"{today}_top20.csv"
    )

    # ======================================================
    # 全銘柄CSV
    # ======================================================

    df.to_csv(
        csv_file,
        index=False,
        encoding="utf-8-sig",
    )

    # ======================================================
    # 初動スコアTOP20
    # ======================================================

    initial_move_top20 = (
        make_initial_move_top20(
            df
        )
    )

    print()
    print(
        "=============================="
    )
    print(
        " 初動スコア TOP20"
    )
    print(
        "=============================="
    )

    if initial_move_top20.empty:

        print(
            "初動スコア対象銘柄なし"
        )

    else:

        display_columns = [
            column
            for column in [
                "コード",
                "銘柄名",
                "終値",
                "5日騰落率",
                "20日騰落率",
                "RSI",
                "ATR",
                "初動スコア",
            ]
            if column in initial_move_top20.columns
        ]

        print(
            initial_move_top20[
                display_columns
            ].to_string(
                index=False
            )
        )

    # ======================================================
    # 初動追跡
    # ======================================================

    print()
    print(
        "過去の初動銘柄を追跡中..."
    )

    try:

        record_initial_move(
            initial_move_top20
        )

    except Exception as e:

        print(
            "初動追跡ERROR :",
            e
        )

    # ======================================================
    # ニュース取得
    # ======================================================

    print()
    print(
        "初動スコアTOP20ニュース取得中..."
    )

    news_data = {}

    if not initial_move_top20.empty:

        try:

            news_data = get_top20_news(
                initial_move_top20
            )

        except Exception as e:

            print(
                "ニュース取得ERROR :",
                e
            )

            news_data = {}

    print(
        "初動スコアTOP20ニュース取得完了"
    )

    print(
        f"news_data件数 : {len(news_data)}"
    )

    # ======================================================
    # ニュース理由分析
    # ======================================================

    print()
    print(
        "初動スコアTOP20ニュース理由分析中..."
    )

    reason_data_all = (
        analyze_top20_news(
            initial_move_top20,
            news_data,
        )
    )

    print(
        "ニュース理由分析完了"
    )

    print(
        f"reason_data_all件数 : {len(reason_data_all)}"
    )

    # ======================================================
    # チャート
    # ======================================================

    chart_files = {}

    if not initial_move_top20.empty:

        print()
        print(
            "日足チャート作成中..."
        )

        chart_files = create_charts(
            initial_move_top20
        )

        print(
            f"chart_files件数 : {len(chart_files)}"
        )

    # ======================================================
    # Excel
    # ======================================================

    print()
    print(
        "Excel作成中..."
    )

    workbook = Workbook()

    default_sheet = (
        workbook.active
    )

    workbook.remove(
        default_sheet
    )

    print()
    print("===== chart_files DEBUG =====")

    for k in list(chart_files.keys())[:5]:
        print("chart key :", repr(k))

    print()

    for _, row in initial_move_top20.head().iterrows():
        print(
            "top20 code:",
            repr(str(get_value(row, "コード", "")))
        )

    print("=============================")

    # ======================================================
    # TOP20
    # ======================================================

    create_top20_sheet(
        workbook,
        initial_move_top20,
        chart_files,
        reason_data_all,
        news_data,
    )

    # ======================================================
    # TOP20ニュース
    # ======================================================

    create_news_sheet(
        workbook,
        initial_move_top20,
        news_data,
    )

    # ======================================================
    # 全銘柄
    # ======================================================

    result_sheet = dataframe_to_sheet(
        workbook,
        "全銘柄",
        df,
    )

    result_sheet.freeze_panes = "A2"

    apply_score_color(
        result_sheet,
        "初動スコア",
    )

    # ======================================================
    # 初動追跡
    # ======================================================

    tracking_file = Path(
        "data/tracking/initial_move_tracking.csv"
    )

    if tracking_file.exists():

        try:

            tracking_df = pd.read_csv(
                tracking_file,
                encoding="utf-8-sig",
            )

        except Exception:

            tracking_df = pd.DataFrame()

    else:

        tracking_df = pd.DataFrame()

    dataframe_to_sheet(
        workbook,
        "初動追跡",
        tracking_df,
    )

    # ======================================================
    # シート順
    # ======================================================

    desired_order = [
        "TOP20",
        "TOP20ニュース",
        "全銘柄",
        "初動追跡",
    ]

    for sheet_name in reversed(
        desired_order
    ):

        if sheet_name not in workbook.sheetnames:
            continue

        sheet = workbook[
            sheet_name
        ]

        workbook._sheets.remove(
            sheet
        )

        workbook._sheets.insert(
            0,
            sheet
        )

    # ======================================================
    # TOP20を最初に表示
    # ======================================================

    if "TOP20" in workbook.sheetnames:

        workbook.active = workbook.index(
            workbook["TOP20"]
        )

    # ======================================================
    # Excel保存
    # ======================================================

    try:

        workbook.save(
            excel_file
        )

    except PermissionError:

        print()
        print(
            "=============================================="
        )
        print(
            f"Excelを保存できません: {excel_file}"
        )
        print(
            "Excelファイルが開いている可能性があります。"
        )
        print(
            "Excelを閉じてから再実行してください。"
        )
        print(
            "=============================================="
        )

        return

    # ======================================================
    # TOP20 CSV
    # ======================================================

    save_top20_csv(
        initial_move_top20,
        top20_csv,
    )

    # ======================================================
    # 完了表示
    # ======================================================

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