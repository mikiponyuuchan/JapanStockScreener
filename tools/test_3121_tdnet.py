import requests

url = "https://webapi.yanoshin.jp/webapi/tdnet/list/20260911.json"

r = requests.get(
    url,
    timeout=30,
    headers={
        "User-Agent": "JapanStockScreener/1.0"
    },
)
r.raise_for_status()

data = r.json()

print("=" * 70)
print("3121 TDnet disclosures")
print("=" * 70)

found = 0

for item in data.get("items", []):
    tdnet = item.get("Tdnet", item)

    code = str(
        tdnet.get("company_code", "")
    ).strip()

    if code != "31210":
        continue

    found += 1

    print()
    print("pubdate :", tdnet.get("pubdate"))
    print("title   :", tdnet.get("title"))
    print("PDF     :", tdnet.get("document_url"))

print()
print("Found :", found)
