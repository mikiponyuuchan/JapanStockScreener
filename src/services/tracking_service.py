import pandas as pd
from pathlib import Path
from datetime import datetime

from services.yahoo_service import get_history


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
    )

    return date + pd.offsets.BDay(
        days
    )


# ==========================
# 株価取得
# ==========================

def get_price_on_or_after(
        code,
        target_date):

    try:

        history = get_history(
            code
        )

    except Exception:

        return None

    if history is None:

        return None

    if history.empty:

        return None

    history = history.copy()

    # ==========================
    # 日付列がある場合
    # ==========================

    if "Date" in history.columns:

        history["Date"] = pd.to_datetime(
            history["Date"]
        )

        history = history.set_index(
            "Date"
        )

    else:

        history.index = pd.to_datetime(
            history.index
        )

    # ==========================
    # タイムゾーン除去
    # ==========================

    if getattr(
        history.index,
        "tz",
        None
    ) is not None:

        history.index = (
            history.index
            .tz_localize(None)
        )

    target_date = pd.Timestamp(
        target_date
    ).normalize()

    # ==========================
    # 対象日以降の最初の取引日
    # ==========================

    available = history[
        history.index.normalize()
        >= target_date
    ]

    if available.empty:

        return None

    price = available.iloc[0][
        "Close"
    ]

    if pd.isna(price):

        return None

    return float(price)


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
    # 未来日付の誤登録を除外
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

    updated_count = 0

    # ==========================
    # 各銘柄を追跡
    # ==========================

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
        # 1日後～10日後
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

            # ======================
            # まだ対象日になって
            # いなければスキップ
            # ======================

            if market_date < target_date:

                continue

            # ======================
            # すでに記録済みなら
            # スキップ
            # ======================

            existing_price = pd.to_numeric(
                row[price_column],
                errors="coerce"
            )

            if pd.notna(existing_price):

                continue

            # ======================
            # 株価取得
            # ======================

            price = get_price_on_or_after(
                code,
                target_date
            )

            if price is None:

                continue

            # ======================
            # 株価保存
            # ======================

            tracking_df.at[
                index,
                price_column
            ] = round(
                price,
                2
            )

            # ======================
            # 騰落率
            # ======================

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
    # 初動スコア上位を抽出
    # ==========================

    candidates = (
        df[
            df["初動スコア"].notna()
        ]
        .sort_values(
            "初動スコア",
            ascending=False
        )
        .head(20)
        .copy()
    )

    if candidates.empty:

        print(
            "初動スコア対象銘柄なし"
        )

        return tracking_df

    # ==========================
    # 新規登録
    # ==========================

    new_rows = []

    for _, row in candidates.iterrows():

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