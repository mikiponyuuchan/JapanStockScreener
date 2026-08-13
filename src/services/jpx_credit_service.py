import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ============================================================
# 設定
# ============================================================

JPX_MARGIN_URL = (
    "https://www.jpx.co.jp/"
    "markets/statistics-equities/margin/index.html"
)

DATA_DIR = Path("data/jpx_credit")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ============================================================
# 最新XLSのURLを取得
# ============================================================

def find_latest_xls_url() -> tuple[str, str]:
    """
    JPX信用取引ページから最新の個別銘柄信用取引残高XLSを探す。

    Returns
    -------
    tuple[str, str]
        (XLS URL, YYYYMMDD)
    """

    response = requests.get(
        JPX_MARGIN_URL,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    xls_links = []

    for link in soup.find_all("a"):

        href = link.get("href")

        if not href:
            continue

        full_url = urljoin(
            JPX_MARGIN_URL,
            href
        )

        if not re.search(
            r"\.xls$",
            full_url,
            re.IGNORECASE
        ):
            continue

        filename = full_url.split("/")[-1]

        match = re.search(
            r"(\d{8})",
            filename
        )

        if not match:
            continue

        date_str = match.group(1)

        xls_links.append(
            (date_str, full_url)
        )

    if not xls_links:
        raise RuntimeError(
            "JPX信用取引XLSファイルが見つかりません。"
        )

    # 日付の新しい順
    xls_links.sort(
        key=lambda x: x[0],
        reverse=True
    )

    latest_date, latest_url = xls_links[0]

    return latest_url, latest_date


# ============================================================
# XLSダウンロード
# ============================================================

def download_latest_xls() -> Path:
    """
    JPXから最新信用取引XLSをダウンロードする。
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    xls_url, date_str = find_latest_xls_url()

    filename = xls_url.split("/")[-1]

    output_path = DATA_DIR / filename

    response = requests.get(
        xls_url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    output_path.write_bytes(
        response.content
    )

    print(
        f"JPX信用データ取得 : {date_str}"
    )

    print(
        f"XLS保存           : {output_path}"
    )

    print(
        f"ファイルサイズ     : {len(response.content):,} bytes"
    )

    return output_path


# ============================================================
# XLS読み込み
# ============================================================

def load_credit_xls(
    xls_path: Path
) -> pd.DataFrame:
    """
    JPX信用取引XLSを読み込み、
    必要な信用取引データをDataFrameとして返す。
    """

    df = pd.read_excel(
        xls_path,
        sheet_name="個別銘柄信用取引残高",
        header=None
    )

    # 実データは8行目(index 7)から
    data = df.iloc[7:].copy()

    # 必要な列
    #
    # 3 : 銘柄名
    # 4 : 市場
    # 5 : 銘柄種別
    # 6 : コード
    # 8 : 売残高
    # 9 : 売残高 前日比
    # 10: 売残高 上場比
    # 11: 買残高
    # 12: 買残高 前日比
    # 13: 買残高 上場比
    # 14: 取組比率

    data = data.iloc[
        :,
        [3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14]
    ].copy()

    data.columns = [
        "銘柄名",
        "市場",
        "信用種別",
        "コード",
        "売残高",
        "売残高前日比",
        "売残高上場比",
        "買残高",
        "買残高前日比",
        "買残高上場比",
        "取組比率",
    ]

    # ========================================================
    # コード整理
    # ========================================================

    # 数字だけでなく英字を含むコードにも対応
    # 例:
    # 52400 → 5240
    # 36560 → 3656
    # 147A  → 147A

    data["コード"] = (
        data["コード"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )

    # JPXの5桁コードで末尾が0の場合、
    # 正式な4桁コードへ変換
    mask = (
        data["コード"].str.len().eq(5)
        & data["コード"].str.endswith(
            "0",
            na=False
        )
    )

    data.loc[mask, "コード"] = (
        data.loc[mask, "コード"].str[:-1]
    )

    # 欠損・空文字を除外
    data = data[
        data["コード"].notna()
        & (data["コード"] != "")
    ].copy()

    # 4桁コードへ統一
    # 英字コードもそのまま保持
    data["コード"] = (
        data["コード"]
        .str.zfill(4)
    )

    # ========================================================
    # 数値列
    # ========================================================

    numeric_columns = [
        "売残高",
        "売残高前日比",
        "売残高上場比",
        "買残高",
        "買残高前日比",
        "買残高上場比",
        "取組比率",
    ]

    for column in numeric_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    # ========================================================
    # 信用倍率
    # ========================================================

    data["信用倍率"] = (
        data["買残高"] /
        data["売残高"]
    )

    # 売残高0の場合は倍率をNaN
    data.loc[
        data["売残高"] <= 0,
        "信用倍率"
    ] = pd.NA

    # ========================================================
    # 基準日
    # ========================================================

    filename = xls_path.name

    match = re.search(
        r"(\d{8})",
        filename
    )

    if match:

        data["基準日"] = pd.to_datetime(
            match.group(1),
            format="%Y%m%d"
        ).strftime("%Y-%m-%d")

    else:

        data["基準日"] = pd.NA

    # ========================================================
    # 列順整理
    # ========================================================

    data = data[
        [
            "基準日",
            "コード",
            "銘柄名",
            "市場",
            "信用種別",
            "売残高",
            "売残高前日比",
            "売残高上場比",
            "買残高",
            "買残高前日比",
            "買残高上場比",
            "信用倍率",
            "取組比率",
        ]
    ]

    return data


# ============================================================
# CSV保存
# ============================================================

def save_credit_csv(
    df: pd.DataFrame
) -> Path:
    """
    整理した信用データを日付別CSVとして保存する。
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if df.empty:
        raise ValueError(
            "信用データが空です。"
        )

    date_str = df["基準日"].iloc[0]

    output_path = (
        DATA_DIR /
        f"credit_{date_str}.csv"
    )

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"信用データCSV保存 : {output_path}"
    )

    print(
        f"銘柄数             : {len(df):,}"
    )

    return output_path


