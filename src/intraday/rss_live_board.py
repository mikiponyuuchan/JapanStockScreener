# ================================================
# 楽天RSS 共通ライブボード管理
# ================================================

import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rss_excel import get_microsoft_excel


ROOT = Path(__file__).resolve().parents[2]

BASELINE_FILE = (
    ROOT
    / "data"
    / "cache"
    / "morning_baseline.csv"
)

WORKBOOK_NAME = "rakuten_rss_morning.xlsx"
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
            excel = get_microsoft_excel(
                start_if_missing=True
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




def _normal_limit_up_formula(row_number):
    """
    Return the existing normal TSE upper-limit formula.

    The reference price is obtained directly from
    Rakuten RSS.
    """
    r = row_number

    prev_close = (
        f'RssMarket(A{r}&".T","前日終値")'
    )

    return (
        f'=IFERROR(LET('
        f'p,{prev_close},'
        f'IFS('
        f'p<100,p+30,'
        f'p<200,p+50,'
        f'p<500,p+80,'
        f'p<700,p+100,'
        f'p<1000,p+150,'
        f'p<1500,p+300,'
        f'p<2000,p+400,'
        f'p<3000,p+500,'
        f'p<5000,p+700,'
        f'p<7000,p+1000,'
        f'p<10000,p+1500,'
        f'p<15000,p+3000,'
        f'p<20000,p+4000,'
        f'p<30000,p+5000,'
        f'p<50000,p+7000,'
        f'p<70000,p+10000,'
        f'p<100000,p+15000,'
        f'p<150000,p+30000,'
        f'p<200000,p+40000,'
        f'p<300000,p+50000,'
        f'p<500000,p+70000,'
        f'p<700000,p+100000,'
        f'p<1000000,p+150000,'
        f'p<1500000,p+300000,'
        f'p<2000000,p+400000,'
        f'p<3000000,p+500000,'
        f'p<5000000,p+700000,'
        f'p<7000000,p+1000000,'
        f'p<10000000,p+1500000,'
        f'p<15000000,p+3000000,'
        f'p<20000000,p+4000000,'
        f'p<30000000,p+5000000,'
        f'p<50000000,p+7000000,'
        f'TRUE,p+10000000'
        f')),"")'
    )


def _extract_jpx_expanded_limits(text):
    """
    Extract:
        stock code -> published JPX stop-high price

    Only JPX-published stop-high values are used.
    The expanded width is NOT added manually because
    tick-size rules can make that result incorrect.
    """
    import re

    result = {}

    # JPX announcements normally contain a block such as:
    #
    #   株式（コード 9246）
    #   ...
    #   ストップ高：3,345円
    #
    # Limit the search distance so a code cannot accidentally
    # pick up the price belonging to another stock.
    pattern = re.compile(
        r'コード[\s　]*([0-9A-Z]{4})'
        r'.{0,700}?'
        r'ストップ高[\s　]*[：:][\s　]*'
        r'([0-9,]+)[\s　]*円',
        re.DOTALL,
    )

    for match in pattern.finditer(text):
        code = match.group(1).strip()
        price = int(
            match.group(2).replace(",", "")
        )

        if code and price > 0:
            result[code] = price

    return result


def fetch_jpx_expanded_price_limits():
    """
    Search recent JPX market-news pages directly and return:

        stock code -> JPX-published stop-high price

    No JPX index-page URL is required.
    """
    from datetime import datetime, timedelta

    today = datetime.now().date()

    expanded = {}

    # Search recent announcement dates.
    # Seven calendar days covers weekends and normal
    # holiday sequences.
    candidate_dates = [
        today - timedelta(days=i)
        for i in range(1, 8)
    ]

    for announce_date in candidate_dates:

        date_token = announce_date.strftime(
            "%Y%m%d"
        )

        # JPX may publish several market-news articles
        # on the same day, so do not assume "-01".
        for article_no in range(1, 6):

            url = (
                "https://www.jpx.co.jp/"
                "news/1030/"
                f"{date_token}-{article_no:02d}.html"
            )

            try:
                response = requests.get(
                    url,
                    timeout=10,
                )

                if response.status_code == 404:
                    continue

                response.raise_for_status()

                soup = BeautifulSoup(
                    response.content,
                    "html.parser",
                )

                page_text = soup.get_text(
                    " ",
                    strip=True,
                )

                if "制限値幅の拡大" not in page_text:
                    continue

                # JPX announcement must explicitly say
                # that the expanded limit applies today.
                #
                # Examples:
                #   翌営業日（10月1日）
                #   翌営業日（1日）
                full_date_text = (
                    f"{today.month}月{today.day}日"
                )

                short_date_text = (
                    f"（{today.day}日）"
                )

                if (
                    full_date_text not in page_text
                    and short_date_text not in page_text
                ):
                    continue

                found = (
                    _extract_jpx_expanded_limits(
                        page_text
                    )
                )

                if found:
                    expanded.update(found)

                    print(
                        "JPX expanded-limit page : "
                        f"{url}"
                    )

            except requests.RequestException:
                # A missing/broken candidate page must
                # never stop the morning runner.
                continue

    return expanded


def refresh_expanded_price_limits():
    """
    Refresh J/K on the H1 live board.

    Normal stocks:
        J = normal TSE upper price limit.

    Expanded-limit stocks:
        J = JPX-published stop-high price.

    K always remains:
        stop-high / current price - 1

    JPX network/parser failure is non-fatal.  In that case all
    rows use the normal price-limit formula.
    """
    excel, book, sheet = get_live_board()

    expanded = {}

    try:
        expanded = (
            fetch_jpx_expanded_price_limits()
        )

        print(
            "JPX expanded price limit : CHECK OK"
        )
        print(
            "Expanded stocks          : "
            f"{len(expanded)}"
        )

    except Exception as exc:
        print(
            "JPX expanded price limit : CHECK FAILED"
        )
        print(
            "Fallback                 : "
            "NORMAL PRICE LIMIT"
        )
        print(
            f"Reason                   : {exc}"
        )

    applied = []

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

        # Always restore the normal formula first.  This is
        # important because yesterday's expanded value must not
        # remain in the workbook on a later day.
        sheet.Cells(
            row_number,
            10,
        ).Formula = (
            _normal_limit_up_formula(
                row_number
            )
        )

        if code in expanded:
            limit_price = expanded[code]

            # JPX's published stop-high is authoritative.
            sheet.Cells(
                row_number,
                10,
            ).Value = limit_price

            applied.append(
                (code, limit_price)
            )

        sheet.Cells(
            row_number,
            11,
        ).Formula = (
            f'=IFERROR('
            f'J{row_number}/C{row_number}-1,'
            f'""'
            f')'
        )

    excel.Calculate()
    book.Save()

    if applied:
        for code, price in applied:
            print(
                "Expanded limit applied  : "
                f"{code} -> {price:,}"
            )
    else:
        print(
            "Expanded limit applied  : none"
        )

    return expanded


def refresh_volume_master():
    """
    Refresh only the AA:AB volume master from the latest
    morning_baseline.csv.

    AA : CodeMaster
    AB : Prev5AvgVolumeMaster

    Existing live-board rows, RSS formulas and labels are
    not changed.
    """

    if not BASELINE_FILE.exists():
        raise RuntimeError(
            "morning_baseline.csv not found."
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
            "Baseline columns missing: "
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

    df["Prev5AvgVolumeX"] = pd.to_numeric(
        df["Prev5AvgVolume"],
        errors="coerce",
    )

    df = (
        df
        .drop_duplicates(
            subset=["CodeX"],
            keep="last",
        )
    )

    df = df[
        df["Prev5AvgVolumeX"].notna()
        & (df["Prev5AvgVolumeX"] > 0)
        & (df["CodeX"] != "")
    ]

    master_values = [
        (
            str(row.CodeX),
            float(row.Prev5AvgVolumeX),
        )
        for row in df.itertuples(
            index=False
        )
    ]

    if not master_values:
        raise RuntimeError(
            "Volume master is empty."
        )

    excel, book, sheet = get_live_board()

    sheet.Cells(
        1,
        27,
    ).Value = "CodeMaster"

    sheet.Cells(
        1,
        28,
    ).Value = "Prev5AvgVolumeMaster"

    # Remove the previous master only.
    sheet.Range(
        "AA2:AB10000"
    ).ClearContents()

    end_row = (
        len(master_values)
        + 1
    )

    sheet.Range(
        sheet.Cells(2, 27),
        sheet.Cells(end_row, 28),
    ).Value = tuple(master_values)

    excel.Calculate()
    book.Save()

    print(
        "Volume master refresh : OK"
    )
    print(
        f"Master stocks         : "
        f"{len(master_values)}"
    )

    return len(master_values)



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




def clear_j1_labels():
    """
    Remove old J1 labels from column H.

    Stock codes are preserved.

    H1 / SSR and all other labels are preserved.
    """

    excel, book, sheet = get_live_board()

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
                item != "J1 BUY"
                and not item.startswith(
                    "J1 BUY "
                )
            )
        ]

        if new_labels == labels:
            continue

        sheet.Cells(
            row_number,
            8,
        ).Value = " / ".join(
            new_labels
        )

        changed += 1

    excel.Calculate()
    book.Save()

    print(
        f"Old J1 labels cleared : "
        f"{changed}"
    )

    return changed


