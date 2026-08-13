import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path
import re


# ============================================================
# 設定
# ============================================================

PAGE_URL = "https://www.jpx.co.jp/markets/statistics-equities/margin/index.html"

OUTPUT_DIR = Path("data/jpx_credit")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# JPXページ取得
# ============================================================

headers = {
    "User-Agent": "Mozilla/5.0"
}

r = requests.get(
    PAGE_URL,
    headers=headers,
    timeout=20
)

print("status :", r.status_code)

if r.status_code != 200:
    print("JPXページの取得に失敗しました。")
    raise SystemExit(1)


# ============================================================
# HTML解析
# ============================================================

soup = BeautifulSoup(r.text, "html.parser")

links = soup.find_all("a")

print("link数 :", len(links))
print()


# ============================================================
# XLSリンクを探す
# ============================================================

xls_links = []

for link in links:

    href = link.get("href")

    if not href:
        continue

    # 相対URL → 完全URL
    full_url = urljoin(PAGE_URL, href)

    # XLSファイルだけ対象
    if re.search(r"\.xls$", full_url, re.IGNORECASE):

        xls_links.append(full_url)


print("XLSリンク数 :", len(xls_links))
print()


# ============================================================
# 見つかったXLSを表示
# ============================================================

for url in xls_links:
    print(url)


if not xls_links:
    print()
    print("XLSファイルが見つかりませんでした。")
    raise SystemExit(1)


# ============================================================
# 最新XLSを選択
# ============================================================

# ファイル名に含まれる日付
# 例:
# mtdailyk2026081200.xls
#
# → 20260812

def extract_date(url):

    filename = url.split("/")[-1]

    match = re.search(r"(\d{8})", filename)

    if match:
        return match.group(1)

    return ""


xls_links.sort(
    key=extract_date,
    reverse=True
)

latest_url = xls_links[0]

latest_date = extract_date(latest_url)

print()
print("最新XLS :")
print(latest_url)
print("日付     :", latest_date)


# ============================================================
# XLSダウンロード
# ============================================================

filename = latest_url.split("/")[-1]

output_path = OUTPUT_DIR / filename

print()
print("ダウンロード中...")
print("保存先 :", output_path)

xls_response = requests.get(
    latest_url,
    headers=headers,
    timeout=30
)

print("status :", xls_response.status_code)

if xls_response.status_code != 200:
    print("XLSファイルのダウンロードに失敗しました。")
    raise SystemExit(1)


# ============================================================
# ファイル保存
# ============================================================

output_path.write_bytes(xls_response.content)

print()
print("ダウンロード成功")
print("ファイル :", output_path)
print("サイズ   :", len(xls_response.content), "bytes")