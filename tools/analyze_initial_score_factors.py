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


# ============================================================
# 設定
# ============================================================

CACHE_DIR = ROOT_DIR / "data" / "cache"
OUTPUT_DIR = ROOT_DIR / "data" / "tracking"

JPX_FILE = ROOT_DIR / "data" / "jpx_stock_list.xls"


# ------------------------------------------------------------
# 検証期間
# ------------------------------------------------------------

START_DATE = "2026-05-01"
END_DATE = "2026-08-07"


# ------------------------------------------------------------
# 何営業日先まで見るか
# ------------------------------------------------------------

FORWARD_DAYS = 5


# ============================================================
# 高騰初動の定義
# ============================================================

TARGET_5 = 5
TARGET_10 = 10
TARGET_20 = 20


# ============================================================
# 日付
# ============================================================

def normalize_code(value):

    if pd.isna(value):
        return None

    text = str(value).strip()

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

    df = pd.read_excel(
        JPX_FILE
    )

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
            "銘柄コード列がありません。"
        )

    df["コード"] = (
        df[code_column]
        .apply(normalize_code)
    )

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
            "市場区分列がありません。"
        )

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
        f"対象銘柄数: {len(stocks):,}"
    )

    return stocks


# ============================================================
# キャッシュ読み込み
# ============================================================

def load_cache(code):

    path = (
        CACHE_DIR
        / f"{code}.csv"
    )

    if not path.exists():

        return None

    try:

        df = pd.read_csv(
            path
        )

        if df.empty:

            return None

        if "Date" not in df.columns:

            return None

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

    except Exception:

        return None


# ============================================================
# 営業日一覧
# ============================================================

