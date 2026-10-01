from pathlib import Path

path = Path("src/intraday/rss_live_board.py")
text = path.read_text(encoding="utf-8")

start = text.index(
    "def fetch_jpx_expanded_price_limits():"
)

end = text.index(
    "\ndef refresh_expanded_price_limits():",
    start,
)

new_func = r'''def fetch_jpx_expanded_price_limits():
    """
    Search recent JPX market-news pages directly and return:

        stock code -> JPX-published stop-high price

    No JPX index-page URL is required.
    """
    from datetime import datetime, timedelta

    today = datetime.now().date()

    expanded = {}

    # Search recent announcement dates.
    # Seven calendar days covers weekends and normal
    # holiday sequences.
    candidate_dates = [
        today - timedelta(days=i)
        for i in range(1, 8)
    ]

    for announce_date in candidate_dates:

        date_token = announce_date.strftime(
            "%Y%m%d"
        )

        # JPX may publish several market-news articles
        # on the same day, so do not assume "-01".
        for article_no in range(1, 6):

            url = (
                "https://www.jpx.co.jp/"
                "news/1030/"
                f"{date_token}-{article_no:02d}.html"
            )

            try:
                response = requests.get(
                    url,
                    timeout=10,
                )

                if response.status_code == 404:
                    continue

                response.raise_for_status()

                soup = BeautifulSoup(
                    response.content,
                    "html.parser",
                )

                page_text = soup.get_text(
                    " ",
                    strip=True,
                )

                if "制限値幅の拡大" not in page_text:
                    continue

                # JPX announcement must explicitly say
                # that the expanded limit applies today.
                #
                # Examples:
                #   翌営業日（10月1日）
                #   翌営業日（1日）
                full_date_text = (
                    f"{today.month}月{today.day}日"
                )

                short_date_text = (
                    f"（{today.day}日）"
                )

                if (
                    full_date_text not in page_text
                    and short_date_text not in page_text
                ):
                    continue

                found = (
                    _extract_jpx_expanded_limits(
                        page_text
                    )
                )

                if found:
                    expanded.update(found)

                    print(
                        "JPX expanded-limit page : "
                        f"{url}"
                    )

            except requests.RequestException:
                # A missing/broken candidate page must
                # never stop the morning runner.
                continue

    return expanded

'''

text = (
    text[:start]
    + new_func
    + text[end:]
)

path.write_text(
    text,
    encoding="utf-8",
)

print("PATCHED : JPX direct page discovery")
print("PATCHED :", path)
print("COMPLETE")