# ============================================================
# 保存済み信用データ一覧
# ============================================================

def get_credit_history_files() -> list[Path]:
    """
    data/jpx_credit/ に保存されている
    日付別信用データCSVを取得する。
    """

    files = list(
        DATA_DIR.glob("credit_*.csv")
    )

    files.sort(
        key=lambda p: p.name,
        reverse=True
    )

    return files


# ============================================================
# 1営業日前の信用データ取得
# ============================================================

def get_previous_day_credit_data(
    current_date: str
) -> tuple[pd.DataFrame | None, str | None]:
    """
    現在の日付より前に保存されている信用データから、
    直前の営業日データを取得する。

    土日・祝日は、
    保存されている直近のJPX営業日データを使用する。

    Parameters
    ----------
    current_date : str
        現在の基準日 YYYY-MM-DD

    Returns
    -------
    tuple
        (前営業日データ, 前営業日)
    """

    files = get_credit_history_files()

    previous_files = []

    for file_path in files:

        match = re.search(
            r"credit_(\d{4}-\d{2}-\d{2})\.csv",
            file_path.name
        )

        if not match:
            continue

        date_str = match.group(1)

        if date_str < current_date:

            previous_files.append(
                (date_str, file_path)
            )

    # 新しい順
    previous_files.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # 直前営業日が存在しない
    if not previous_files:

        print(
            "前営業日データなし : "
            "比較できる履歴がありません"
        )

        return None, None

    # 一番新しい過去データ
    previous_date, previous_file = (
        previous_files[0]
    )

    previous_df = pd.read_csv(
        previous_file,
        encoding="utf-8-sig"
    )

    return previous_df, previous_date


# ============================================================
# 売り残前日比判定
# ============================================================

def add_previous_day_change(
    current_df: pd.DataFrame
) -> pd.DataFrame:
    """
    現在の売残高と1営業日前の売残高を比較し、
    以下を追加する。

    - 前日売残高
    - 売り残増加数
    - 売り残増加率
    - 売り残前日比増加
    """

    if current_df.empty:
        return current_df

    current_date = current_df[
        "基準日"
    ].iloc[0]

    previous_df, previous_date = (
        get_previous_day_credit_data(
            current_date
        )
    )

    # 前営業日のデータがない場合
    if previous_df is None:

        current_df[
            "前日売残高"
        ] = pd.NA

        current_df[
            "売り残増加数"
        ] = pd.NA

        current_df[
            "売り残増加率"
        ] = pd.NA

        current_df[
            "売り残前日比増加"
        ] = pd.NA

        return current_df

    # ========================================================
    # 前日データから必要な列を取得
    # ========================================================

    previous = previous_df[
        [
            "コード",
            "売残高",
        ]
    ].copy()

    previous = previous.rename(
        columns={
            "売残高": "前日売残高"
        }
    )

    # ========================================================
    # コードで結合
    # ========================================================

    result = current_df.merge(
        previous,
        on="コード",
        how="left"
    )

    # ========================================================
    # 売り残増加数
    # ========================================================

    result["売り残増加数"] = (
        result["売残高"]
        - result["前日売残高"]
    )

    # ========================================================
    # 売り残増加率
    # ========================================================

    result["売り残増加率"] = (
        result["売り残増加数"]
        / result["前日売残高"]
        * 100
    )

    # 前日売残高が0の場合は計算不能
    result.loc[
        result["前日売残高"] <= 0,
        "売り残増加率"
    ] = pd.NA

    # ========================================================
    # 売り残前日比増加
    # ========================================================

    result["売り残前日比増加"] = (
        result["売残高"]
        > result["前日売残高"]
    )

    print()

    print(
        f"前営業日比較 : {previous_date}"
    )

    print(
        "売り残前日比増加 : "
        f"{result['売り残前日比増加'].sum()} 銘柄"
    )

    return result


# ============================================================
# 一連の処理
# ============================================================

def update_credit_data() -> pd.DataFrame:
    """
    JPX信用データを取得して、
    整理・保存・前営業日比較まで行う。
    """

    xls_path = download_latest_xls()

    df = load_credit_xls(
        xls_path
    )

    # 現在のデータを保存
    save_credit_csv(
        df
    )

    # 前営業日データと比較
    df = add_previous_day_change(
        df
    )

    return df


# ============================================================
# テスト実行
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("JPX信用取引データ取得テスト")
    print("=" * 60)
    print()

    df = update_credit_data()

    print()
    print("取得完了")
    print()

    print(
        "銘柄数 :",
        len(df)
    )

    print()

    print("先頭10銘柄")
    print("-" * 60)

    print(
        df[
            [
                "コード",
                "銘柄名",
                "市場",
                "売残高",
                "買残高",
                "信用倍率",
                "取組比率",
                "前日売残高",
                "売り残増加数",
                "売り残増加率",
                "売り残前日比増加",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )