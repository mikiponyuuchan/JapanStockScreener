import requests
import pandas as pd

URL = (
    "https://webapi.yanoshin.jp/"
    "webapi/tdnet/list/20260911.json"
)

r = requests.get(
    URL,
    timeout=30,
    headers={
        "User-Agent": "JapanStockScreener/1.0"
    },
)
r.raise_for_status()

data = r.json()

print("=" * 78)
print("TDnet earnings disclosures after 15:30")
print("=" * 78)

count = 0

for item in data.get("items", []):
    tdnet = item.get("Tdnet", item)

    pubdate = str(
        tdnet.get("pubdate", "")
    ).strip()

    title = str(
        tdnet.get("title", "")
    ).strip()

    if "\u6c7a\u7b97\u77ed\u4fe1" not in title:
        continue

    try:
        dt = pd.to_datetime(pubdate)
    except Exception:
        continue

    cutoff = (
        pd.Timestamp(dt.date())
        + pd.Timedelta(
            hours=15,
            minutes=30,
        )
    )

    if dt < cutoff:
        continue

    company_code = str(
        tdnet.get("company_code", "")
    ).strip()

    if (
        len(company_code) == 5
        and company_code.endswith("0")
    ):
        code = company_code[:-1]
    else:
        code = company_code

    name = str(
        tdnet.get("company_name", "")
    ).strip()

    pdf = str(
        tdnet.get("document_url", "")
    ).strip()

    count += 1

    print()
    print("code    :", code)
    print("name    :", name)
    print("pubdate :", pubdate)
    print("title   :", title)
    print("PDF     :", pdf)

print()
print("Found :", count)
