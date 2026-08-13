import requests
from bs4 import BeautifulSoup

CODE = "1301"

URL = f"https://finance.yahoo.co.jp/quote/{CODE}.T/history?styl=margin"

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
print("URL :", URL)
print()

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=20
)

print("status :", response.status_code)
print("size   :", len(response.content))
print()

if response.status_code != 200:
    print("取得失敗")
    raise SystemExit

soup = BeautifulSoup(
    response.text,
    "html.parser"
)

page_text = soup.get_text(
    " ",
    strip=True
)

print("キーワード確認")
print("-" * 60)

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
        f"{keyword:12s} : "
        f"{keyword in page_text}"
    )

print()

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

    for row in rows[:20]:
        print(row)

    print()
