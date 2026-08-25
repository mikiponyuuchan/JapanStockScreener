import pandas as pd
from pathlib import Path
from datetime import datetime

import holidays
import io
from contextlib import redirect_stdout

from services.yahoo_service import (
    get_history,
    _download_history_batch,
)


# ============================================================
# Initial Move Tracking Ver.2
#
# 目的
# ------------------------------------------------------------
# 初動スコアで検出した銘柄について、
# 検出後10営業日までの値動きを追跡する。
#
# 旧仕様の「強気度」は完全に廃止。
#
# 保存項目
# ------------------------------------------------------------
# 検出日
# コード
# 銘柄名
# 検出時株価
# 初動スコア
# 1～10営業日後株価
# 1～10営業日後騰落率
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
# 空の追跡DataFrame
# ============================================================

def empty_tracking_dataframe():

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "検出時株価",
        "初動スコア",
    ]

    for day in range(1, 11):

        columns.append(
            f"{day}日後株価"
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

    # 新仕様の列だけ残す
    df = df[
        list(required_columns)
    ]

    return df


# ============================================================
# 日本の営業日を計算
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
# Yahoo履歴から対象日の株価を取得
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
# 指定日の株価取得
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

        with redirect_stdout(io.StringIO()):
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
        "初動銘柄を追跡中..."
    )

    # --------------------------------------------------------
    # 将来日付のデータを削除
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
            "未来日付の追跡データを削除 :",
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
    # Yahoo取得対象コード
    # --------------------------------------------------------

    target_codes = set()

    for _, row in tracking_df.iterrows():

        try:

            detection_date = pd.Timestamp(
                row["検出日"]
            ).normalize()

        except Exception:

            continue

        code = str(
            row["コード"]
        )

        if not code or code == "nan":

            continue

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

            if market_date < target_date:

                continue

            price_column = (
                f"{day}日後株価"
            )

            existing_price = pd.to_numeric(
                row[price_column],
                errors="coerce"
            )

            if pd.notna(existing_price):

                continue

            target_codes.add(
                code
            )

    target_codes = sorted(
        target_codes
    )


    # --------------------------------------------------------
    # Yahoo一括取得
    # --------------------------------------------------------

    yahoo_results = {}

    if target_codes:

        try:

            with redirect_stdout(io.StringIO()):
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
    # 各銘柄を更新
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
            row["検出時株価"],
            errors="coerce"
        )

        if pd.isna(base_price):

            continue

        history = yahoo_results.get(
            code
        )

        row_updated = False

        for day in range(1, 11):

            target_date = add_business_days(
                detection_date,
                day
            )

            price_column = (
                f"{day}日後株価"
            )

            change_column = (
                f"{day}日後騰落率"
            )

            # まだ対象営業日になっていない
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
            # 株価保存
            # ------------------------------------------------

            tracking_df.at[
                index,
                price_column
            ] = round(
                price,
                2
            )

            # ------------------------------------------------
            # 騰落率保存
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

            row_updated = True

        if row_updated:

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

    print(
        "初動追跡データ保存 :",
        TRACKING_FILE
    )

    return tracking_df


# ============================================================
# 初動銘柄を新規記録
# ============================================================

def record_initial_move(df):

    ensure_tracking_folder()

    tracking_df = load_tracking()

    # --------------------------------------------------------
    # データ日付
    # --------------------------------------------------------

    if "_data_date" in df.columns:

        data_date = str(
            df["_data_date"].iloc[0]
        )

    else:

        data_date = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )

    try:

        data_date = pd.Timestamp(
            data_date
        ).strftime("%Y-%m-%d")

    except Exception:

        data_date = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )

    # --------------------------------------------------------
    # 初動スコア列確認
    # --------------------------------------------------------

    if "初動スコア" not in df.columns:

        print(
            "初動追跡SKIP : 初動スコア列がありません"
        )

        return tracking_df

    # --------------------------------------------------------
    # TOP20を対象
    #
    # runner.pyから渡されたdfが既にTOP20なら
    # そのまま利用する。
    #
    # 全銘柄の場合は初動スコア順にTOP20を取得。
    # --------------------------------------------------------

    work_df = df.copy()

    try:

        work_df["初動スコア"] = pd.to_numeric(
            work_df["初動スコア"],
            errors="coerce"
        )

        work_df = (
            work_df
            .dropna(
                subset=["初動スコア"]
            )
            .sort_values(
                "初動スコア",
                ascending=False
            )
            .head(20)
        )

    except Exception:

        return tracking_df

    new_rows = []

    # --------------------------------------------------------
    # 新規記録
    # --------------------------------------------------------

    for _, row in work_df.iterrows():

        # ----------------------------------------------------
        # コード
        # ----------------------------------------------------

        code = ""

        for code_column in [
            "コード",
            "Code",
            "code"
        ]:

            if code_column not in row.index:

                continue

            value = row[code_column]

            if pd.notna(value):

                code = str(value)

                if code.endswith(".0"):

                    code = code[:-2]

                break

        if not code or code == "nan":

            continue

        # ----------------------------------------------------
        # 銘柄名
        # ----------------------------------------------------

        name = ""

        for name_column in [
            "銘柄名",
            "Name",
            "name"
        ]:

            if name_column not in row.index:

                continue

            value = row[name_column]

            if pd.notna(value):

                name = str(value)

                break

        # ----------------------------------------------------
        # 検出時株価
        # ----------------------------------------------------

        base_price = None

        for price_column in [
            "終値",
            "Close",
            "株価"
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

        if base_price is None:

            continue

        # ----------------------------------------------------
        # 初動スコア
        # ----------------------------------------------------

        initial_score = pd.to_numeric(
            row["初動スコア"],
            errors="coerce"
        )

        if pd.isna(initial_score):

            continue

        initial_score = int(
            initial_score
        )

        # ----------------------------------------------------
        # 同一日・同一銘柄チェック
        # ----------------------------------------------------

        if not tracking_df.empty:

            existing_date = (
                tracking_df["検出日"]
                .astype(str)
                .str[:10]
            )

            existing_code = (
                tracking_df["コード"]
                .astype(str)
                .str.replace(
                    ".0",
                    "",
                    regex=False
                )
            )

            already_exists = (
                (
                    existing_date
                    ==
                    data_date
                )
                &
                (
                    existing_code
                    ==
                    code
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

            "検出時株価":
                round(
                    base_price,
                    2
                ),

            "初動スコア":
                initial_score,
        }

        for day in range(1, 11):

            new_row[
                f"{day}日後株価"
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
        "今回の新規記録件数 :",
        len(new_rows)
    )

    return tracking_df