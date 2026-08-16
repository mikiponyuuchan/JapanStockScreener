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
        )

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

def create_top20_sheet(
    workbook,
    initial_move_top20,
    chart_files,
    reason_data_all,
    news_data,
):
    """
    初動スコアTOP20を1枚にまとめる。

    ・初動スコア
    ・初動判定
    ・テクニカル情報
    ・高騰理由
    ・ニュース
    ・ニュースリンク
    ・日足チャート

    を同じシートに配置する。
    """

    columns = [
        "順位",
        "コード",
        "銘柄名",
        "市場",
        "終値",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "ATR",
        "初動スコア",
        "初動シグナル",
        "押し目判定",
        "ブレイクアウト",
        "MACD GC",
        "30日高値更新",
        "出来高倍率",
        "出来高20日倍率",
        "高騰理由",
        "ニュースタイトル",
        "ニュース要約",
        "ニュース日時",
        "ニュースリンク",
        "日足チャート",
    ]

    rows = []

    if not initial_move_top20.empty:

        for rank, (_, row) in enumerate(
            initial_move_top20.iterrows(),
            start=1
        ):

            code = str(
                get_value(
                    row,
                    "コード",
                    ""
                )
            )

            reason = reason_data_all.get(
                code,
                {}
            )

            news_list = news_data.get(
                code,
                []
            )

            # ------------------------------------------
            # 高騰理由
            # ------------------------------------------

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

            # ------------------------------------------
            # ニュース情報
            # ------------------------------------------

            news_title = (
                get_reason_value(
                    reason,
                    [
                        "main_title",
                        "news_title",
                        "title",
                    ],
                    "",
                )
            )

            if not news_title:

                news_title = (
                    get_first_news_title(
                        news_list
                    )
                )

            news_summary = (
                get_reason_value(
                    reason,
                    [
                        "main_summary",
                        "news_summary",
                        "summary",
                        "description",
                    ],
                    "",
                )
            )

            if not news_summary:

                news_summary = (
                    get_first_news_summary(
                        news_list
                    )
                )

            news_date = (
                get_reason_value(
                    reason,
                    [
                        "published",
                        "date",
                        "news_date",
                    ],
                    "",
                )
            )

            if not news_date:

                news_date = (
                    get_first_news_date(
                        news_list
                    )
                )

            news_link = (
                get_reason_value(
                    reason,
                    [
                        "main_link",
                        "news_url",
                        "url",
                        "link",
                    ],
                    "",
                )
            )

            if not news_link:

                news_link = (
                    get_first_news_url(
                        news_list
                    )
                )

            # ------------------------------------------
            # 行
            # ------------------------------------------

            rows.append(
                {
                    "順位": rank,
                    "コード": code,
                    "銘柄名": get_value(
                        row,
                        "銘柄名"
                    ),
                    "市場": get_value(
                        row,
                        "市場"
                    ),
                    "終値": get_value(
                        row,
                        "終値"
                    ),
                    "前日比": get_value(
                        row,
                        "前日比"
                    ),
                    "5日騰落率": get_value(
                        row,
                        "5日騰落率"
                    ),
                    "20日騰落率": get_value(
                        row,
                        "20日騰落率"
                    ),
                    "RSI": get_value(
                        row,
                        "RSI"
                    ),
                    "ATR": get_value(
                        row,
                        "ATR"
                    ),
                    "初動スコア": get_value(
                        row,
                        "初動スコア"
                    ),
                    "初動シグナル": get_value(
                        row,
                        "InitialMoveSignal"
                    ),
                    "押し目判定": get_value(
                        row,
                        "PullbackSignal"
                    ),
                    "ブレイクアウト": get_value(
                        row,
                        "BreakoutSignal"
                    ),
                    "MACD GC": get_value(
                        row,
                        "MACD_GC"
                    ),
                    "30日高値更新": get_value(
                        row,
                        "New30High"
                    ),
                    "出来高倍率": get_value(
                        row,
                        "VolumeRatio"
                    ),
                    "出来高20日倍率": get_value(
                        row,
                        "VolumeRatio20"
                    ),
                    "高騰理由": main_reason,
                    "ニュースタイトル": news_title,
                    "ニュース要約": news_summary,
                    "ニュース日時": news_date,
                    "ニュースリンク": news_link,
                    "日足チャート": "",
                }
            )

    output = pd.DataFrame(
        rows,
        columns=columns
    )

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
            "A": 7,
            "B": 9,
            "C": 18,
            "D": 18,
            "E": 10,
            "F": 10,
            "G": 11,
            "H": 11,
            "I": 9,
            "J": 10,
            "K": 11,
            "L": 12,
            "M": 12,
            "N": 14,
            "O": 10,
            "P": 14,
            "Q": 12,
            "R": 14,
            "S": 45,
            "T": 45,
            "U": 60,
            "V": 20,
            "W": 45,
            "X": 32,
        }
    )

    # ======================================================
    # 固定
    # ======================================================

    sheet.freeze_panes = "A2"

    # ======================================================
    # 行高
    # ======================================================

    for row_number in range(
        2,
        sheet.max_row + 1
    ):

        sheet.row_dimensions[
            row_number
        ].height = 125

    # ======================================================
    # 初動スコア色
    # ======================================================

    apply_score_color(
        sheet,
        "初動スコア"
    )

    # ======================================================
    # ニュースリンク
    # ======================================================

    headers = {}

    for cell in sheet[1]:

        headers[
            cell.value
        ] = cell.column

    if (
        "ニュースリンク" in headers
    ):

        link_col = headers[
            "ニュースリンク"
        ]

        for row_number in range(
            2,
            sheet.max_row + 1
        ):

            cell = sheet.cell(
                row_number,
                link_col
            )

            if not cell.value:
                continue

            url = str(
                cell.value
            ).strip()

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

                # 表示文字を短くする
                cell.value = "ニュースを見る"

    # ======================================================
    # チャート
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

                image.width = 320
                image.height = 160

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
            )

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
            "A": 9,
            "B": 18,
            "C": 11,
            "D": 45,
            "E": 60,
            "F": 20,
            "G": 55,
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
        ].height = 60

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
        )

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