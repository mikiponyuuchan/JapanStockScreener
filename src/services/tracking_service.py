import pandas as pd
from pathlib import Path
from datetime import datetime

import holidays

from services.yahoo_service import (
    get_history,
    _download_history_batch,
)


# ============================================================
# 設定
# ============================================================

TRACKING_DIR = Path("data/tracking")

TRACKING_FILE = (
    TRACKING_DIR / "initial_move_tracking.csv"
)


# ============================================================
# フォルダ
# ============================================================

def ensure_tracking_folder():

    TRACKING_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# 空の追跡データ
# ============================================================

def empty_tracking_dataframe():

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "検出時終値",
        "強気度",
        "初動スコア",
    ]

    # 1～10営業日後
    for day in range(1, 11):

        columns.append(
            f"{day}日後終値"
        )

        columns.append(
            f"{day}日後騰落率"
        )

    return pd.DataFrame(
        columns=columns
    )


# ============================================================
# 追跡ファイル読み込み
# ============================================================

def load_tracking():

    ensure_tracking_folder()

    if not TRACKING_FILE.exists():

        return empty_tracking_dataframe()

    try:

        df = pd.read_csv(
            TRACKING_FILE,
            encoding="utf-8-sig"
        )

    except Exception as e:

        print(
            "追跡ファイル読込ERROR :",
            e
        )

        return empty_tracking_dataframe()

    required_columns = (
        empty_tracking_dataframe().columns
    )

    # 不足列を追加
    for column in required_columns:

        if column not in df.columns:

            df[column] = ""

    # 列順を統一
    df = df[
        list(required_columns)
    ]

    return df


# ============================================================
# 営業日計算
# ============================================================

def add_business_days(
        date,
        days):

    date = pd.Timestamp(
        date
    ).normalize()

    jp_holidays = holidays.Japan(
        years=[
            date.year - 1,
            date.year,
            date.year + 1
        ]
    )

    current = date

    count = 0

    while count < days:

        current += pd.Timedelta(
            days=1
        )

        # 土日
        if current.weekday() >= 5:

            continue

        # 日本の祝日
        if current.date() in jp_holidays:

            continue

        count += 1

    return current


# ============================================================
# Yahoo履歴から価格取得
# ============================================================

def _find_price(
        history,
        target_date):

    if history is None:

        return None

    if history.empty:

        return None

    df = history.copy()

    # --------------------------------------------------------
    # Date列をindexへ
    # --------------------------------------------------------

    if "Date" in df.columns:

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["Date"]
        )

        if df.empty:

            return None

        df = df.set_index(
            "Date"
        )

    else:

        try:

            df.index = pd.to_datetime(
                df.index,
                errors="coerce"
            )

        except Exception:

            return None

        df = df[
            ~df.index.isna()
        ]

    if df.empty:

        return None

    # --------------------------------------------------------
    # timezone除去
    # --------------------------------------------------------

    if getattr(
        df.index,
        "tz",
        None
    ) is not None:

        df.index = (
            df.index
            .tz_localize(None)
        )

    # --------------------------------------------------------
    # 対象日以降
    # --------------------------------------------------------

    target_date = pd.Timestamp(
        target_date
    ).normalize()

    available = df[
        df.index.normalize()
        >= target_date
    ]

    if available.empty:

        return None

    available = (
        available
        .sort_index()
    )

    # --------------------------------------------------------
    # Close取得
    # --------------------------------------------------------

    if "Close" not in available.columns:

        return None

    price = available.iloc[0]["Close"]

    if pd.isna(price):

        return None

    try:

        return float(price)

    except Exception:

        return None


# ============================================================
# 指定日以降の株価取得
# ============================================================

def get_price_on_or_after(
        code,
        target_date):

    # --------------------------------------------------------
    # まず通常履歴
    # --------------------------------------------------------

    try:

        history = get_history(
            code
        )

    except Exception:

        history = None

    price = _find_price(
        history,
        target_date
    )

    if price is not None:

        return price

    # --------------------------------------------------------
    # 履歴に無ければYahoo 10d
    # --------------------------------------------------------

    try:

        batch_result = (
            _download_history_batch(
                [str(code)],
                period="10d",
                batch_size=1
            )
        )

    except Exception:

        return None

    if not batch_result:

        return None

    yahoo_history = batch_result.get(
        str(code)
    )

    return _find_price(
        yahoo_history,
        target_date
    )


# ============================================================
# 騰落率計算
# ============================================================

def calculate_change(
        base_price,
        current_price):

    if (
        base_price is None
        or current_price is None
    ):

        return None

    try:

        base_price = float(
            base_price
        )

        current_price = float(
            current_price
        )

    except Exception:

        return None

    if pd.isna(base_price):

        return None

    if base_price == 0:

        return None

    return round(
        (
            current_price
            /
            base_price
            - 1
        )
        * 100,
        2
    )


