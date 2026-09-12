import argparse
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests


CURRENT_URL = (
    "https://www.jpx.co.jp/markets/equities/"
    "ss-reg/"
)

ARCHIVE_URL = (
    "https://www.jpx.co.jp/markets/equities/"
    "ss-reg/00-archives-01.html"
)

OUTPUT_DIR = Path("data/jpx_short_sale_trigger")

REQUEST_TIMEOUT = 30
WAIT_SECONDS = 1.0


def get_html(url):
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def extract_trigger_links(html, page_url):
    pattern = re.compile(
        r'href=["\']([^"\']*?(\d{8}_Triggered_Stocks\.xls))["\']',
        re.IGNORECASE,
    )

    links = {}

    for match in pattern.finditer(html):
        href = match.group(1)
        filename = match.group(2)

        full_url = urljoin(
            page_url,
            href,
        )

        links[filename] = full_url

    return links


def download_file(url, path):
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    data = response.content

    if len(data) < 1000:
        raise RuntimeError(
            f"Downloaded file too small: {len(data)} bytes"
        )

    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        default=None,
    )

    parser.add_argument(
        "--month",
        default=None,
        help="YYYYMM",
    )

    args = parser.parse_args()

    current_month = datetime.now().strftime(
        "%Y%m"
    )

    target_month = (
        args.month
        if args.month
        else current_month
    )

    if args.url:
        page_url = args.url
    elif target_month == current_month:
        page_url = CURRENT_URL
    else:
        page_url = ARCHIVE_URL

    print("=" * 76)
    print("JPX SHORT SALE TRIGGER DOWNLOADER")
    print("=" * 76)
    print("Target month :", target_month)
    print("Page         :", page_url)

    html = get_html(page_url)

    links = extract_trigger_links(
        html,
        page_url,
    )

    links = {
        filename: url
        for filename, url in links.items()
        if filename.startswith(target_month)
    }

    links = dict(sorted(links.items()))

    print("Files found :", len(links))

    if not links:
        raise SystemExit(
            "No Triggered_Stocks XLS links found."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    downloaded = 0
    skipped = 0
    errors = 0

    total = len(links)

    for number, item in enumerate(
        links.items(),
        start=1,
    ):
        filename, url = item
        path = OUTPUT_DIR / filename

        if (
            path.exists()
            and path.stat().st_size > 1000
        ):
            print(
                f"[{number}/{total}] SKIP {filename}"
            )
            skipped += 1
            continue

        try:
            download_file(
                url,
                path,
            )

            size = path.stat().st_size

            print(
                f"[{number}/{total}] OK   "
                f"{filename} {size} bytes"
            )

            downloaded += 1

        except Exception as exc:
            print(
                f"[{number}/{total}] ERROR "
                f"{filename} : {exc}"
            )
            errors += 1

        time.sleep(WAIT_SECONDS)

    print()
    print("=" * 76)
    print("RESULT")
    print("=" * 76)
    print("Found      :", total)
    print("Downloaded :", downloaded)
    print("Skipped    :", skipped)
    print("Errors     :", errors)
    print("Directory  :", OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()
