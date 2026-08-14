import time

import pandas as pd
import requests


# ============================================================
# 設定
# ============================================================

CODES = [
    "1301",
    "1332",
    "1605",
    "1801",
    "2002",
]

DELAY = 10

BASE_URL = "https://finance.yahoo.co.jp"

HEADERS = {
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
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    "Referer": "https://finance.yahoo.co.jp/",
    "Connection": "keep-alive",
}


# ============================================================
# 信用残テーブル解析
# ============================================================

def parse_credit_table(html):

    try:

        tables = pd.read_html(
            html
        )

    except Exception as e:

        print(
            f"pd.read_html ERROR : {e}"
        )

        return None


    required = {
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    }


    for table in tables:

        columns = {
            str(column)
            for column in table.columns
        }

        if required.issubset(columns):

            return table[
                [
                    "日付",
                    "売残",
                    "買残",
                    "売残増減",
                    "買残増減",
                    "信用倍率",
                ]
            ].copy()


    return None


# ============================================================
# 1銘柄取得
# ============================================================

def get_credit(
    session,
    code
):

    url = (
        f"{BASE_URL}/quote/"
        f"{code}.T/history?styl=margin"
    )


    try:

        response = session.get(
            url,
            timeout=20
        )

    except Exception as e:

        print(
            f"[{code}] REQUEST ERROR : {e}"
        )

        return None


    print(
        f"[{code}] HTTP {response.status_code} "
        f"size={len(response.content):,}"
    )


    if response.status_code != 200:

        return None


    # --------------------------------------------------------
    # キーワード確認
    # --------------------------------------------------------

    html = response.text

    keywords = [
        "信用残",
        "売残",
        "買残",
        "信用倍率",
    ]


    keyword_result = {
        keyword: keyword in html
        for keyword in keywords
    }


    print(
        f"[{code}] keywords : "
        f"{keyword_result}"
    )


    # --------------------------------------------------------
    # pandas解析
    # --------------------------------------------------------

    credit_df = parse_credit_table(
        html
    )


    if credit_df is None:

        print(
            f"[{code}] 信用残テーブルなし"
        )

        return None


    if credit_df.empty:

        print(
            f"[{code}] 信用残データ空"
        )

        return None


    print(
        f"[{code}] 信用残テーブル取得成功 "
        f"({len(credit_df)}行)"
    )


    print(
        credit_df.head(2).to_string(
            index=False
        )
    )


    return credit_df


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 70)
    print("Yahoo!ファイナンス 信用残 5銘柄テスト")
    print("=" * 70)
    print()

    print(
        f"取得銘柄 : {', '.join(CODES)}"
    )

    print(
        f"取得間隔 : {DELAY}秒"
    )

    print()


    # ========================================================
    # Session作成
    # ========================================================

    session = requests.Session()

    session.headers.update(
        HEADERS
    )


    print(
        "Yahooトップページ取得..."
    )


    top = session.get(
        BASE_URL,
        timeout=20
    )


    print(
        f"TOP status : {top.status_code}"
    )

    print(
        f"Cookie数   : {len(session.cookies)}"
    )

    print()


    # ========================================================
    # 5銘柄
    # ========================================================

    success = []
    failed = []


    for index, code in enumerate(
        CODES,
        1
    ):

        print("=" * 70)

        print(
            f"[{index}/{len(CODES)}] {code}"
        )

        print("=" * 70)


        result = get_credit(
            session,
            code
        )


        if result is not None:

            success.append(
                code
            )

        else:

            failed.append(
                code
            )


        if index < len(CODES):

            print()

            print(
                f"{DELAY}秒待機..."
            )

            time.sleep(
                DELAY
            )


    # ========================================================
    # 結果
    # ========================================================

    print()
    print("=" * 70)
    print("TEST RESULT")
    print("=" * 70)


    print(
        f"成功 : {len(success)}/{len(CODES)}"
    )

    print(
        f"失敗 : {len(failed)}/{len(CODES)}"
    )


    if success:

        print()

        print(
            "成功 :",
            ", ".join(success)
        )


    if failed:

        print()

        print(
            "失敗 :",
            ", ".join(failed)
        )


    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":

    main()