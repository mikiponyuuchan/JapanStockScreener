import time
from pathlib import Path

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
    "2502",
    "2914",
    "3382",
    "4063",
    "4502",
]

BASE_URL = "https://finance.yahoo.co.jp"

DELAY = 3

HTML_DIR = Path(
    "data/yahoo_credit_test"
)

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
# Session作成
# ============================================================

def create_session():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    print(
        "Yahooトップページへアクセス..."
    )

    response = session.get(
        BASE_URL,
        timeout=20
    )

    print(
        f"TOP status : {response.status_code}"
    )

    print(
        f"TOP size   : {len(response.content):,}"
    )

    print(
        f"Cookie数   : {len(session.cookies)}"
    )

    if response.status_code != 200:

        raise RuntimeError(
            "Yahooトップページ取得失敗"
        )

    return session


# ============================================================
# 信用残テーブル抽出
# ============================================================

def parse_credit_table(
    html
):

    try:

        tables = pd.read_html(
            html
        )

    except Exception as e:

        print(
            f"pd.read_html ERROR : {e}"
        )

        return None


    if not tables:

        print(
            "HTML内にtableなし"
        )

        return None


    required_columns = {
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    }


    for df in tables:

        columns = {
            str(column)
            for column in df.columns
        }

        if required_columns.issubset(
            columns
        ):

            result = df[
                [
                    "日付",
                    "売残",
                    "買残",
                    "売残増減",
                    "買残増減",
                    "信用倍率",
                ]
            ].copy()


            numeric_columns = [
                "売残",
                "買残",
                "売残増減",
                "買残増減",
                "信用倍率",
            ]


            for column in numeric_columns:

                result[column] = pd.to_numeric(
                    result[column],
                    errors="coerce"
                )


            return result


    return None


# ============================================================
# 1銘柄取得
# ============================================================

def get_credit_history(
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
        f"[{code}] status={response.status_code} "
        f"size={len(response.content):,}"
    )


    if response.status_code != 200:

        print(
            f"[{code}] HTTP ERROR"
        )

        return None


    # --------------------------------------------------------
    # HTML保存
    # --------------------------------------------------------

    HTML_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    html_path = (
        HTML_DIR /
        f"{code}.html"
    )


    html_path.write_bytes(
        response.content
    )


    # --------------------------------------------------------
    # 信用残テーブル解析
    # --------------------------------------------------------

    credit_df = parse_credit_table(
        response.text
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


    latest = credit_df.iloc[0].copy()


    latest["コード"] = code


    # コードを先頭へ

    latest = latest[
        [
            "コード",
            "日付",
            "売残",
            "買残",
            "売残増減",
            "買残増減",
            "信用倍率",
        ]
    ]


    return latest


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 70)
    print("Yahoo!ファイナンス 信用残 10銘柄テスト")
    print("=" * 70)
    print()


    session = create_session()


    print()
    print("=" * 70)
    print("信用残取得開始")
    print("=" * 70)
    print()


    results = []

    success_codes = []
    failed_codes = []


    for index, code in enumerate(
        CODES,
        1
    ):

        print(
            f"[{index}/{len(CODES)}] "
            f"{code} 取得中..."
        )


        result = get_credit_history(
            session,
            code
        )


        if result is None:

            failed_codes.append(
                code
            )

            print(
                f"[{code}] 取得失敗"
            )

        else:

            success_codes.append(
                code
            )

            results.append(
                result
            )

            print(
                f"[{code}] 取得成功"
            )

            print(
                result.to_dict()
            )


        print()


        # ----------------------------------------------------
        # 次の銘柄まで待機
        # ----------------------------------------------------

        if index < len(CODES):

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
        f"成功 : {len(success_codes)}/{len(CODES)}"
    )

    print(
        f"失敗 : {len(failed_codes)}/{len(CODES)}"
    )

    print()


    if success_codes:

        print(
            "成功銘柄:"
        )

        print(
            ", ".join(
                success_codes
            )
        )

        print()


    if failed_codes:

        print(
            "失敗銘柄:"
        )

        print(
            ", ".join(
                failed_codes
            )
        )

        print()


    # ========================================================
    # DataFrame保存
    # ========================================================

    if results:

        result_df = pd.DataFrame(
            results
        )


        output_file = (
            "yahoo_credit_10_result.csv"
        )


        result_df.to_csv(
            output_file,
            index=False,
            encoding="utf-8-sig"
        )


        print(
            f"CSV保存 : {output_file}"
        )

        print()

        print(
            result_df.to_string(
                index=False
            )
        )


    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":

    main()