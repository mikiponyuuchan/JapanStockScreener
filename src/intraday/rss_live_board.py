# ================================================
# 楽天RSS 共通ライブボード管理
# ================================================

import win32com.client as win32


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


def read_board():
    _, _, sheet = get_live_board()

    rows = []

    for row_number in range(
        START_ROW,
        END_ROW + 1,
    ):
        code = normalize_code(
            sheet.Cells(
                row_number,
                1,
            ).Value
        )

        if not code:
            continue

        label = sheet.Cells(
            row_number,
            8,
        ).Value

        rows.append(
            {
                "row": row_number,
                "code": code,
                "label": (
                    str(label).strip()
                    if label
                    else ""
                ),
            }
        )

    return rows


def clear_board():
    excel, book, sheet = get_live_board()

    # A列とH列だけを消す。
    # B～G列の楽天RSS式・表示設定は維持する。
    sheet.Range(
        f"A{START_ROW}:A{END_ROW}"
    ).ClearContents()

    sheet.Range(
        f"H{START_ROW}:H{END_ROW}"
    ).ClearContents()

    excel.Calculate()
    book.Save()


def add_candidate(code, label):
    """
    候補をライブボードへ追加する。

    同一コードが既にある場合は行を増やさず、
    H列の種別を統合する。
    """

    code = normalize_code(code)

    if not code:
        return None

    excel, book, sheet = get_live_board()

    empty_row = None

    for row_number in range(
        START_ROW,
        END_ROW + 1,
    ):
        current_code = normalize_code(
            sheet.Cells(
                row_number,
                1,
            ).Value
        )

        if (
            not current_code
            and empty_row is None
        ):
            empty_row = row_number

        if current_code != code:
            continue

        current_label = sheet.Cells(
            row_number,
            8,
        ).Value

        labels = []

        if current_label:
            labels.extend(
                item.strip()
                for item in str(
                    current_label
                ).split("/")
                if item.strip()
            )

        if label and label not in labels:
            labels.append(label)

        sheet.Cells(
            row_number,
            8,
        ).Value = " / ".join(labels)

        excel.Calculate()
        book.Save()

        return row_number

    if empty_row is None:
        raise RuntimeError(
            "ライブボードに空き行がありません。"
        )

    sheet.Cells(
        empty_row,
        1,
    ).Value = code

    sheet.Cells(
        empty_row,
        8,
    ).Value = label

    excel.Calculate()
    book.Save()

    return empty_row


def set_candidates(candidates):
    """
    例:
        [
            ("9816", "H1 #1"),
            ("4762", "H1 #2"),
            ("1234", "SSR1"),
        ]
    """

    clear_board()

    for code, label in candidates:
        add_candidate(
            code,
            label,
        )


def print_board():
    try:
        rows = read_board()
    except Exception as exc:
        print()
        print(
            "RSS live board display skipped : "
            f"{exc}"
        )
        return

    print()
    print("=" * 60)
    print(" 楽天RSS LIVE BOARD")
    print("=" * 60)

    if not rows:
        print("候補なし")
        return

    for item in rows:
        print(
            f'{item["row"]:2d} '
            f'{item["code"]:>5} '
            f'{item["label"]}'
        )

    print("=" * 60)