def build_business_days(stock_list):

    dates = set()

    print(
        "検証営業日を作成中..."
    )

    for index, stock in stock_list.iterrows():

        code = stock["コード"]

        path = (
            CACHE_DIR
            / f"{code}.csv"
        )

        if not path.exists():

            continue

        try:

            df = pd.read_csv(
                path,
                usecols=["Date"]
            )

            values = pd.to_datetime(
                df["Date"],
                errors="coerce"
            )

            for value in values.dropna():

                date_string = (
                    value.strftime("%Y-%m-%d")
                )

                if (
                    START_DATE
                    <= date_string
                    <= END_DATE
                ):

                    dates.add(
                        date_string
                    )

        except Exception:

            continue

        current = index + 1

        if current % 500 == 0:

            print(
                f"  日付確認: "
                f"{current:,}/{len(stock_list):,}"
            )

    result = sorted(
        dates
    )

    print(
        f"検証営業日数: {len(result)}"
    )

    print(
        f"期間: {START_DATE} ～ {END_DATE}"
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
# 真偽値変換
# ============================================================

def to_bool(value):

    if isinstance(value, bool):

        return value

    if pd.isna(value):

        return False

    text = str(value).strip().lower()

    return text in [
        "true",
        "1",
        "yes",
        "y",
    ]


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

    values = []

    for close in future_closes:

        if close is None:
            continue

        values.append(
            (
                close
                / close_price
                - 1
            )
            * 100
        )

    if not values:

        return None

    return max(values)


# ============================================================
# 1銘柄処理
# ============================================================

def process_stock(
    code,
    name,
    market,
    business_days
):

    df = load_cache(
        code
    )

    if df is None:
        return []

    if "Close" not in df.columns:
        return []

    try:

        df = add_indicators(
            df
        )

    except Exception:

        return []

    if df is None or df.empty:

        return []

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

    df = df.reset_index(
        drop=True
    )

    date_to_position = {}

    for position, value in enumerate(
        df["Date"]
    ):

        key = value.strftime(
            "%Y-%m-%d"
        )

        date_to_position[key] = position

    results = []

    for detection_date in business_days:

        if detection_date not in date_to_position:

            continue

        position = date_to_position[
            detection_date
        ]

        latest = df.iloc[
            position
        ]

        close_price = to_float(
            latest.get(
                "Close"
            )
        )

        if close_price is None:

            continue

        # ----------------------------------------------------
        # 将来5営業日
        # ----------------------------------------------------

        future_closes = []

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

            future_close = to_float(
                df.iloc[
                    future_position
                ].get(
                    "Close"
                )
            )

            future_closes.append(
                future_close
            )

        if not future_closes:

            continue

        # ----------------------------------------------------
        # 最大騰落率
        # ----------------------------------------------------

        max_return = calculate_max_return(
            close_price,
            future_closes
        )

        if max_return is None:

            continue

        # ----------------------------------------------------
        # 各条件
        # ----------------------------------------------------

        volume_ratio = to_float(
            latest.get(
                "VolumeRatio"
            )
        )

        volume_days = to_float(
            latest.get(
                "VolumeIncreaseDays"
            )
        )

        change_percent = to_float(
            latest.get(
                "ChangePercent"
            )
        )

        change_5 = to_float(
            latest.get(
                "Change5Days"
            )
        )

        change_20 = to_float(
            latest.get(
                "Change20Days"
            )
        )

        rsi = to_float(
            latest.get(
                "RSI"
            )
        )

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

            "VolumeRatio":
                volume_ratio,

            "VolumeIncreaseDays":
                volume_days,

            "ChangePercent":
                change_percent,

            "Change5Days":
                change_5,

            "Change20Days":
                change_20,

            "RSI":
                rsi,

            "BreakoutSignal":
                to_bool(
                    latest.get(
                        "BreakoutSignal",
                        False
                    )
                ),

            "BreakoutFirstDay":
                to_bool(
                    latest.get(
                        "BreakoutFirstDay",
                        False
                    )
                ),

            "New30High":
                to_bool(
                    latest.get(
                        "New30High",
                        False
                    )
                ),

            "NewYearHigh":
                to_bool(
                    latest.get(
                        "NewYearHigh",
                        False
                    )
                ),

            "MACD_GC":
                to_bool(
                    latest.get(
                        "MACD_GC",
                        False
                    )
                ),

            "AboveMA5":
                to_bool(
                    latest.get(
                        "AboveMA5",
                        False
                    )
                ),

            "AboveMA25":
                to_bool(
                    latest.get(
                        "AboveMA25",
                        False
                    )
                ),

            "AboveMA75":
                to_bool(
                    latest.get(
                        "AboveMA75",
                        False
                    )
                ),

            # ------------------------------------------------
            # 高騰結果
            # ------------------------------------------------

            "5営業日以内最大騰落率":
                round(
                    max_return,
                    4
                ),

            "Hit5":
                max_return >= TARGET_5,

            "Hit10":
                max_return >= TARGET_10,

            "Hit20":
                max_return >= TARGET_20,
        }

        results.append(
            row
        )

    return results


# ============================================================
# 条件評価
# ============================================================

