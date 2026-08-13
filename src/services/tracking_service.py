import pandas as pd
from pathlib import Path
from datetime import datetime

import pandas as pd
import holidays

from services.yahoo_service import (
    get_history,
    _download_history_batch,
)

# ==========================
# 設定
# ==========================

TRACKING_DIR = Path("data/tracking")

TRACKING_FILE = (
    TRACKING_DIR / "initial_move_tracking.csv"
)


# ==========================
# フォルダ準備
# ==========================

def ensure_tracking_folder():

    TRACKING_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


# ==========================
# 空の追跡データ
# ==========================

def empty_tracking_dataframe():

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "検出時株価",
        "強気度",
        "初動スコア",
    ]

    # 1日後～10日後
    for day in range(1, 11):

        columns.append(
            f"{day}日後株価"
        )

        columns.append(
            f"{day}日後騰落率%"
        )

    return pd.DataFrame(
        columns=columns
    )


# ==========================
# 追跡ファイル読み込み
# ==========================

def load_tracking():

    ensure_tracking_folder()

    if not TRACKING_FILE.exists():

        return empty_tracking_dataframe()

    df = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig"
    )

    # ==========================
    # 必要列
    # ==========================

    required_columns = (
        empty_tracking_dataframe().columns
    )

    # ==========================
    # 古いCSVとの互換性
    # ==========================

    for column in required_columns:

        if column not in df.columns:

            df[column] = ""

    # ==========================
    # 必要列だけに統一
    # ==========================

    df = df[
        list(required_columns)
    ]

    return df


# ==========================
# 営業日計算
# ==========================

def add_business_days(
        date,
        days):

    date = pd.Timestamp(
        date
    ).normalize()

    # 日本の祝日
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

        # 土日を除外
        if current.weekday() >= 5:
            continue

        # 日本の祝日を除外
        if current.date() in jp_holidays:
            continue

        count += 1

    return current

# ==========================
# 株価取得
# ==========================

def get_price_on_or_after(
        code,
        target_date):

    target_date = pd.Timestamp(
        target_date
    ).normalize()

    # ==========================
    # まず通常の履歴を確認
    # ==========================

    try:

        history = get_history(
            code
        )

    except Exception:

        history = None

    # ==========================
    # 履歴を検索する関数
    # ==========================

    def find_price(df):

        if df is None:
            return None

        if df.empty:
            return None

        df = df.copy()

        # --------------------------
        # Dateをインデックスへ
        # --------------------------

        if "Date" in df.columns:

            df["Date"] = pd.to_datetime(
                df["Date"],
                errors="coerce"
            )

            df = df.dropna(
                subset=["Date"]
            )

            df = df.set_index(
                "Date"
            )

        else:

            df.index = pd.to_datetime(
                df.index,
                errors="coerce"
            )

            df = df[
                ~df.index.isna()
            ]

        # --------------------------
        # タイムゾーン除去
        # --------------------------

        if getattr(
            df.index,
            "tz",
            None
        ) is not None:

            df.index = (
                df.index
                .tz_localize(None)
            )

        # --------------------------
        # 指定日以降を検索
        # --------------------------

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

        price = available.iloc[0].get(
            "Close"
        )

        if pd.isna(price):

            return None

        return float(price)

    # ==========================
    # 通常履歴から取得
    # ==========================

    price = find_price(
        history
    )

    if price is not None:

        return price

    # ==========================
    # 通常履歴に無ければ
    # Yahoo 10d を直接取得
    #
    # 8/12のような当日データが
    # Parquetにまだ反映されていない
    # 場合に対応
    # ==========================

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

    price = find_price(
        yahoo_history
    )

    if price is not None:

        return price

    return None

# ==========================
# 騰落率計算
# ==========================

def calculate_change(
        base_price,
        current_price):

    if (
        base_price is None
        or current_price is None
    ):

        return None

    if pd.isna(base_price):

        return None

    if float(base_price) == 0:

        return None

    return round(
        (
            float(current_price)
            /
            float(base_price)
            - 1
        )
        * 100,
        2
    )

# ==========================
# 追跡結果更新
# ==========================