# ============================================================
# 追跡結果更新
# ============================================================

def update_tracking_results(
        tracking_df,
        data_date=None):

    if tracking_df.empty:

        return tracking_df

    # --------------------------------------------------------
    # 基準日
    # --------------------------------------------------------

    if data_date is not None:

        market_date = pd.Timestamp(
            data_date
        ).normalize()

    else:

        market_date = pd.Timestamp(
            datetime.now().date()
        )

    print()
    print(
        "過去の初動銘柄を追跡中..."
    )

    # --------------------------------------------------------
    # 将来日のデータを除去
    # --------------------------------------------------------

    tracking_dates = pd.to_datetime(
        tracking_df["検出日"],
        errors="coerce"
    )

    future_mask = (
        tracking_dates > market_date
    )

    future_count = int(
        future_mask.sum()
    )

    if future_count > 0:

        print(
            "未来日付の追跡データを除去 :",
            future_count,
            "件"
        )

        tracking_df = (
            tracking_df[
                ~future_mask
            ]
            .copy()
        )

    tracking_df.reset_index(
        drop=True,
        inplace=True
    )

    # --------------------------------------------------------
    # 更新対象コード
    # --------------------------------------------------------

    target_codes = set()

    for index, row in tracking_df.iterrows():

        try:

            detection_date = pd.Timestamp(
                row["検出日"]
            ).normalize()

        except Exception:

            continue

        code = str(
            row["コード"]
        )

        base_price = pd.to_numeric(
            row["検出時終値"],
            errors="coerce"
        )

        if pd.isna(base_price):

            continue

        for day in range(1, 11):

            target_date = add_business_days(
                detection_date,
                day
            )

            # まだ対象日になっていない
            if market_date < target_date:

                continue

            price_column = (
                f"{day}日後終値"
            )

            existing_price = pd.to_numeric(
                row[price_column],
                errors="coerce"
            )

            # 既に取得済み
            if pd.notna(existing_price):

                continue

            target_codes.add(
                code
            )

    target_codes = sorted(
        target_codes
    )

    print(
        "Yahoo一括取得対象銘柄 :",
        len(target_codes),
        "件"
    )

    # --------------------------------------------------------
    # Yahoo一括取得
    # --------------------------------------------------------

    yahoo_results = {}

    if target_codes:

        try:

            yahoo_results = (
                _download_history_batch(
                    target_codes,
                    period="10d",
                    batch_size=100
                )
            )

        except Exception as e:

            print(
                "Yahoo batch download ERROR :",
                e
            )

            yahoo_results = {}

    # --------------------------------------------------------
    # 各銘柄更新
    # --------------------------------------------------------

    updated_count = 0

    for index, row in tracking_df.iterrows():

        try:

            detection_date = pd.Timestamp(
                row["検出日"]
            ).normalize()

        except Exception:

            continue

        code = str(
            row["コード"]
        )

        base_price = pd.to_numeric(
            row["検出時終値"],
            errors="coerce"
        )

        if pd.isna(base_price):

            continue

        history = yahoo_results.get(
            code
        )

        for day in range(1, 11):

            target_date = add_business_days(
                detection_date,
                day
            )

            price_column = (
                f"{day}日後終値"
            )

            change_column = (
                f"{day}日後騰落率"
            )

            # まだ対象日ではない
            if market_date < target_date:

                continue

            # 既に取得済み
            existing_price = pd.to_numeric(
                row[price_column],
                errors="coerce"
            )

            if pd.notna(existing_price):

                continue

            # ------------------------------------------------
            # 一括取得データから検索
            # ------------------------------------------------

            price = _find_price(
                history,
                target_date
            )

            # ------------------------------------------------
            # 無ければ個別取得
            # ------------------------------------------------

            if price is None:

                try:

                    price = get_price_on_or_after(
                        code,
                        target_date
                    )

                except Exception:

                    price = None

            if price is None:

                continue

            # ------------------------------------------------
            # 終値
            # ------------------------------------------------

            tracking_df.at[
                index,
                price_column
            ] = round(
                price,
                2
            )

            # ------------------------------------------------
            # 騰落率
            # ------------------------------------------------

            change = calculate_change(
                base_price,
                price
            )

            if change is not None:

                tracking_df.at[
                    index,
                    change_column
                ] = change

            updated_count += 1

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    tracking_df.to_csv(
        TRACKING_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        "追跡結果更新 :",
        updated_count,
        "件"
    )

    return tracking_df


# ============================================================
# 初動銘柄を記録
# ============================================================

