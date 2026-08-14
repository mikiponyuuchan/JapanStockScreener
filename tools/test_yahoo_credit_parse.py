from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup


HTML_FILE = Path("yahoo_credit_session_1301.html")


print("=" * 70)
print("Yahoo!ファイナンス 信用残HTML解析テスト")
print("=" * 70)
print()


if not HTML_FILE.exists():

    print(
        f"HTMLファイルがありません: {HTML_FILE}"
    )

    raise SystemExit(1)


html = HTML_FILE.read_text(
    encoding="utf-8"
)


print(
    f"HTMLサイズ : {len(html):,} bytes"
)

print()


soup = BeautifulSoup(
    html,
    "html.parser"
)


# ============================================================
# table確認
# ============================================================

tables = soup.find_all("table")


print(
    f"table数 : {len(tables)}"
)

print()


# ============================================================
# 信用残関連tableを探す
# ============================================================

keywords = [
    "信用残",
    "売残",
    "買残",
    "信用倍率",
    "売残増減",
    "買残増減",
]


found_tables = []


for table_no, table in enumerate(
    tables,
    1
):

    text = table.get_text(
        " ",
        strip=True
    )

    matched = [
        keyword
        for keyword in keywords
        if keyword in text
    ]

    if not matched:
        continue


    found_tables.append(
        (
            table_no,
            table
        )
    )


    print("=" * 70)
    print(
        f"信用残関連 table : {table_no}"
    )

    print(
        "含まれる項目 :",
        ", ".join(matched)
    )

    print("=" * 70)


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


    for row in rows[:20]:

        print(row)


    print()


# ============================================================
# pandasでtableを解析
# ============================================================

print("=" * 70)
print("pandas table解析")
print("=" * 70)
print()


try:

    dfs = pd.read_html(
        str(HTML_FILE)
    )

    print(
        f"pandas table数 : {len(dfs)}"
    )

    print()


    for i, df in enumerate(
        dfs,
        1
    ):

        text = " ".join(
            str(column)
            for column in df.columns
        )

        text += " "

        text += " ".join(
            df.astype(str)
            .head(10)
            .values
            .flatten()
        )


        matched = [
            keyword
            for keyword in keywords
            if keyword in text
        ]


        if not matched:
            continue


        print("=" * 70)
        print(
            f"pandas table {i}"
        )

        print(
            "関連項目 :",
            ", ".join(matched)
        )

        print("=" * 70)

        print(
            df.head(10).to_string(
                index=False
            )
        )

        print()


except Exception as e:

    print(
        "pandas解析エラー:",
        repr(e)
    )


print("=" * 70)
print("解析完了")
print("=" * 70)