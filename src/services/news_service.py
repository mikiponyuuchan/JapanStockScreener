import os
import re
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
# 急騰理由キーワード
# ==========================



REASON_RULES = [
    (
        "業績上方修正・増益",
        [
            "上方修正",
            "上期最終を",
            "通期最終を",
            "営業利益増益",
            "経常利益増益",
            "最終利益増益",
            "営業益増益",
            "経常益増益",
            "最終益増益",
            "増益",
            "利益増",
            "業績予想を上方",
            "業績予想 上方",
        ],
        100,
    ),
    (
        "決算・好業績",
        [
            "決算",
            "四半期決算",
            "業績",
            "営業利益",
            "経常利益",
            "最終利益",
            "利益",
            "増収",
        ],
        90,
    ),
    (
        "株主還元・配当",
        [
            "増配",
            "配当増額",
            "配当予想を増額",
            "自社株買い",
            "自己株取得",
            "自己株式取得",
            "株主還元",
            "還元方針",
        ],
        95,
    ),
    (
        "株主優待",
        [
            "株主優待",
            "優待制度",
            "優待新設",
            "優待拡充",
            "優待変更",
        ],
        98,
    ),
    (
        "受注・大型契約",
        [
            "受注",
            "大型受注",
            "受注獲得",
            "契約",
            "大型契約",
            "受注高",
            "受注額",
        ],
        85,
    ),
    (
        "業務提携・資本提携",
        [
            "業務提携",
            "資本提携",
            "提携",
            "協業",
            "共同開発",
            "連携",
        ],
        80,
    ),
    (
        "M&A・買収",
        [
            "Ｍ＆Ａ",
            "M&A",
            "買収",
            "子会社化",
            "株式取得",
            "TOB",
        ],
        90,
    ),
    (
        "新製品・新サービス",
        [
            "新製品",
            "新商品",
            "新サービス",
            "新技術",
            "発売",
            "販売開始",
            "サービス開始",
        ],
        70,
    ),
    (
        "業界・政策材料",
        [
            "政策",
            "政府",
            "規制緩和",
            "補助金",
            "業界",
            "市場拡大",
            "需要拡大",
        ],
        60,
    ),
]


# ==========================
# 材料とはみなさないニュース
# ==========================

NOISE_KEYWORDS = [
    "ボリンジャー",
    "移動平均線",
    "テクニカル",
    "チャート",
    "ランキング",
    "値上がりランキング",
    "値下がりランキング",
    "前日に動いた銘柄",
    "本日の【",
    "今日の【",
    "注目銘柄",
    "注目株",
    "市況",
    "相場概況",
    "寄り付き",
    "大引け",
    "東証",
    "日経平均",
]


# ==========================
# 急騰理由判定
# ==========================

