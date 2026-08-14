import requests
import time


CODE = "1301"

BASE = "https://finance.yahoo.co.jp"


URLS = [
    f"{BASE}/quote/{CODE}.T",
    f"{BASE}/quote/{CODE}.T/history",
    f"{BASE}/quote/{CODE}.T/history?styl=margin",
    f"{BASE}/quote/{CODE}.T/margin",
]


HEADERS_LIST = [

    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0.0.0 "
            "Safari/537.36"
        )
    },

    {
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
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://finance.yahoo.co.jp/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },

]


print("=" * 70)
print("Yahoo!ファイナンス 信用残取得経路テスト")
print("=" * 70)
print(f"CODE : {CODE}")
print()


# ============================================================
# Test 1
# 通常 requests
# ============================================================

print("=" * 70)
print("TEST 1 : 通常 requests")
print("=" * 70)

for url in URLS:

    try:

        response = requests.get(
            url,
            headers=HEADERS_LIST[0],
            timeout=20
        )

        print(
            f"status={response.status_code:3d} "
            f"size={len(response.content):,} "
            f"url={url}"
        )

    except Exception as e:

        print(
            f"ERROR "
            f"url={url}"
        )

        print(
            repr(e)
        )


    time.sleep(1)


# ============================================================
# Test 2
# Session + Cookie
# ============================================================

print()
print("=" * 70)
print("TEST 2 : Session + Cookie")
print("=" * 70)


session = requests.Session()

session.headers.update(
    HEADERS_LIST[1]
)


try:

    response = session.get(
        BASE,
        timeout=20
    )

    print(
        "TOP PAGE"
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
        dict(session.cookies)
    )

except Exception as e:

    print(
        "TOP PAGE ERROR:",
        repr(e)
    )


time.sleep(2)


url = (
    f"{BASE}/quote/"
    f"{CODE}.T/history?styl=margin"
)


try:

    response = session.get(
        url,
        timeout=20
    )

    print()
    print(
        "CREDIT PAGE"
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

    print(
        "cookies:",
        dict(session.cookies)
    )

    print(
        "history:",
        response.history
    )

    print()

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
            f"{keyword:10s}: "
            f"{keyword in text}"
        )


    print()

    if response.status_code == 200:

        with open(
            "yahoo_credit_1301.html",
            "w",
            encoding="utf-8"
        ) as f:

            f.write(text)

        print(
            "HTML保存 : yahoo_credit_1301.html"
        )


except Exception as e:

    print(
        "CREDIT PAGE ERROR:",
        repr(e)
    )


# ============================================================
# Test 3
# 追加ヘッダーを変えて再試行
# ============================================================

print()
print("=" * 70)
print("TEST 3 : Header variation")
print("=" * 70)


header_variations = [

    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0.0.0 "
            "Safari/537.36"
        ),
        "Referer": "https://finance.yahoo.co.jp/",
    },

    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0.0.0 "
            "Safari/537.36"
        ),
        "Referer": (
            f"https://finance.yahoo.co.jp/"
            f"quote/{CODE}.T"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja-JP,ja;q=0.9",
    },

]


for i, headers in enumerate(
    header_variations,
    1
):

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        print(
            f"variation {i}: "
            f"status={response.status_code}, "
            f"size={len(response.content):,}"
        )

    except Exception as e:

        print(
            f"variation {i}: ERROR "
            f"{repr(e)}"
        )

    time.sleep(2)


print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)