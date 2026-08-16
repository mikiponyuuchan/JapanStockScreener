import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


DATA_DIR = Path("data/yahoo_credit")

TOP_URL = "https://finance.yahoo.co.jp/quote/{}.T"

CREDIT_URL = (
    "https://finance.yahoo.co.jp/quote/{}.T/history?styl=margin"
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
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
}

MAX_RETRIES = 2
REQUEST_DELAY = 0.8
RETRY_DELAYS = [3, 8]

class YahooCreditNotFound(Exception):
    """Yahooに銘柄ページが存在しない場合"""
    pass

class YahooCreditTemporaryError(Exception):
    """Yahooの一時エラーが連続した場合"""
    pass

def get_credit_history(
    code: str,
    timeout: int = 20,
) -> pd.DataFrame | None:

    code = str(code).strip()

    if not code:
        return None

    top_url = TOP_URL.format(code)
    credit_url = CREDIT_URL.format(code)

    session = requests.Session()
    session.headers.update(HEADERS)

    # --------------------------------------------------------
    # Step 1: access stock top page
    # --------------------------------------------------------

    top_ok = False

    for attempt in range(MAX_RETRIES + 1):

        try:

            response = session.get(
                top_url,
                timeout=timeout,
            )

            if response.status_code == 200:

                top_ok = True
                break

            print(
                f"[{code}] TOP HTTP "
                f"{response.status_code}"
            )

            # Yahooに銘柄ページが存在しない
            # 404はリトライ・待機不要
            if response.status_code == 404:

                print(
                    f"[{code}] Yahooに銘柄ページなし"
                )

                raise YahooCreditNotFound(code)

        except requests.RequestException as e:

            print(
                f"[{code}] TOP request error: {e}"
            )

        if attempt < MAX_RETRIES:

            time.sleep(
                RETRY_DELAYS[
                    min(
                        attempt,
                        len(RETRY_DELAYS) - 1,
                    )
                ]
            )

    if not top_ok:

        print(
            f"[{code}] TOP page failed"
        )

        return None

    # --------------------------------------------------------
    # Step 2: access credit history page
    # --------------------------------------------------------

    time.sleep(REQUEST_DELAY)

    response = None

    for attempt in range(MAX_RETRIES + 1):

        try:

            response = session.get(
                credit_url,
                timeout=timeout,
            )

            status = response.status_code

            print(
                f"[{code}] CREDIT HTTP "
                f"{status} "
                f"size={len(response.content):,}"
            )

            if status == 200:
                break

        except requests.RequestException as e:

            print(
                f"[{code}] CREDIT request error: {e}"
            )

            response = None

        if attempt < MAX_RETRIES:

            delay = RETRY_DELAYS[
                min(
                    attempt,
                    len(RETRY_DELAYS) - 1,
                )
            ]

            print(
                f"[{code}] retry after {delay}s"
            )

            time.sleep(delay)

    if response is None:
        return None

    if response.status_code != 200:

        print(
            f"[{code}] CREDIT page failed"
        )

        return None

    # --------------------------------------------------------
    # Step 3: parse HTML
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    tables = soup.find_all("table")

    print(
        f"[{code}] tables={len(tables)}"
    )

    if not tables:

        print(
            f"[{code}] no table"
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

    target_rows = None

    for table in tables:

        rows = []

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            values = [
                cell.get_text(
                    " ",
                    strip=True,
                )
                for cell in cells
            ]

            if values:
                rows.append(values)

        if not rows:
            continue

        header = set(rows[0])

        if required.issubset(header):

            target_rows = rows

            break

    if target_rows is None:

        print(
            f"[{code}] no credit table"
        )

        return None

    # --------------------------------------------------------
    # Step 4: DataFrame
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

        print(
            f"[{code}] no data rows"
        )

        return None

    df = pd.DataFrame(
        data_rows,
        columns=header,
    )

    columns = [
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    df = df[columns].copy()

    df.insert(
        0,
        "コード",
        code,
    )

    # --------------------------------------------------------
    # Step 5: numeric conversion
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
                regex=False,
            )
            .str.strip()
        )

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Step 6: date conversion
    # --------------------------------------------------------

    df["日付"] = pd.to_datetime(
        df["日付"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["日付"]
    )

    if df.empty:
        return None

    df = (
        df.sort_values(
            "日付",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    return df


def save_credit_history(
    df: pd.DataFrame,
    code: str,
) -> Path | None:

    if df is None or df.empty:
        return None

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = DATA_DIR / f"{code}.csv"

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    return path

def download_credit_batch(
    codes: list[str],
) -> dict[str, pd.DataFrame]:
    """
    Yahoo信用データを複数銘柄まとめて取得する。

    ルール
    ------
    ・既存CSVがある銘柄はYahooへアクセスしない
    ・ブラックリスト登録銘柄はYahooへアクセスしない
    ・YahooCreditNotFound（404）はブラックリストへ追加
    ・500 / timeout / 通信エラー等はブラックリストへ追加しない
    ・一時エラーが3回連続した場合は30分待機する
    ・30分待機後、自動的に同じ銘柄から再開する
    ・Yahooが復旧するまで30分待機→再開を繰り返す
    """

    results = {}

    total = len(codes)

    # ==========================
    # ブラックリスト
    # ==========================

    failed_path = (
        DATA_DIR.parent
        / "yahoo_credit_failed.csv"
    )

    failed_codes = set()

    if failed_path.exists():

        try:

            failed_df = pd.read_csv(
                failed_path,
                dtype=str,
                encoding="utf-8-sig",
            )

            if "code" in failed_df.columns:

                failed_codes = {
                    str(code).strip()
                    for code in failed_df["code"]
                    if pd.notna(code)
                }

        except Exception as e:

            print(
                f"ブラックリスト読込失敗: {e}"
            )

    # ==========================
    # 一時エラー管理
    # ==========================

    consecutive_errors = 0

    # この回数連続したら30分待機
    MAX_CONSECUTIVE_ERRORS = 3

    # Yahoo負荷対策
    SHORT_WAIT_SECONDS = 30
    LONG_WAIT_SECONDS = 30 * 60

    # ==========================
    # 取得位置
    # ==========================

    index = 0

    # ==========================
    # 取得ループ
    # ==========================

    while index < total:

        code = str(codes[index]).strip()

        if not code:

            index += 1
            continue

        # ==========================
        # ブラックリスト
        # ==========================

        if code in failed_codes:

            print(
                f"[{index + 1}/{total}] "
                f"{code} : ブラックリスト除外"
            )

            index += 1
            continue

        # ==========================
        # 既存CSV
        # ==========================

        path = (
            DATA_DIR
            / f"{code}.csv"
        )

        if path.exists():

            try:

                df = pd.read_csv(
                    path,
                    encoding="utf-8-sig",
                )

                if (
                    df is not None
                    and not df.empty
                ):

                    results[code] = df

                    print(
                        f"[{index + 1}/{total}] "
                        f"{code} : CSV利用"
                    )

                    # 成功したのでリセット
                    consecutive_errors = 0

                    index += 1
                    continue

            except Exception as e:

                print(
                    f"[{index + 1}/{total}] "
                    f"{code} : CSV読込失敗 "
                    f"{e}"
                )

        # ==========================
        # 20銘柄ごとの休憩
        # ==========================

        if (
            index > 0
            and index % 20 == 0
        ):

            print()
            print(
                "Yahoo負荷対策: "
                "20秒待機..."
            )

            time.sleep(20)

        # ==========================
        # Yahoo取得
        # ==========================

        print(
            f"[{index + 1}/{total}] "
            f"{code} : Yahoo取得開始"
        )

        try:

            df = get_credit_history(
                code
            )

            # ==========================
            # None / empty
            # ==========================

            if (
                df is None
                or df.empty
            ):

                print(
                    f"[{index + 1}/{total}] "
                    f"{code} : 取得失敗"
                )

                consecutive_errors += 1

                print(
                    f"{code} : "
                    "一時エラー扱い "
                    f"({consecutive_errors}/"
                    f"{MAX_CONSECUTIVE_ERRORS})"
                )

                # --------------------------
                # 3回連続 → 30分待機
                # --------------------------

                if (
                    consecutive_errors
                    >= MAX_CONSECUTIVE_ERRORS
                ):

                    print()
                    print(
                        "===================================="
                    )
                    print(
                        "Yahoo一時エラーが"
                        f"{MAX_CONSECUTIVE_ERRORS}回連続しました。"
                    )
                    print(
                        "Yahoo負荷対策のため"
                    )
                    print(
                        "15分待機してから自動再開します。"
                    )
                    print(
                        "===================================="
                    )

                    try:

                        for remaining in range(
                            LONG_WAIT_SECONDS,
                            0,
                            -60,
                        ):

                            minutes = remaining // 60

                            print(
                                f"再開まで約 {minutes} 分..."
                            )

                            time.sleep(
                                min(60, remaining)
                            )

                    except KeyboardInterrupt:

                        print()
                        print(
                            "ユーザー操作により"
                            "取得を中断しました。"
                        )

                        break

                    print()
                    print(
                        "30分待機が完了しました。"
                    )
                    print(
                        f"{code} から自動再開します。"
                    )
                    print()

                    # 重要：
                    # indexを進めない
                    # → 同じ銘柄を再取得する
                    consecutive_errors = 0

                    continue

                # --------------------------
                # 3回未満なら短時間待機
                # --------------------------

                print(
                    "Yahoo負荷対策: "
                    f"{SHORT_WAIT_SECONDS}秒待機..."
                )

                try:

                    time.sleep(
                        SHORT_WAIT_SECONDS
                    )

                except KeyboardInterrupt:

                    print()
                    print(
                        "ユーザー操作により"
                        "取得を中断しました。"
                    )

                    break

                # 同じ銘柄を再取得
                continue

            # ==========================
            # 正常取得
            # ==========================

            save_credit_history(
                df,
                code,
            )

            results[code] = df

            print(
                f"[{index + 1}/{total}] "
                f"{code} : 保存完了 "
                f"({len(df)} rows)"
            )

            # 成功したのでリセット
            consecutive_errors = 0

            # 次の銘柄へ
            index += 1

        # ==========================
        # 404
        # ==========================

        except YahooCreditNotFound:

            print(
                f"[{index + 1}/{total}] "
                f"{code} : Yahoo対象外"
            )

            # 404だけブラックリストへ追加
            failed_codes.add(
                code
            )

            print(
                f"{code} : "
                "ブラックリスト追加"
            )

            # ブラックリストを即時保存
            try:

                failed_df = pd.DataFrame(
                    sorted(failed_codes),
                    columns=["code"],
                )

                failed_df.to_csv(
                    failed_path,
                    index=False,
                    encoding="utf-8-sig",
                )

            except Exception as e:

                print(
                    "ブラックリスト保存失敗: "
                    f"{e}"
                )

            # 404は銘柄固有なので
            # 連続エラーには含めない
            consecutive_errors = 0

            # 次の銘柄へ
            index += 1

        # ==========================
        # Ctrl+C
        # ==========================

        except KeyboardInterrupt:

            print()
            print(
                "ユーザー操作により"
                "取得を中断しました。"
            )

            break

        # ==========================
        # その他のエラー
        # ==========================

        except Exception as e:

            print(
                f"[{index + 1}/{total}] "
                f"{code} : ERROR "
                f"{type(e).__name__}: {e}"
            )

            # ブラックリストには入れない
            consecutive_errors += 1

            print(
                f"{code} : "
                "一時エラー扱い "
                f"({consecutive_errors}/"
                f"{MAX_CONSECUTIVE_ERRORS})"
            )

            # --------------------------
            # 3回連続 → 30分待機
            # --------------------------

            if (
                consecutive_errors
                >= MAX_CONSECUTIVE_ERRORS
            ):

                print()
                print(
                    "===================================="
                )
                print(
                    "Yahoo一時エラーが"
                    f"{MAX_CONSECUTIVE_ERRORS}回連続しました。"
                )
                print(
                    "Yahoo負荷対策のため"
                )
                print(
                    "15分待機してから自動再開します。"
                )
                print(
                    "===================================="
                )

                try:

                    for remaining in range(
                        LONG_WAIT_SECONDS,
                        0,
                        -60,
                    ):

                        minutes = remaining // 60

                        print(
                            f"再開まで約 {minutes} 分..."
                        )

                        time.sleep(
                            min(60, remaining)
                        )

                except KeyboardInterrupt:

                    print()
                    print(
                        "ユーザー操作により"
                        "取得を中断しました。"
                    )

                    break

                print()
                print(
                    "30分待機が完了しました。"
                )
                print(
                    f"{code} から自動再開します。"
                )
                print()

                # 同じ銘柄から再開
                consecutive_errors = 0

                continue

            # --------------------------
            # 3回未満なら60秒待機
            # --------------------------

            print(
                "Yahoo負荷対策: "
                "60秒待機..."
            )

            try:

                time.sleep(60)

            except KeyboardInterrupt:

                print()
                print(
                    "ユーザー操作により"
                    "取得を中断しました。"
                )

                break

            # 同じ銘柄を再取得
            continue

    # ==========================
    # 最終ブラックリスト保存
    # ==========================

    try:

        failed_df = pd.DataFrame(
            sorted(failed_codes),
            columns=["code"],
        )

        failed_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        failed_df.to_csv(
            failed_path,
            index=False,
            encoding="utf-8-sig",
        )

        print()
        print(
            "ブラックリスト保存 : "
            f"{len(failed_codes)} 銘柄"
        )

    except Exception as e:

        print(
            "ブラックリスト保存失敗: "
            f"{e}"
        )

    # ==========================
    # 結果
    # ==========================

    print()
    print(
        "Yahoo信用データ取得完了 : "
        f"{len(results)}/{total}銘柄"
    )

    return results

def load_latest_credit_data(
    codes=None,
) -> dict[str, pd.Series]:
    """
    data/yahoo_credit/ に保存されているYahoo信用データから
    各銘柄の最新信用データを読み込み、
    {コード: 最新行} の辞書を返す。
    """

    credit_map = {}

    if codes is not None:
        target_codes = {
            str(code).strip()
            for code in codes
        }
    else:
        target_codes = None

    if not DATA_DIR.exists():
        return credit_map

    for path in DATA_DIR.glob("*.csv"):

        code = path.stem.strip()

        if target_codes is not None:
            if code not in target_codes:
                continue

        try:

            df = pd.read_csv(
                path,
                encoding="utf-8-sig",
            )

        except Exception as e:

            print(
                f"[{code}] credit CSV read error: {e}"
            )

            continue

        if df.empty:
            continue

        # 日付の新しい順に並べる
        if "日付" in df.columns:

            df["日付"] = pd.to_datetime(
                df["日付"],
                errors="coerce",
            )

            df = df.dropna(
                subset=["日付"]
            )

            if df.empty:
                continue

            df = df.sort_values(
                "日付",
                ascending=False,
            )

        latest = df.iloc[0]

        credit_map[code] = latest

    return credit_map

def main():

    print("=" * 60)
    print("Yahoo credit test")
    print("=" * 60)

    test_codes = [
        "1301",
        "1332",
        "1605",
        "1801",
        "2002",
    ]

    success = 0
    failed = 0

    for code in test_codes:

        start = time.perf_counter()

        print()
        print(
            f"[{code}] retrieving..."
        )

        try:

            df = get_credit_history(code)

            elapsed = (
                time.perf_counter()
                - start
            )

            if df is not None and not df.empty:

                success += 1

                print(
                    f"[{code}] SUCCESS "
                    f"{len(df)} rows "
                    f"({elapsed:.2f}s)"
                )

                print(
                    df.head(3).to_string(
                        index=False
                    )
                )

                path = save_credit_history(
                    df,
                    code,
                )

                print(
                    f"saved: {path}"
                )

            else:

                failed += 1

                print(
                    f"[{code}] FAILED "
                    f"({elapsed:.2f}s)"
                )

        except Exception as e:

            failed += 1

            elapsed = (
                time.perf_counter()
                - start
            )

            print(
                f"[{code}] ERROR: {e} "
                f"({elapsed:.2f}s)"
            )

    print()
    print("=" * 60)
    print("TEST RESULT")
    print("=" * 60)
    print(
        f"success: {success}/{len(test_codes)}"
    )
    print(
        f"failed : {failed}/{len(test_codes)}"
    )


if __name__ == "__main__":
    main()