def record_initial_move(df):

    ensure_tracking_folder()

    tracking_df = load_tracking()

    # --------------------------------------------------------
    # データ日
    # --------------------------------------------------------

    if (
        "_data_date" in df.columns
        and not df.empty
    ):

        data_date = str(
            df["_data_date"].iloc[0]
        )

    else:

        data_date = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )

    # --------------------------------------------------------
    # 過去データ更新
    # --------------------------------------------------------

    tracking_df = update_tracking_results(
        tracking_df,
        data_date
    )

    # --------------------------------------------------------
    # 対象データ無し
    # --------------------------------------------------------

    if df.empty:

        print(
            "初動スコア対象データなし"
        )

        return tracking_df

    # --------------------------------------------------------
    # 初動スコアTOP20を対象
    #
    # 呼び出し側からTOP20が渡される想定。
    # 念のためここでも初動スコア順に整列。
    # --------------------------------------------------------

    if "初動スコア" in df.columns:

        try:

            df = (
                df.sort_values(
                    "初動スコア",
                    ascending=False
                )
                .head(20)
                .copy()
            )

        except Exception:

            df = df.head(20).copy()

    else:

        df = df.head(20).copy()

    # --------------------------------------------------------
    # 新規記録
    # --------------------------------------------------------

    new_rows = []

    for _, row in df.iterrows():

        # ----------------------------------------------------
        # コード
        # ----------------------------------------------------

        if "コード" not in row.index:

            continue

        code = str(
            row["コード"]
        )

        if not code or code == "nan":

            continue

        # ----------------------------------------------------
        # 終値取得
        #
        # ★今回のエラー対策
        #
        # analyzerの結果で
        # 「終値」が無い場合でも停止しない。
        #
        # 優先順位：
        #   1. 終値
        #   2. Close
        #   3. 株価
        # ----------------------------------------------------

        base_price = None

        for price_column in [
            "終値",
            "Close",
            "株価",
        ]:

            if price_column not in row.index:

                continue

            value = pd.to_numeric(
                row[price_column],
                errors="coerce"
            )

            if pd.notna(value):

                base_price = float(
                    value
                )

                break

        # ----------------------------------------------------
        # 終値が無ければ記録しない
        #
        # ここで main 全体を落とさない。
        # ----------------------------------------------------

        if base_price is None:

            print(
                f"初動追跡SKIP {code} : "
                "終値データなし"
            )

            continue

        # ----------------------------------------------------
        # 銘柄名
        # ----------------------------------------------------

        name = ""

        if "銘柄名" in row.index:

            value = row["銘柄名"]

            if pd.notna(value):

                name = value

        # ----------------------------------------------------
        # 強気度
        #
        # 旧バージョンとの互換性を残す。
        # ----------------------------------------------------

        bullish_score = ""

        if "強気度" in row.index:

            value = row["強気度"]

            if pd.notna(value):

                bullish_score = value

        # ----------------------------------------------------
        # 初動スコア
        # ----------------------------------------------------

        initial_score = ""

        if "初動スコア" in row.index:

            value = row["初動スコア"]

            if pd.notna(value):

                initial_score = value

        # ----------------------------------------------------
        # 同日・同銘柄の重複確認
        # ----------------------------------------------------

        if not tracking_df.empty:

            already_exists = (
                (
                    tracking_df[
                        "検出日"
                    ]
                    .astype(str)
                    == data_date
                )
                &
                (
                    tracking_df[
                        "コード"
                    ]
                    .astype(str)
                    == code
                )
            ).any()

        else:

            already_exists = False

        if already_exists:

            continue

        # ----------------------------------------------------
        # 新規行
        # ----------------------------------------------------

        new_row = {

            "検出日":
                data_date,

            "コード":
                code,

            "銘柄名":
                name,

            "検出時終値":
                round(
                    base_price,
                    2
                ),

            "強気度":
                bullish_score,

            "初動スコア":
                initial_score,
        }

        # ----------------------------------------------------
        # 1～10営業日後
        # ----------------------------------------------------

        for day in range(1, 11):

            new_row[
                f"{day}日後終値"
            ] = ""

            new_row[
                f"{day}日後騰落率"
            ] = ""

        new_rows.append(
            new_row
        )

    # --------------------------------------------------------
    # 新規データ追加
    # --------------------------------------------------------

    if new_rows:

        new_df = pd.DataFrame(
            new_rows
        )

        tracking_df = pd.concat(
            [
                tracking_df,
                new_df
            ],
            ignore_index=True
        )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    tracking_df.to_csv(
        TRACKING_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(
        "初動追跡データ保存 :",
        TRACKING_FILE
    )

    print(
        "今回の新規記録件数 :",
        len(new_rows)
    )

    return tracking_df