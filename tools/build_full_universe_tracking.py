import sys
import time
from pathlib import Path

import pandas as pd


# ============================================================
# プロジェクトパス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from indicators.technical import add_indicators
from screener.analyzer import calculate_initial_score


# ============================================================
# 設定
# ============================================================

CACHE_DIR = ROOT_DIR / "data" / "cache"
OUTPUT_DIR = ROOT_DIR / "data" / "tracking"

JPX_FILE = ROOT_DIR / "data" / "jpx_stock_list.xls"


# 検証期間
START_DATE = "2026-07-27"
END_DATE = "2026-08-07"

# 何営業日先まで追跡するか
FORWARD_DAYS = 5


# ============================================================
# 日付関連
# ============================================================

def normalize_date(value):
    """
    日付を YYYY-MM-DD の文字列へ変換
    """

    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return None


def get_date_series(df):
    """
    DataFrameから日付Seriesを取得する。
    """

    if "Date" in df.columns:
        return pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

    return pd.to_datetime(
        df.index,
        errors="coerce"
    )


# ============================================================
# キャッシュ読み込み
# ============================================================

def load_cache(code):
    """
    data/cache/{code}.csv を読み込む。
    """

    path = CACHE_DIR / f"{code}.csv"

    if not path.exists():
        return None

    try:

        df = pd.read_csv(path)

        if df.empty:
            return None

        # Date列が存在する場合
        if "Date" in df.columns:

            df["Date"] = pd.to_datetime(
                df["Date"],
                errors="coerce"
            )

            df = df.dropna(
                subset=["Date"]
            )

            df = df.sort_values(
                "Date"
            )

            df = df.drop_duplicates(
                subset=["Date"],
                keep="last"
            )

            df = df.reset_index(
                drop=True
            )

            return df

        # Date列がない場合はindexを日付として扱う
        date_index = pd.to_datetime(
            df.index,
            errors="coerce"
        )

        if date_index.notna().sum() == 0:
            return None

        df = df.copy()

        df["_Date"] = date_index

        df = df.dropna(
            subset=["_Date"]
        )

        df = df.sort_values(
            "_Date"
        )

        df = df.drop_duplicates(
            subset=["_Date"],
            keep="last"
        )

        df = df.reset_index(
            drop=True
        )

        df["Date"] = df["_Date"]

        df = df.drop(
            columns=["_Date"]
        )

        return df

    except Exception as e:

        print(
            f"キャッシュ読込エラー: {code} / {e}"
        )

        return None


# ============================================================
# 銘柄コード正規化
# ============================================================

def normalize_code(value):

    if pd.isna(value):
        return None

    text = str(value).strip()

    # Excelから 1301.0 のようになるケース
    if text.endswith(".0"):
        text = text[:-2]

    return text


# ============================================================
# JPX銘柄一覧
# ============================================================

def load_stock_list():

    if not JPX_FILE.exists():

        raise FileNotFoundError(
            f"JPX銘柄一覧がありません: {JPX_FILE}"
        )

    print(
        f"JPX銘柄一覧読込: {JPX_FILE}"
    )

    df = pd.read_excel(
        JPX_FILE
    )

    print(
        f"JPX全行数: {len(df)}"
    )

    # --------------------------------------------------------
    # コード
    # --------------------------------------------------------

    code_column = None

    for column in [
        "コード",
        "銘柄コード",
    ]:

        if column in df.columns:
            code_column = column
            break

    if code_column is None:

        raise ValueError(
            "銘柄コード列が見つかりません。"
            f" columns={list(df.columns)}"
        )

    df["コード"] = (
        df[code_column]
        .apply(normalize_code)
    )

    # --------------------------------------------------------
    # 市場区分
    # --------------------------------------------------------

    market_column = None

    for column in [
        "市場・商品区分",
        "市場区分",
    ]:

        if column in df.columns:
            market_column = column
            break

    if market_column is None:

        raise ValueError(
            "市場区分列が見つかりません。"
            f" columns={list(df.columns)}"
        )

    # 普通株対象市場
    target_markets = [
        "プライム",
        "スタンダード",
        "グロース",
    ]

    mask = pd.Series(
        False,
        index=df.index
    )

    for market in target_markets:

        mask |= (
            df[market_column]
            .astype(str)
            .str.contains(
                market,
                na=False
            )
        )

    stocks = df.loc[
        mask
    ].copy()

    stocks = stocks[
        stocks["コード"].notna()
    ]

    stocks = stocks.drop_duplicates(
        subset=["コード"]
    )

    stocks = stocks.reset_index(
        drop=True
    )

    print(
        f"対象銘柄数: {len(stocks)}"
    )

    print(
        "対象市場: "
        + ", ".join(target_markets)
    )

    return stocks