def add_j1_live_board_codes(codes):
    """
    Add today's J1 NEXT_OPEN stocks
    to the live board.

    Existing rows are reused by add_candidate().
    """

    added = 0

    for code in codes:
        code = normalize_code(code)

        if not code:
            continue

        row_number = add_candidate(
            code,
            "J1 BUY",
        )

        if row_number is not None:
            added += 1

    print(
        f"J1 live-board stocks  : "
        f"{added}"
    )

    return added

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
                and not item.startswith("H1 CAND #")
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

        if label:
            # H1 decision labels replace the old label
            # for the same H1 rank.
            #
            # Example:
            #   H1 #1
            #       -> H1 #1 WAIT 1234
            #
            # Other labels such as SSR-Ver1 are preserved.
            if label.startswith("H1 #"):
                parts = label.split()

                if len(parts) >= 2:
                    h1_prefix = " ".join(parts[:2])

                    labels = [
                        item
                        for item in labels
                        if not (
                            item == h1_prefix
                            or item.startswith(
                                h1_prefix + " "
                            )
                        )
                    ]

            if label not in labels:
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

def read_board_preview_safe():
    """
    Read the existing H1 board for preview only.

    Never launch Excel, write cells, or save workbook.
    """
    excel = get_microsoft_excel(
        start_if_missing=False
    )

    book = excel.Workbooks(WORKBOOK_NAME)
    sheet = book.Worksheets(SHEET_NAME)

    rows = []

    for row_number in range(
        START_ROW,
        END_ROW + 1,
    ):
        code = normalize_code(
            sheet.Cells(row_number, 1).Value
        )

        if not code:
            continue

        label = sheet.Cells(
            row_number, 8
        ).Value

        rows.append({
            "row": row_number,
            "code": code,
            "label": (
                str(label).strip()
                if label else ""
            ),
        })

    return rows
