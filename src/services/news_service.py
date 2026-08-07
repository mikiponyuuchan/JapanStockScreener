import os
import requests
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import pandas as pd


# ==========================
# Google News RSS
# ==========================

BASE_URL = "https://news.google.com/rss/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/150.0 Safari/537.36"
    )
}


# ==========================
# 1銘柄のニュース取得
# ==========================

def get_news(
    code,
    name,
    hours=72,
    limit=5
):
    """
    1銘柄のニュースを取得
    """

    query = (
        f'"{name}" 株 '
        f'when:3d'
    )

    url = (
        f"{BASE_URL}"
        f"?q={quote_plus(query)}"
        f"&hl=ja"
        f"&gl=JP"
        f"&ceid=JP:ja"
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.content
        )

    except Exception as e:

        print(
            f"ニュース取得エラー "
            f"{code} {name}: {e}"
        )

        return []


    # ==========================
    # 現在時刻
    # ==========================

    jst = timezone(
        timedelta(hours=9)
    )

    now = datetime.now(jst)

    cutoff = (
        now -
        timedelta(hours=hours)
    )


    results = []


    # ==========================
    # RSS解析
    # ==========================

    for item in root.findall(
        ".//item"
    ):

        title = item.findtext(
            "title",
            ""
        )

        link = item.findtext(
            "link",
            ""
        )

        pub_date = item.findtext(
            "pubDate",
            ""
        )

        source = item.findtext(
            "source",
            ""
        )


        if not title:
            continue


        # ----------------------
        # 日付
        # ----------------------

        published = None

        if pub_date:

            try:

                published = (
                    parsedate_to_datetime(
                        pub_date
                    )
                    .astimezone(jst)
                )

            except Exception:

                published = None


        # ----------------------
        # 古いニュースを除外
        # ----------------------

        if (
            published
            and published < cutoff
        ):
            continue


        results.append(
            {
                "code": str(code),
                "name": name,
                "title": title,
                "published": (
                    published.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if published
                    else ""
                ),
                "source": source,
                "link": link,
            }
        )


        if len(results) >= limit:
            break


    return results


# ==========================
# TOP20ニュース取得
# ==========================

def get_top20_news(top20):

    """
    TOP20全銘柄のニュースを取得
    """

    news_data = {}


    for index, row in top20.iterrows():

        code = str(
            row["コード"]
        )

        name = str(
            row["銘柄名"]
        )

        print(
            f"[{index + 1}/{len(top20)}] "
            f"{code} {name}"
        )

        news = get_news(
            code=code,
            name=name,
            hours=72,
            limit=5
        )

        news_data[code] = news

        print(
            f"  ニュース {len(news)}件"
        )


    return news_data


# ==========================
# 単体テスト
# ==========================

if __name__ == "__main__":

    print()
    print(
        "=============================="
    )
    print(
        " TOP20ニュース取得テスト"
    )
    print(
        "=============================="
    )


    # --------------------------
    # TOP20 CSV
    # --------------------------

    csv_path = os.path.join(
        "results",
        "2026-08-07_top20.csv"
    )


    if not os.path.exists(csv_path):

        print()
        print(
            "TOP20 CSVが見つかりません:"
        )
        print(csv_path)

        raise SystemExit


    print()
    print(
        "読み込み :",
        csv_path
    )


    top20 = pd.read_csv(
        csv_path,
        dtype={
            "コード": str
        }
    )


    print(
        "TOP20件数 :",
        len(top20)
    )


    # --------------------------
    # ニュース取得
    # --------------------------

    print()
    print(
        "ニュース取得開始..."
    )
    print()


    news_data = get_top20_news(
        top20
    )


    # --------------------------
    # 結果表示
    # --------------------------

    print()
    print(
        "=============================="
    )
    print(
        " ニュース取得結果"
    )
    print(
        "=============================="
    )


    for code, news_list in news_data.items():

        print()

        if not news_list:

            name = top20.loc[
                top20["コード"] == code,
                "銘柄名"
            ].iloc[0]

            print(
                f"{code} {name}"
            )

            print(
                "  ニュースなし"
            )

            continue


        for news in news_list:

            print(
                f"{news['published']} "
                f"{news['source']}"
            )

            print(
                f"  {news['title']}"
            )

            print(
                f"  {news['link']}"
            )