# ============================================================
# 営業日一覧
# ============================================================

def build_business_days(stock_list):

    """
    全銘柄のキャッシュから検証期間内の営業日を抽出する。

    特定銘柄だけを基準にせず、
    全キャッシュの日付を集約する。
    """

    all_dates = set()

    print(
        "営業日一覧を作成中..."
    )

    for i, code in enumerate(
        stock_list["コード"],
        start=1
    ):

        path = CACHE_DIR / f"{code}.csv"

        if not path.exists():
            continue

        try:

            df = pd.read_csv(
                path,
                usecols=["Date"]
            )

            dates = pd.to_datetime(
                df["Date"],
                errors="coerce"
            )

            for date in dates.dropna():

                date_string = (
                    date.strftime("%Y-%m-%d")
                )

                if (
                    START_DATE
                    <= date_string
                    <= END_DATE
                ):

                    all_dates.add(
                        date_string
                    )

        except Exception:
            continue

        if i % 500 == 0:

            print(
                f"  日付確認: {i}/{len(stock_list)}"
            )

    business_days = sorted(
        all_dates
    )

    print(
        f"検証営業日数: {len(business_days)}"
    )

    print(
        f"検証日: {business_days}"
    )

    return business_days


# ============================================================
# 未来の日付を取得
# ============================================================

def get_future_dates(
    dates,
    detection_position
):

    result = []

    for offset in range(
        1,
        FORWARD_DAYS + 1
    ):

        position = (
            detection_position
            + offset
        )

        if position >= len(dates):
            break

        result.append(
            dates[position]
        )

    return result


# ============================================================
# 数値変換
# ============================================================

def to_float(value):

    try:

        if pd.isna(value):
            return None

        return float(value)

    except Exception:

        return None


# ============================================================
# 最大騰落率
# ============================================================

def calculate_max_return(
    close_price,
    future_closes
):

    if close_price is None:
        return None

    if close_price == 0:
        return None

    returns = []

    for close in future_closes:

        if close is None:
            continue

        returns.append(
            (
                close
                / close_price
                - 1
            )
            * 100
        )

    if not returns:
        return None

    return max(returns)


# ============================================================
# 1銘柄の検証
# ============================================================

