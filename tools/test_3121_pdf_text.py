import re
import requests
from pathlib import Path

PDF_URL = (
    "https://webapi.yanoshin.jp/rd.php?"
    "https://www.release.tdnet.info/inbs/"
    "140120260911535098.pdf"
)

OUT = Path("data/analysis/3121_20260911_q3.pdf")

r = requests.get(
    PDF_URL,
    timeout=30,
    headers={
        "User-Agent": "JapanStockScreener/1.0"
    },
)

r.raise_for_status()

OUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

OUT.write_bytes(r.content)

print("status :", r.status_code)
print("type   :", r.headers.get("content-type"))
print("size   :", len(r.content))
print("saved  :", OUT)

print()

try:
    from pypdf import PdfReader

    reader = PdfReader(str(OUT))

    print("pages :", len(reader.pages))
    print("=" * 70)

    text_parts = []

    for page_no, page in enumerate(
        reader.pages[:5],
        start=1,
    ):
        text = page.extract_text() or ""
        text_parts.append(text)

        print(f"[PAGE {page_no}]")
        print(text[:4000])
        print()

    full_text = "\n".join(text_parts)

    print("=" * 70)
    print("KEYWORD CHECK")
    print("=" * 70)

    keywords = [
        "売上高",
        "営業利益",
        "経常利益",
        "親会社株主に帰属する",
        "四半期純利益",
        "通期",
        "業績予想",
    ]

    for word in keywords:
        print(
            word,
            ":",
            "FOUND" if word in full_text else "NONE"
        )

except Exception as e:
    print("PDF TEXT ERROR :", repr(e))