def analyze_news_reason(news_list):
    """
    ニュースタイトルから急騰理由を複数判定する。

    戻り値:
        {
            "reason": "決算・好業績 ＋ 株主還元・配当",
            "main_title": "...",
            "main_source": "...",
            "main_published": "...",
            "main_link": "..."
        }
    """

    if not news_list:

        return {
            "reason": "明確な材料を確認できず",
            "main_title": "",
            "main_source": "",
            "main_published": "",
            "main_link": "",
        }


    candidates = []


    # ==========================
    # ニュースごとに判定
    # ==========================

    for news in news_list:

        title = str(
            news.get("title", "")
        )

        title_lower = title.lower()


        # --------------------------
        # 市況・テクニカル系を除外
        # --------------------------

        if any(
            keyword in title
            for keyword in NOISE_KEYWORDS
        ):
            continue


        # --------------------------
        # このニュースに該当する理由
        # --------------------------

        matched_reasons = []


        for reason, keywords, priority in REASON_RULES:

            matched = []

            for keyword in keywords:

                if keyword.lower() in title_lower:

                    matched.append(keyword)


            if matched:

                matched_reasons.append(
                    {
                        "reason": reason,
                        "priority": priority,
                        "match_count": len(matched),
                    }
                )


        # --------------------------
        # 材料があるニュースだけ保存
        # --------------------------

        if matched_reasons:

            # このニュース内で最も重要な理由
            matched_reasons.sort(
                key=lambda x: (
                    x["priority"],
                    x["match_count"],
                ),
                reverse=True,
            )

            best_reason = matched_reasons[0]


            candidates.append(
                {
                    "reason": best_reason["reason"],
                    "priority": best_reason["priority"],
                    "match_count": best_reason["match_count"],
                    "all_reasons": matched_reasons,
                    "title": title,
                    "source": news.get(
                        "source",
                        ""
                    ),
                    "published": news.get(
                        "published",
                        ""
                    ),
                    "link": news.get(
                        "link",
                        ""
                    ),
                }
            )


    # ==========================
    # 材料が見つからない場合
    # ==========================

    if not candidates:

        return {
            "reason": "明確な材料を確認できず",
            "main_title": "",
            "main_source": "",
            "main_published": "",
            "main_link": "",
        }


    # ==========================
    # 全ニュースから理由を集約
    # ==========================

    reason_scores = {}


    for candidate in candidates:

        for item in candidate["all_reasons"]:

            reason = item["reason"]

            if reason not in reason_scores:

                reason_scores[reason] = {
                    "priority": item["priority"],
                    "count": 1,
                }

            else:

                reason_scores[reason]["count"] += 1


    # ==========================
    # 理由を重要度順に並べる
    # ==========================

    sorted_reasons = sorted(
        reason_scores.items(),
        key=lambda x: (
            x[1]["priority"],
            x[1]["count"],
        ),
        reverse=True,
    )


    # ==========================
    # 複数材料を最大3種類まで表示
    # ==========================

    reasons = [
        reason
        for reason, _ in sorted_reasons[:3]
    ]


    reason_text = " ＋ ".join(
        reasons
    )


    # ==========================
    # 最重要ニュースを選択
    # ==========================

    candidates.sort(
        key=lambda x: (
            x["priority"],
            x["match_count"],
        ),
        reverse=True,
    )


    best = candidates[0]


    # ==========================
    # 結果
    # ==========================

    return {
        "reason": reason_text,
        "main_title": best["title"],
        "main_source": best["source"],
        "main_published": best["published"],
        "main_link": best["link"],
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
        f"when:3d"
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
                    ).astimezone(jst)
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


    for position, (_, row) in enumerate(
        top20.iterrows(),
        start=1
    ):

        code = str(
            row["コード"]
        )

        name = str(
            row["銘柄名"]
        )

        print(
            f"[{position}/{len(top20)}] "
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
# TOP20急騰理由分析
# ==========================

def analyze_top20_news(
    top20,
    news_data
):
    """
    TOP20ニュースから
    各銘柄の急騰理由を分析する。
    """

    analysis_data = {}


    for _, row in top20.iterrows():

        code = str(
            row["コード"]
        )

        news_list = news_data.get(
            code,
            []
        )


        analysis_data[code] = (
            analyze_news_reason(
                news_list
            )
        )


    return analysis_data


# ==========================
# 単体テスト
# ==========================

if __name__ == "__main__":

    print()
    print(
        "=============================="
    )
    print(
        " TOP20ニュース・急騰理由テスト"
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


    if not os.path.exists(
        csv_path
    ):

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
    # 急騰理由分析
    # --------------------------

    print()
    print(
        "急騰理由分析開始..."
    )


    analysis_data = (
        analyze_top20_news(
            top20,
            news_data
        )
    )


    # --------------------------
    # 結果表示
    # --------------------------

    print()
    print(
        "=============================="
    )
    print(
        " 急騰理由分析結果"
    )
    print(
        "=============================="
    )


    for _, row in top20.iterrows():

        code = str(
            row["コード"]
        )

        name = str(
            row["銘柄名"]
        )

        analysis = (
            analysis_data[code]
        )


        print()
        print(
            f"{code} {name}"
        )

        print(
            f"  急騰理由 : "
            f"{analysis['reason']}"
        )

        if analysis["main_title"]:

            print(
                f"  主な材料 : "
                f"{analysis['main_title']}"
            )

            print(
                f"  情報元   : "
                f"{analysis['main_source']}"
            )