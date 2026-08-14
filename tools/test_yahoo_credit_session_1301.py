import requests


CODE = "1301"

URL = (
    f"https://finance.yahoo.co.jp/quote/"
    f"{CODE}.T/history?styl=margin"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    "Referer": "https://finance.yahoo.co.jp/",
    "Connection": "keep-alive",
}


print("=" * 70)
print("Yahoo信用残 Session方式 1301テスト")
print("=" * 70)
print()


session = requests.Session()

session.headers.update(
    HEADERS
)


# ============================================================
# Yahooトップ
# ============================================================

print("TOP PAGE")

response = session.get(
    "https://finance.yahoo.co.jp/",
    timeout=20
)

print(
    "status :",
    response.status_code
)

print(
    "size   :",
    len(response.content)
)

print(
    "cookies:",
    session.cookies.get_dict()
)

print()


# ============================================================
# 信用残ページ
# ============================================================

print("CREDIT PAGE")

response = session.get(
    URL,
    timeout=20
)

print(
    "status :",
    response.status_code
)

print(
    "size   :",
    len(response.content)
)

print(
    "url    :",
    response.url
)

print()


# ============================================================
# HTML保存
# ============================================================

output = (
    "yahoo_credit_session_1301.html"
)

with open(
    output,
    "wb"
) as f:

    f.write(
        response.content
    )


print(
    "HTML保存 :",
    output
)

print()


# ============================================================
# 信用残キーワード
# ============================================================

text = response.text

keywords = [
    "信用残",
    "売残",
    "買残",
    "信用倍率",
    "売残増減",
    "買残増減",
]


print("KEYWORD CHECK")
print("-" * 70)


for keyword in keywords:

    print(
        f"{keyword:8s} : "
        f"{keyword in text}"
    )


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)