def process_stock(
    code,
    name,
    market,
    business_days
):

    cache_start = time.time()

    df = load_cache(
        code
    )

    if df is None:
        return []

    if "Close" not in df.columns:
        return []

    # --------------------------------------------------------
    # 日付
    # --------------------------------------------------------

    dates = get_date_series(
        df
    )

    df = df.copy()

    df["Date"] = dates

    df = df.dropna(
        subset=["Date"]
    )

    df = df.sort_values(
        "Date"
    )

    df = df.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # 検証期間より前から必要
    #
    # MA25 / MA75 / MACD等の計算のため、
    # キャッシュ全期間を使って指標計算する。
    # --------------------------------------------------------

    try:

        df = add_indicators(
            df
        )

    except Exception as e:

        print(
            f"指標計算エラー: {code} / {e}"
        )

        return []

    if df is None or df.empty:
        return []

    # --------------------------------------------------------
    # 日付を辞書化
    # --------------------------------------------------------

    date_to_position = {}

    for position, value in enumerate(
        df["Date"]
    ):

        if pd.isna(value):
            continue

        key = value.strftime(
            "%Y-%m-%d"
        )

        date_to_position[key] = position

    results = []

    # --------------------------------------------------------
    # 各検証日
    # --------------------------------------------------------

    for detection_date in business_days:

        if detection_date not in date_to_position:
            continue

        position = date_to_position[
            detection_date
        ]

        latest = df.iloc[
            position
        ]

        # ----------------------------------------------------
        # 終値
        # ----------------------------------------------------

        close_price = to_float(
            latest.get(
                "Close",
                None
            )
        )

        if close_price is None:
            continue

        # ----------------------------------------------------
        # 初動スコア
        #
        # 信用情報は、この全銘柄版では一旦None。
        # 価格・テクニカル部分を純粋に検証する。
        # ----------------------------------------------------

        try:

            initial_score = (
                calculate_initial_score(
                    latest,
                    None
                )
            )

        except Exception as e:

            print(
                f"スコア計算エラー: "
                f"{code} {detection_date} / {e}"
            )

            continue

        # ----------------------------------------------------
        # 将来5営業日
        # ----------------------------------------------------

        future_positions = []

        for offset in range(
            1,
            FORWARD_DAYS + 1
        ):

            future_position = (
                position
                + offset
            )

            if future_position >= len(df):
                break

            future_positions.append(
                future_position
            )

        future_closes = []

        for future_position in future_positions:

            future_close = to_float(
                df.iloc[
                    future_position
                ].get(
                    "Close",
                    None
                )
            )

            future_closes.append(
                future_close
            )

        # ----------------------------------------------------
        # 騰落率
        # ----------------------------------------------------

        returns = []

        for future_close in future_closes:

            if (
                future_close is None
                or close_price == 0
            ):

                returns.append(
                    None
                )

            else:

                returns.append(
                    round(
                        (
                            future_close
                            / close_price
                            - 1
                        )
                        * 100,
                        4
                    )
                )

        # ----------------------------------------------------
        # 最高騰落率
        # ----------------------------------------------------

        max_return = (
            calculate_max_return(
                close_price,
                future_closes
            )
        )

        # ----------------------------------------------------
        # 結果
        # ----------------------------------------------------

        row = {

            "検出日":
                detection_date,

            "コード":
                code,

            "銘柄名":
                name,

            "市場":
                market,

            "終値":
                close_price,

            "初動スコア":
                initial_score,

            # ----------------------------------------------
            # スコア構成要素
            # ----------------------------------------------

            "VolumeRatio":
                latest.get(
                    "VolumeRatio",
                    pd.NA
                ),

            "VolumeIncreaseDays":
                latest.get(
                    "VolumeIncreaseDays",
                    0
                ),

            "ChangePercent":
                latest.get(
                    "ChangePercent",
                    pd.NA
                ),

            "Change5Days":
                latest.get(
                    "Change5Days",
                    pd.NA
                ),

            "Change20Days":
                latest.get(
                    "Change20Days",
                    pd.NA
                ),

            "BreakoutSignal":
                latest.get(
                    "BreakoutSignal",
                    False
                ),

            "BreakoutFirstDay":
                latest.get(
                    "BreakoutFirstDay",
                    False
                ),

            "New30High":
                latest.get(
                    "New30High",
                    False
                ),

            "MACD_GC":
                latest.get(
                    "MACD_GC",
                    False
                ),

            "AboveMA5":
                latest.get(
                    "AboveMA5",
                    False
                ),

            "AboveMA25":
                latest.get(
                    "AboveMA25",
                    False
                ),

            "AboveMA75":
                latest.get(
                    "AboveMA75",
                    False
                ),

            "RSI":
                latest.get(
                    "RSI",
                    pd.NA
                ),

            # ----------------------------------------------
            # 将来騰落率
            # ----------------------------------------------

            "1日後":
                returns[0]
                if len(returns) >= 1
                else None,

            "2日後":
                returns[1]
                if len(returns) >= 2
                else None,

            "3日後":
                returns[2]
                if len(returns) >= 3
                else None,

            "4日後":
                returns[3]
                if len(returns) >= 4
                else None,

            "5日後":
                returns[4]
                if len(returns) >= 5
                else None,

            "5営業日以内最大騰落率":
                (
                    round(
                        max_return,
                        4
                    )
                    if max_return is not None
                    else None
                ),
        }

        results.append(
            row
        )

    return results


# ============================================================
# 集計
# ============================================================

