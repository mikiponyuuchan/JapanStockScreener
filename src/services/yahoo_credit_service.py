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

# 実際に HTTP 200 を確認できた User-Agent
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

# リトライ回数
MAX_RETRIES = 3

# 通常アクセス時の待機時間
REQUEST_DELAY = 0.8

# リトライ時の待機時間
RETRY_DELAYS = [2, 5, 10]


# ============================================================
# Yahoo!ファイナンス 信用残時系列取得
# ============================================================

def get_credit_history(
    code: str,
    timeout: int = 20
) -> pd.DataFrame | None:
    """
    Yahoo!ファイナンスから個別銘柄の信用残時系列を取得する。

    戻り値:
        成功:
            DataFrame

        信用データなし:
            None

        HTTP・通信エラー:
            None

    DataFrame列:
        コード
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

    response = None

    # ========================================================
    # HTTP取得
    # ========================================================

    for attempt in range(MAX_RETRIES + 1):

        if attempt > 0:

            delay = RETRY_DELAYS[
                min(
                    attempt - 1,
                    len(RETRY_DELAYS) - 1
                )
            ]

            print(
                f"[{code}] "
                f"リトライ {attempt}/{MAX_RETRIES} "
                f"{delay}秒待機..."
            )

            time.sleep(delay)

        try:

            # Sessionを使わず、直接 requests.get()
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=timeout
            )

            status = response.status_code

            # ------------------------------------------------
            # 成功
            # ------------------------------------------------

            if status == 200:

                print(
                    f"[{code}] HTTP 200 "
                    f"({len(response.content):,} bytes)"
                )

                break

            # ------------------------------------------------
            # アクセス制限
            # ------------------------------------------------

            if status == 429:

                print(
                    f"[{code}] "
                    f"HTTP 429 Too Many Requests"
                )

                continue

            # ------------------------------------------------
            # サーバーエラー
            # ------------------------------------------------

            if status >= 500:

                print(
                    f"[{code}] "
                    f"HTTP {status} Server Error"
                )

                continue

            # ------------------------------------------------
            # その他HTTPエラー
            # ------------------------------------------------

            print(
                f"[{code}] "
                f"HTTP {status} エラー"
            )

            return None

        except requests.RequestException as e:

            print(
                f"[{code}] "
                f"通信エラー: {e}"
            )

            if attempt >= MAX_RETRIES:
                return None

            continue

    # ========================================================
    # 最終確認
    # ========================================================

    if response is None:
        return None

    if response.status_code != 200:

        print(
            f"[{code}] "
            f"取得失敗 status={response.status_code}"
        )

        return None

    # ========================================================
    # アクセス間隔
    # ========================================================

    time.sleep(REQUEST_DELAY)

    # ========================================================
    # HTML解析
    # ========================================================

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    tables = soup.find_all("table")

    if not tables:

        print(
            f"[{code}] "
            f"tableなし"
        )

        return None

    # ========================================================
    # 信用残テーブル検索
    # ========================================================

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
            f"[{code}] "
            f"信用データなし"
        )

        return None

    # ========================================================
    # DataFrame作成
    # ========================================================

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

    # ========================================================
    # 必要列だけ残す
    # ========================================================

    columns = [
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    df = df[columns].copy()

    # ========================================================
    # コード追加
    # ========================================================

    df.insert(
        0,
        "コード",
        code
    )

    # ========================================================
    # 数値変換
    # ========================================================

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
            .str.replace(",", "", regex=False)
            .str.replace("-", "0", regex=False)
            .str.strip()
        )

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # ========================================================
    # 日付変換
    # ========================================================

    df["日付"] = pd.to_datetime(
        df["日付"],
        errors="coerce"
    )

    # ========================================================
    # 不正行削除
    # ========================================================

    df = df.dropna(
        subset=["日付"]
    )

    if df.empty:
        return None

    # ========================================================
    # 日付順
    # ========================================================

    df = df.sort_values(
        "日付",
        ascending=False
    ).reset_index(
        drop=True
    )

    return df


# ============================================================
# CSV保存
# ============================================================

def save_credit_history(
    df: pd.DataFrame,
    code: str
) -> Path | None:

    if df is None or df.empty:
        return None

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    path = DATA_DIR / f"{code}.csv"

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig"
    )

    return path


# ============================================================
# テスト
# ============================================================

def main():

    print("=" * 60)
    print("Yahoo!ファイナンス 信用残取得テスト")
    print("=" * 60)
    print()

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

    success = 0
    failed = 0

    for code in test_codes:

        start = time.perf_counter()

        print(
            f"[{code}] 取得中..."
        )

        try:

            df = get_credit_history(
                code
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            if df is not None and not df.empty:

                success += 1

                print(
                    f"[{code}] 成功 "
                    f"{len(df)}件 "
                    f"({elapsed:.2f}秒)"
                )

                print(
                    df.head(3).to_string(
                        index=False
                    )
                )

                path = save_credit_history(
                    df,
                    code
                )

                if path:
                    print(
                        f"保存: {path}"
                    )

            else:

                failed += 1

                print(
                    f"[{code}] 信用データなし "
                    f"({elapsed:.2f}秒)"
                )

        except Exception as e:

            failed += 1

            elapsed = (
                time.perf_counter()
                - start
            )

            print(
                f"[{code}] エラー: {e} "
                f"({elapsed:.2f}秒)"
            )

        print()

    print("=" * 60)
    print("テスト結果")
    print("=" * 60)

    total = success + failed

    rate = (
        success / total * 100
        if total > 0
        else 0
    )

    print(
        f"成功 : {success}銘柄"
    )

    print(
        f"失敗 : {failed}銘柄"
    )

    print(
        f"成功率 : {rate:.1f}%"
    )


if __name__ == "__main__":
    main()