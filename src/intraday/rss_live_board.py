# ================================================
# 楽天RSS 共通ライブボード管理
# ================================================

import time

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
    """
    Get the active Rakuten RSS live board.

    Excel may temporarily reject COM calls while RSS is
    updating or Excel is busy, so retry a few times before
    treating the connection as failed.
    """

    retry_count = 5
    retry_wait = 0.5
    last_error = None

    for attempt in range(
        1,
        retry_count + 1,
    ):
        try:
            excel = win32.GetActiveObject(
                "Excel.Application"
            )

            book = excel.Workbooks(
                WORKBOOK_NAME
            )

            sheet = book.Worksheets(
                SHEET_NAME
            )

            return excel, book, sheet

        except Exception as exc:
            last_error = exc

            if attempt < retry_count:
                time.sleep(
                    retry_wait
                )

    raise RuntimeError(
        "RSS live board COM connection failed "
        f"after {retry_count} attempts: "
        f"{last_error}"
    ) from last_error


def get_current_price(code):
    """
    ??????????????????????

    A? : ?????
    C? : ???
    """
    code = normalize_code(code)

    if not code:
        return None

    _, _, sheet = get_live_board()

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

        if current_code != code:
            continue

        value = sheet.Cells(
            row_number,
            3,
        ).Value

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return None


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



def clear_h1_labels():
    """
    H列から古いH1順位ラベルだけを削除する。

    A列の銘柄コードは削除しない。
    SSR-Ver1 / SSR-Ver2など他のラベルは保持する。
    I列以降の手入力メモには触れない。
    """
    excel, book, sheet = get_live_board()

    h1_labels = {
        "H1 #1",
        "H1 #2",
        "H1 #3",
    }

    changed = 0

    for row_number in range(
        START_ROW,
        END_ROW + 1,
    ):
        value = sheet.Cells(
            row_number,
            8,
        ).Value

        if not value:
            continue

        labels = [
            item.strip()
            for item in str(value).split("/")
            if item.strip()
        ]

        new_labels = [
            item
            for item in labels
            if (
                item not in h1_labels
                and not item.startswith("H1 #1 ")
                and not item.startswith("H1 #2 ")
                and not item.startswith("H1 #3 ")
            )
        ]

        if new_labels == labels:
            continue

        sheet.Cells(
            row_number,
            8,
        ).Value = " / ".join(new_labels)

        changed += 1

    excel.Calculate()
    book.Save()

    print(
        f"Old H1 labels cleared : {changed}"
    )

    return changed

def color_h1_result(sheet, row_number):
    """
    H?? H1 ?????????????

    PASS : ?
    SKIP : ?

    H1???SSR???????????????
    """

    cell = sheet.Cells(
        row_number,
        8,
    )

    value = cell.Value

    if not value:
        return

    text = str(value)

    # ???????????????
    # PASS / SKIP ?????????
    try:
        cell.Font.Color = 0
    except Exception:
        pass

    for word, color in (
        ("PASS", 16711680),  # blue
        ("SKIP", 255),       # red
    ):
        start = 0

        while True:
            index = text.find(
                word,
                start,
            )

            if index < 0:
                break

            # Excel Characters ?1???
            chars = cell.GetCharacters(
                index + 1,
                len(word),
            )

            chars.Font.Color = color

            start = (
                index
                + len(word)
            )



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

        color_h1_result(
            sheet,
            row_number,
        )

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

    color_h1_result(
        sheet,
        empty_row,
    )

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