def print_summary(
    result_df
):

    print()
    print(
        "============================================================"
    )
    print(
        "=== 全銘柄検証完了 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"対象銘柄日数 : {len(result_df):,}"
    )

    if result_df.empty:
        return

    print()
    print(
        "=== 初動スコア別集計 ==="
    )

    score_values = sorted(
        result_df["初動スコア"]
        .dropna()
        .unique(),
        reverse=True
    )

    for score in score_values:

        group = result_df[
            result_df["初動スコア"]
            == score
        ]

        print()
        print(
            f"【初動スコア {score}点】 "
            f"対象 {len(group):,}銘柄日"
        )

        for days in range(
            1,
            FORWARD_DAYS + 1
        ):

            column = f"{days}日後"

            values = pd.to_numeric(
                group[column],
                errors="coerce"
            ).dropna()

            if values.empty:
                continue

            average = values.mean()

            win_rate = (
                values.gt(0).mean()
                * 100
            )

            plus5_rate = (
                values.ge(5).mean()
                * 100
            )

            plus10_rate = (
                values.ge(10).mean()
                * 100
            )

            print(
                f"  {days}日後: "
                f"平均 {average:+.2f}% / "
                f"勝率 {win_rate:.1f}% / "
                f"+5%率 {plus5_rate:.1f}% / "
                f"+10%率 {plus10_rate:.1f}% / "
                f"n={len(values):,}"
            )

    # --------------------------------------------------------
    # 5営業日以内最大騰落率
    # --------------------------------------------------------

    print()
    print(
        "=== 5営業日以内・最大騰落率集計 ==="
    )

    max_values = pd.to_numeric(
        result_df[
            "5営業日以内最大騰落率"
        ],
        errors="coerce"
    ).dropna()

    if not max_values.empty:

        print(
            f"平均最大騰落率 : "
            f"{max_values.mean():+.2f}%"
        )

        print(
            f"+5%以上 : "
            f"{max_values.ge(5).mean() * 100:.1f}%"
        )

        print(
            f"+10%以上: "
            f"{max_values.ge(10).mean() * 100:.1f}%"
        )

        print(
            f"+20%以上: "
            f"{max_values.ge(20).mean() * 100:.1f}%"
        )

        print(
            f"最大値   : "
            f"{max_values.max():+.2f}%"
        )


# ============================================================
# メイン
# ============================================================

def main():

    total_start = time.time()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print()
    print(
        "============================================================"
    )
    print(
        "=== 全銘柄・初動スコア履歴検証 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"検証期間 : {START_DATE} ～ {END_DATE}"
    )

    print(
        f"キャッシュ : {CACHE_DIR}"
    )

    # --------------------------------------------------------
    # 銘柄一覧
    # --------------------------------------------------------

    stock_list = load_stock_list()

    # --------------------------------------------------------
    # 営業日
    # --------------------------------------------------------

    business_days = build_business_days(
        stock_list
    )

    if not business_days:

        raise RuntimeError(
            "検証営業日が取得できませんでした。"
        )

    # --------------------------------------------------------
    # 全銘柄処理
    # --------------------------------------------------------

    all_results = []

    total_stocks = len(
        stock_list
    )

    process_start = time.time()

    for index, stock in stock_list.iterrows():

        code = stock["コード"]

        name = stock.get(
            "銘柄名",
            ""
        )

        market = stock.get(
            "市場・商品区分",
            ""
        )

        results = process_stock(
            code,
            name,
            market,
            business_days
        )

        all_results.extend(
            results
        )

        current = index + 1

        if (
            current % 100 == 0
            or current == total_stocks
        ):

            elapsed = (
                time.time()
                - process_start
            )

            print(
                f"進捗: "
                f"{current:,}/{total_stocks:,} "
                f"({current / total_stocks * 100:.1f}%) "
                f"/ "
                f"記録 {len(all_results):,}件 "
                f"/ "
                f"{elapsed:.1f}秒"
            )

    # --------------------------------------------------------
    # DataFrame
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        all_results
    )

    if result_df.empty:

        raise RuntimeError(
            "検証結果が0件です。"
        )

    # --------------------------------------------------------
    # 並び順
    # --------------------------------------------------------

    sort_columns = [
        "検出日",
        "初動スコア",
        "コード",
    ]

    result_df = result_df.sort_values(
        sort_columns,
        ascending=[
            True,
            False,
            True,
        ]
    )

    result_df = result_df.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    output_path = (
        OUTPUT_DIR
        / "historical_full_universe_tracking.csv"
    )

    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # 集計
    # --------------------------------------------------------

    print_summary(
        result_df
    )

    # --------------------------------------------------------
    # 完了
    # --------------------------------------------------------

    total_time = (
        time.time()
        - total_start
    )

    print()
    print(
        "============================================================"
    )
    print(
        "=== 全銘柄検証完了 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"対象銘柄数 : {total_stocks:,}"
    )

    print(
        f"検証営業日数 : {len(business_days)}"
    )

    print(
        f"検証記録数 : {len(result_df):,}"
    )

    print(
        f"保存先 : {output_path}"
    )

    print(
        f"処理時間 : {total_time:.1f} 秒"
    )


if __name__ == "__main__":
    main()