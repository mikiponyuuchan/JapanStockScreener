import requests

CODE = "1573"

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
print("Yahoo credit test")
print("CODE:", CODE)
print("URL:", URL)
print("=" * 60)

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=20
)

print("status:", response.status_code)
print("size  :", len(response.content))

if response.status_code == 200:
    print("RESULT: HTTP 200")
else:
    print("RESULT: HTTP ERROR")
