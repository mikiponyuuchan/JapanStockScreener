from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

LIVE_BOARD = ROOT / "src" / "intraday" / "rss_live_board.py"
RUNNER = ROOT / "src" / "intraday" / "rss_morning_runner.py"

LIVE_BACKUP = ROOT / "src" / "intraday" / "rss_live_board_before_expanded_limit.py"
RUNNER_BACKUP = ROOT / "src" / "intraday" / "rss_morning_runner_before_expanded_limit.py"


# ============================================================
# Backup
# ============================================================

shutil.copy2(LIVE_BOARD, LIVE_BACKUP)
shutil.copy2(RUNNER, RUNNER_BACKUP)


# ============================================================
# Patch rss_live_board.py
# ============================================================

text = LIVE_BOARD.read_text(encoding="utf-8")

if "def refresh_expanded_price_limits(" in text:
    raise SystemExit(
        "rss_live_board.py is already patched."
    )


# requests / BeautifulSoup imports
old = """import pandas as pd
import win32com.client as win32
"""

new = """import pandas as pd
import requests
from bs4 import BeautifulSoup
import win32com.client as win32
"""

if old not in text:
    raise RuntimeError(
        "Import insertion point not found "
        "in rss_live_board.py"
    )

text = text.replace(old, new, 1)


# ------------------------------------------------------------
# Add JPX expanded-price-limit functions before
# refresh_volume_master()
# ------------------------------------------------------------

marker = "\ndef refresh_volume_master():\n"

if marker not in text:
    raise RuntimeError(
        "refresh_volume_master insertion point "
        "not found."
    )

block = r'''

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
    Find recent JPX price-limit-expansion announcements and
    return the stop-high prices applicable today.

    Failure is intentionally non-fatal.  The caller can
    continue with normal TSE price limits.
    """
    import re
    from datetime import datetime, timedelta
    from urllib.parse import urljoin

    today = datetime.now().date()

    # The JPX announcement is normally made on the preceding
    # business day.  Search several calendar days so weekends
    # and holidays do not break the morning runner.
    candidate_dates = [
        today - timedelta(days=i)
        for i in range(1, 8)
    ]

    index_url = (
        "https://www.jpx.co.jp/news/1030/"
        "index.html"
    )

    response = requests.get(
        index_url,
        timeout=15,
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.content,
        "html.parser",
    )

    links = []

    date_tokens = {
        d.strftime("%Y%m%d")
        for d in candidate_dates
    }

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "")

        if not any(
            token in href
            for token in date_tokens
        ):
            continue

        full_url = urljoin(
            index_url,
            href,
        )

        if full_url not in links:
            links.append(full_url)

    expanded = {}

    for url in links:
        try:
            page = requests.get(
                url,
                timeout=15,
            )
            page.raise_for_status()

            page_soup = BeautifulSoup(
                page.content,
                "html.parser",
            )

            text = page_soup.get_text(
                " ",
                strip=True,
            )

            if "制限値幅の拡大" not in text:
                continue

            # The announcement must explicitly state that the
            # expansion applies on today's month/day.
            today_text = (
                f"{today.month}月{today.day}日"
            )

            if today_text not in text:
                continue

            found = (
                _extract_jpx_expanded_limits(
                    text
                )
            )

            expanded.update(found)

        except Exception:
            # One malformed/unavailable announcement must not
            # stop examination of the other candidates.
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

'''

text = text.replace(
    marker,
    block + marker,
    1,
)

LIVE_BOARD.write_text(
    text,
    encoding="utf-8",
)


# ============================================================
# Patch rss_morning_runner.py
# ============================================================

text = RUNNER.read_text(
    encoding="utf-8"
)

old = """    refresh_volume_master,
)"""

new = """    refresh_volume_master,
    refresh_expanded_price_limits,
)"""

if old not in text:
    raise RuntimeError(
        "rss_live_board import block not found."
    )

text = text.replace(
    old,
    new,
    1,
)


old = """    refresh_volume_master()

    # ============================================
    # Load the 09:20-side full-market panel."""

new = """    refresh_volume_master()

    # ============================================
    # Refresh today's JPX expanded price limits.
    #
    # This must never stop the Morning Runner.
    # The helper automatically falls back to the
    # normal TSE price-limit formula.
    # ============================================

    print()
    print("=" * 60)
    print(" JPX EXPANDED PRICE LIMIT")
    print("=" * 60)

    try:
        refresh_expanded_price_limits()
    except Exception as exc:
        print(
            "Expanded price-limit refresh failed."
        )
        print(
            "Morning Runner will continue."
        )
        print(
            f"Reason : {exc}"
        )

    # ============================================
    # Load the 09:20-side full-market panel."""

if old not in text:
    raise RuntimeError(
        "Morning Runner insertion point not found."
    )

text = text.replace(
    old,
    new,
    1,
)

RUNNER.write_text(
    text,
    encoding="utf-8",
)


print("PATCHED : JPX expanded price-limit support")
print("BACKUP  :", LIVE_BACKUP)
print("BACKUP  :", RUNNER_BACKUP)
print("PATCHED :", LIVE_BOARD)
print("PATCHED :", RUNNER)
print("COMPLETE")