def build_conditions(df):

    conditions = {}

    # --------------------------------------------------------
    # 出来高急増
    # --------------------------------------------------------

    conditions[
        "出来高1.5倍以上"
    ] = (
        pd.to_numeric(
            df["VolumeRatio"],
            errors="coerce"
        )
        >= 1.5
    )

    conditions[
        "出来高2倍以上"
    ] = (
        pd.to_numeric(
            df["VolumeRatio"],
            errors="coerce"
        )
        >= 2.0
    )

    conditions[
        "出来高3倍以上"
    ] = (
        pd.to_numeric(
            df["VolumeRatio"],
            errors="coerce"
        )
        >= 3.0
    )

    # --------------------------------------------------------
    # 出来高増加日数
    # --------------------------------------------------------

    volume_days = pd.to_numeric(
        df["VolumeIncreaseDays"],
        errors="coerce"
    )

    conditions[
        "出来高増加1日"
    ] = volume_days == 1

    conditions[
        "出来高増加2日"
    ] = volume_days == 2

    conditions[
        "出来高増加3日"
    ] = volume_days == 3

    # --------------------------------------------------------
    # 前日比
    # --------------------------------------------------------

    change = pd.to_numeric(
        df["ChangePercent"],
        errors="coerce"
    )

    conditions[
        "前日比+1%以上"
    ] = change >= 1

    conditions[
        "前日比+3%以上"
    ] = change >= 3

    conditions[
        "前日比+5%以上"
    ] = change >= 5

    # --------------------------------------------------------
    # 5日騰落率
    # --------------------------------------------------------

    change5 = pd.to_numeric(
        df["Change5Days"],
        errors="coerce"
    )

    conditions[
        "5日騰落率5%未満"
    ] = change5 < 5

    conditions[
        "5日騰落率10%未満"
    ] = change5 < 10

    conditions[
        "5日騰落率0%未満"
    ] = change5 < 0

    # --------------------------------------------------------
    # 20日騰落率
    # --------------------------------------------------------

    change20 = pd.to_numeric(
        df["Change20Days"],
        errors="coerce"
    )

    conditions[
        "20日騰落率10%未満"
    ] = change20 < 10

    conditions[
        "20日騰落率20%未満"
    ] = change20 < 20

    # --------------------------------------------------------
    # ブレイク
    # --------------------------------------------------------

    conditions[
        "ブレイク"
    ] = df["BreakoutSignal"]

    conditions[
        "ブレイク初日"
    ] = df["BreakoutFirstDay"]

    # --------------------------------------------------------
    # 高値
    # --------------------------------------------------------

    conditions[
        "30日高値更新"
    ] = df["New30High"]

    conditions[
        "年初来高値更新"
    ] = df["NewYearHigh"]

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    conditions[
        "MACD GC"
    ] = df["MACD_GC"]

    # --------------------------------------------------------
    # MA
    # --------------------------------------------------------

    conditions[
        "MA5上"
    ] = df["AboveMA5"]

    conditions[
        "MA25上"
    ] = df["AboveMA25"]

    conditions[
        "MA75上"
    ] = df["AboveMA75"]

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = pd.to_numeric(
        df["RSI"],
        errors="coerce"
    )

    conditions[
        "RSI70未満"
    ] = rsi < 70

    conditions[
        "RSI80未満"
    ] = rsi < 80

    conditions[
        "RSI90未満"
    ] = rsi < 90

    return conditions


# ============================================================
# 条件集計
# ============================================================

def analyze_condition(
    df,
    condition_name,
    mask
):

    selected = df.loc[
        mask
    ]

    other = df.loc[
        ~mask
    ]

    if selected.empty:

        return None

    selected_max = pd.to_numeric(
        selected[
            "5営業日以内最大騰落率"
        ],
        errors="coerce"
    ).dropna()

    other_max = pd.to_numeric(
        other[
            "5営業日以内最大騰落率"
        ],
        errors="coerce"
    ).dropna()

    if selected_max.empty:

        return None

    selected_hit5 = (
        selected_max.ge(5).mean()
        * 100
    )

    selected_hit10 = (
        selected_max.ge(10).mean()
        * 100
    )

    selected_hit20 = (
        selected_max.ge(20).mean()
        * 100
    )

    if other_max.empty:

        other_hit5 = None
        other_hit10 = None
        other_hit20 = None
        other_average = None

    else:

        other_hit5 = (
            other_max.ge(5).mean()
            * 100
        )

        other_hit10 = (
            other_max.ge(10).mean()
            * 100
        )

        other_hit20 = (
            other_max.ge(20).mean()
            * 100
        )

        other_average = (
            other_max.mean()
        )

    return {

        "条件":
            condition_name,

        "条件あり件数":
            len(selected_max),

        "条件あり平均最大騰落率":
            selected_max.mean(),

        "条件あり+5%率":
            selected_hit5,

        "条件あり+10%率":
            selected_hit10,

        "条件あり+20%率":
            selected_hit20,

        "条件なし件数":
            len(other_max),

        "条件なし平均最大騰落率":
            other_average,

        "条件なし+5%率":
            other_hit5,

        "条件なし+10%率":
            other_hit10,

        "条件なし+20%率":
            other_hit20,

        "差+5%率":
            (
                selected_hit5 - other_hit5
                if other_hit5 is not None
                else None
            ),

        "差+10%率":
            (
                selected_hit10 - other_hit10
                if other_hit10 is not None
                else None
            ),

        "差+20%率":
            (
                selected_hit20 - other_hit20
                if other_hit20 is not None
                else None
            ),
    }


