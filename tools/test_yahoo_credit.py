import re
import requests
from bs4 import BeautifulSoup


CODE = "1301"

URLS = [
    f"https://finance.yahoo.co.jp/quote/{CODE}.T/history?styl=margin",
    f"https://finance.yahoo.co.jp/quote/{CODE}.T/history?from={CODE}.T&styl=margin",
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 "
        "Safari/537.36"
    )
}


print("=" * 60)
print("Yahoo!ファイナンス 信用残時系列テスト")
print("=" * 60)
print()


for url in URLS:

    print("=" * 60)
    print("URL :", url)
    print("=" * 60)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20
    )

    print("status :", response.status_code)
    print("size   :", len(response.content))
    print()

    if response.status_code != 200:
        print("取得失敗")
        continue

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # ========================================================
    # 「信用残時系列」を探す
    # ========================================================

    page_text = soup.get_text(
        " ",
        strip=True
    )

    keywords = [
        "信用残時系列",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    for keyword in keywords:

        print(
            f"{keyword:10s} : "
            f"{keyword in page_text}"
        )

    print()

    # ========================================================
    # tableを確認
    # ========================================================

    tables = soup.find_all("table")

    print(
        "table数 :",
        len(tables)
    )

    print()

    for table_no, table in enumerate(
        tables,
        1
    ):

        rows = []

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            values = [
                cell.get_text(
                    " ",
                    strip=True
                )
                for cell in cells
            ]

            if values:
                rows.append(values)

        if not rows:
            continue

        print(
            f"--- table {table_no} ---"
        )

        for row in rows[:15]:

            print(row)

        print()

    # ========================================================
    # 信用関連の文字列周辺を確認
    # ========================================================

    for keyword in keywords:

        pos = page_text.find(keyword)

        if pos == -1:
            continue

        print(
            f"--- 「{keyword}」周辺 ---"
        )

        start = max(
            0,
            pos - 300
        )

        end = min(
            len(page_text),
            pos + 800
        )

        print(
            page_text[start:end]
        )

        print()