def update_tracking_results(
        tracking_df,
        data_date=None):

    if tracking_df.empty:

        return tracking_df

    # ==========================
    # 実際の株価データ日
    # ==========================

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

    # ==========================
    # 未未来日の追跡データを除外
    # ==========================

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
            "未来日付の追跡データを除外 :",
            future_count,
            "件"
        )

        tracking_df = (
            tracking_df[
                ~future_mask
            ]
            .copy()
        )

    # ==========================
    # インデックス整理
    # ==========================

    tracking_df.reset_index(
        drop=True,
        inplace=True
    )

    # ==========================
    # 更新対象銘柄を収集
    # ==========================

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
            row["検出時株価"],
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
                f"{day}日後株価"
            )

            existing_price = pd.to_numeric(
                row[price_column],
                errors="coerce"
            )

            # 既に記録済み
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

    # ==========================
    # Yahoo一括取得
    # ==========================

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

    # ==========================
    # Yahooデータ検索関数
    # ==========================

    def find_price(
            history,
            target_date):

        if history is None:

            return None

        if history.empty:

            return None

        df = history.copy()

        # --------------------------
        # Date列をindexへ
        # --------------------------

        if "Date" in df.columns:

            df["Date"] = pd.to_datetime(
                df["Date"],
                errors="coerce"
            )

            df = df.dropna(
                subset=["Date"]
            )

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

        # --------------------------
        # timezone除去
        # --------------------------

        if getattr(
            df.index,
            "tz",
            None
        ) is not None:

            df.index = (
                df.index
                .tz_localize(None)
            )

        # --------------------------
        # 日付検索
        # --------------------------

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

        price = available.iloc[0].get(
            "Close"
        )

        if pd.isna(price):

            return None

        return float(price)

    # ==========================
    # 各銘柄を更新
    # ==========================

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
            row["検出時株価"],
            errors="coerce"
        )

        if pd.isna(base_price):

            continue

        # ==========================
        # Yahoo一括取得データ
        # ==========================

        history = yahoo_results.get(
            code
        )

        # ==========================
        # 1～10営業日後
        # ==========================

        for day in range(1, 11):

            target_date = add_business_days(
                detection_date,
                day
            )

            price_column = (
                f"{day}日後株価"
            )

            change_column = (
                f"{day}日後騰落率%"
            )

            # ----------------------
            # まだ対象日でない
            # ----------------------

            if market_date < target_date:

                continue

            # ----------------------
            # 既に記録済み
            # ----------------------

            existing_price = pd.to_numeric(
                row[price_column],
                errors="coerce"
            )

            if pd.notna(existing_price):

                continue

            # ----------------------
            # 一括取得データから検索
            # ----------------------

            price = find_price(
                history,
                target_date
            )

            # ----------------------
            # Yahoo batchに無かった場合
            # 既存方式でフォールバック
            # ----------------------

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

            # ----------------------
            # 株価保存
            # ----------------------

            tracking_df.at[
                index,
                price_column
            ] = round(
                price,
                2
            )

            # ----------------------
            # 騰落率
            # ----------------------

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

    # ==========================
    # 保存
    # ==========================

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


# ==========================
# 初動銘柄を記録
# ==========================

def record_initial_move(df):

    ensure_tracking_folder()

    tracking_df = load_tracking()

    # ==========================
    # 実際の株価データ日
    # ==========================

    if "_data_date" in df.columns:

        data_date = str(
            df["_data_date"].iloc[0]
        )

    else:

        data_date = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )

    # ==========================
    # まず過去銘柄を更新
    # ==========================

    tracking_df = (
        update_tracking_results(
            tracking_df,
            data_date
        )
    )

    
    # ==========================
    # 初動スコアTOP20抽出
    # ==========================

    if df.empty:

        print(
            "初動スコア対象銘柄なし"
        )

        return tracking_df

    # ==========================
    # 新規登録
    # ==========================

    new_rows = []

    for _, row in df.iterrows():

        code = str(
            row["コード"]
        )

        # ======================
        # 同じ銘柄を同じ日に
        # 二重登録しない
        # ======================

        already_exists = (
            (
                tracking_df[
                    "検出日"
                ].astype(str)
                == data_date
            )
            &
            (
                tracking_df[
                    "コード"
                ].astype(str)
                == code
            )
        ).any()

        if already_exists:

            continue

        new_row = {
            "検出日":
                data_date,

            "コード":
                code,

            "銘柄名":
                row["銘柄名"],

            "検出時株価":
                row["終値"],

            "強気度":
                row["強気度"],

            "初動スコア":
                row["初動スコア"],
        }

        # ======================
        # 1日後～10日後の
        # 空欄を作成
        # ======================

        for day in range(1, 11):

            new_row[
                f"{day}日後株価"
            ] = ""

            new_row[
                f"{day}日後騰落率%"
            ] = ""

        new_rows.append(
            new_row
        )

    # ==========================
    # 新規データ追加
    # ==========================

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

    # ==========================
    # 保存
    # ==========================

    tracking_df.to_csv(
        TRACKING_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(
        "初動銘柄追跡保存 :",
        TRACKING_FILE
    )

    print(
        "今回の追跡登録数 :",
        len(new_rows)
    )

    return tracking_df