# ============================================================
# メイン
# ============================================================

def main():

    total_start = time.time()

    print()
    print(
        "============================================================"
    )
    print(
        "=== 初動スコア構成要素・全銘柄検証 ==="
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

    print(
        "高騰判定 : "
        f"5営業日以内最大騰落率 "
        f"+5% / +10% / +20%"
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
            "検証営業日がありません。"
        )

    # --------------------------------------------------------
    # 全銘柄
    # --------------------------------------------------------

    all_results = []

    process_start = time.time()

    total_stocks = len(
        stock_list
    )

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

        rows = process_stock(
            code,
            name,
            market,
            business_days
        )

        all_results.extend(
            rows
        )

        current = index + 1

        if (
            current % 500 == 0
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

    print()
    print(
        "============================================================"
    )
    print(
        "=== 条件別分析 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"検証記録数 : {len(result_df):,}"
    )

    # --------------------------------------------------------
    # 条件
    # --------------------------------------------------------

    conditions = build_conditions(
        result_df
    )

    analysis_rows = []

    for condition_name, mask in conditions.items():

        result = analyze_condition(
            result_df,
            condition_name,
            mask
        )

        if result is not None:

            analysis_rows.append(
                result
            )

    analysis_df = pd.DataFrame(
        analysis_rows
    )

    # --------------------------------------------------------
    # 表示
    # --------------------------------------------------------

    display_columns = [
        "条件",
        "条件あり件数",
        "条件あり平均最大騰落率",
        "条件あり+5%率",
        "条件あり+10%率",
        "条件あり+20%率",
        "条件なし平均最大騰落率",
        "条件なし+5%率",
        "条件なし+10%率",
        "条件なし+20%率",
        "差+5%率",
        "差+10%率",
        "差+20%率",
    ]

    for _, row in analysis_df.iterrows():

        print()

        print(
            f"【{row['条件']}】 "
            f"n={int(row['条件あり件数']):,}"
        )

        print(
            f"  平均最大騰落率 : "
            f"{row['条件あり平均最大騰落率']:+.2f}%"
        )

        print(
            f"  +5%率          : "
            f"{row['条件あり+5%率']:.1f}%"
        )

        print(
            f"  +10%率         : "
            f"{row['条件あり+10%率']:.1f}%"
        )

        print(
            f"  +20%率         : "
            f"{row['条件あり+20%率']:.1f}%"
        )

        if pd.notna(
            row["条件なし+10%率"]
        ):

            print(
                f"  条件なし+10%率 : "
                f"{row['条件なし+10%率']:.1f}%"
            )

            print(
                f"  +10%率差       : "
                f"{row['差+10%率']:+.1f}pt"
            )

    # --------------------------------------------------------
    # CSV保存
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        OUTPUT_DIR
        / "initial_score_factor_analysis.csv"
    )

    analysis_df[
        display_columns
    ].to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # 生データ保存
    # --------------------------------------------------------

    raw_path = (
        OUTPUT_DIR
        / "initial_score_factor_raw.csv"
    )

    result_df.to_csv(
        raw_path,
        index=False,
        encoding="utf-8-sig"
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
        "=== 初動スコア構成要素検証完了 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"対象銘柄数 : {total_stocks:,}"
    )

    print(
        f"検証営業日数 : {len(business_days):,}"
    )

    print(
        f"検証記録数 : {len(result_df):,}"
    )

    print(
        f"分析結果 : {output_path}"
    )

    print(
        f"生データ : {raw_path}"
    )

    print(
        f"処理時間 : {total_time:.1f} 秒"
    )


if __name__ == "__main__":
    main()