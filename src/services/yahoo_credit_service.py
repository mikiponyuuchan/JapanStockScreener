import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ============================================================
# 設定
# ============================================================

DATA_DIR = Path("data/yahoo_credit")

BASE_URL = (
    "https://finance.yahoo.co.jp/"
    "quote/{}.T/history?styl=margin"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 "
        "Safari/537.36"
    )
}


# ============================================================
# Yahoo!信用残時系列取得
# ============================================================

def get_credit_history(
    code: str,
    timeout: int = 20
) -> pd.DataFrame | None:
    """
    Yahoo!ファイナンスから個別銘柄の信用残時系列を取得する。

    取得項目:
        日付
        売残
        買残
        売残増減
        買残増減
        信用倍率
    """

    code = str(code).strip()

    if not code:
        return None

    url = BASE_URL.format(code)

    # --------------------------------------------------------
    # Yahoo!へのアクセス
    # --------------------------------------------------------

    session = requests.Session()

    session.headers.update(HEADERS)

    try:

        response = session.get(
            url,
            timeout=timeout
        )

        # 500の場合は少し待って1回だけ再試行
        if response.status_code == 500:

            time.sleep(1.0)

            response = session.get(
                url,
                timeout=timeout
            )

        response.raise_for_status()

    except requests.RequestException as e:

        print(
            f"Yahoo信用取得エラー {code}: {e}"
        )

        return None

    # --------------------------------------------------------
    # HTML解析
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    tables = soup.find_all("table")

    # --------------------------------------------------------
    # 信用残時系列テーブルを探す
    # --------------------------------------------------------

    target_rows = None

    required = {
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    }

    for table in tables:

        rows = []

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            values = [
                cell.get_text(
                    " ",
                    strip=True
                )
                for cell in cells
            ]

            if values:
                rows.append(values)

        if not rows:
            continue

        header = rows[0]

        if required.issubset(set(header)):

            target_rows = rows

            break

    if target_rows is None:

        print(
            f"Yahoo信用データなし {code}"
        )

        return None

    # --------------------------------------------------------
    # DataFrame化
    # --------------------------------------------------------

    header = target_rows[0]

    data_rows = []

    for row in target_rows[1:]:

        if len(row) < len(header):
            continue

        data_rows.append(
            row[:len(header)]
        )

    if not data_rows:
        return None

    df = pd.DataFrame(
        data_rows,
        columns=header
    )

    # --------------------------------------------------------
    # 必要列だけ残す
    # --------------------------------------------------------

    df = df[
        [
            "日付",
            "売残",
            "買残",
            "売残増減",
            "買残増減",
            "信用倍率",
        ]
    ].copy()

    # --------------------------------------------------------
    # 数値変換
    # --------------------------------------------------------

    numeric_columns = [
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    for column in numeric_columns:

        df[column] = (
            df[column]
            .astype(str)
            .str.replace(
                ",",
                "",
                regex=False
            )
            .str.replace(
                "－",
                "-",
                regex=False
            )
            .str.strip()
        )

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # 日付変換
    # --------------------------------------------------------

    df["日付"] = pd.to_datetime(
        df["日付"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # コード追加
    # --------------------------------------------------------

    df.insert(
        0,
        "コード",
        code
    )

    # --------------------------------------------------------
    # 不正行を除外
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "日付",
            "売残",
            "買残"
        ]
    )

    df = df.reset_index(
        drop=True
    )

    return df


# ============================================================
# 最新信用残取得
# ============================================================

def get_latest_credit(
    code: str
) -> dict | None:
    """
    最新の信用残データを取得する。
    """

    df = get_credit_history(
        code
    )

    if df is None or df.empty:
        return None

    row = df.iloc[0]

    return {
        "コード": code,
        "日付": row["日付"],
        "売残": row["売残"],
        "買残": row["買残"],
        "売残増減": row["売残増減"],
        "買残増減": row["買残増減"],
        "信用倍率": row["信用倍率"],
    }


# ============================================================
# CSV保存
# ============================================================

def save_credit_history(
    code: str,
    df: pd.DataFrame
) -> Path | None:

    if df is None or df.empty:
        return None

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        DATA_DIR /
        f"{code}.csv"
    )

    save_df = df.copy()

    save_df["日付"] = (
        save_df["日付"]
        .dt.strftime("%Y-%m-%d")
    )

    save_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    return output_path


# ============================================================
# 10銘柄テスト
# ============================================================

if __name__ == "__main__":

    test_codes = [
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

    print("=" * 60)
    print(
        "Yahoo!ファイナンス 信用残取得テスト"
    )
    print("=" * 60)
    print()

    success = 0
    failed = 0

    for code in test_codes:

        print(
            f"[{code}] 取得中..."
        )

        df = get_credit_history(
            code
        )

        if df is None or df.empty:

            print(
                f"[{code}] 取得失敗"
            )

            failed += 1

            continue

        save_credit_history(
            code,
            df
        )

        print(
            f"[{code}] 成功 "
            f"{len(df)}件"
        )

        print(
            df.head(3).to_string(
                index=False
            )
        )

        print()

        success += 1

        # Yahoo!へのアクセス間隔
        time.sleep(1)

    print("=" * 60)
    print("テスト結果")
    print("=" * 60)

    print(
        f"成功 : {success}銘柄"
    )

    print(
        f"失敗 : {failed}銘柄"
    )

    print(
        f"保存先 : {DATA_DIR}"
    )