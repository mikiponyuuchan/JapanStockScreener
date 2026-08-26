from pathlib import Path
import sys

import pandas as pd


# ============================================================
# パス設定
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from indicators.technical import add_indicators
from screener.analyzer import (
    calculate_initial_score,
    calculate_rsi_penalty,
)


RESULTS_DIR = ROOT_DIR / "results"
CACHE_DIR = ROOT_DIR / "data" / "cache"

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "historical_backtest_validation.csv"
)


# ============================================================
# 検証対象日
# ============================================================

TARGET_DATES = [
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
]


# ============================================================
# コード正規化
# ============================================================

def normalize_code(value):

    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


# ============================================================
# 真偽値正規化
# ============================================================

def normalize_bool(value):

    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "yes",
        "y",
    }


# ============================================================
# 数値変換
# ============================================================

def to_number(value):

    return pd.to_numeric(
        value,
        errors="coerce",
    )


# ============================================================
# 数値比較
# ============================================================

def numbers_equal(
    value1,
    value2,
    tolerance=0.01,
):

    a = to_number(value1)
    b = to_number(value2)

    if pd.isna(a) and pd.isna(b):
        return True

    if pd.isna(a) or pd.isna(b):
        return False

    return abs(
        float(a) - float(b)
    ) <= tolerance


# ============================================================
# キャッシュ読込
# ============================================================

def load_history(code):

    file_path = (
        CACHE_DIR
        / f"{code}.csv"
    )

    if not file_path.exists():
        return None

    try:

        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig",
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            file_path,
        )

    except Exception:
        return None

    if df.empty:
        return None

    # --------------------------------------------------------
    # Date列確認
    # --------------------------------------------------------

    if "Date" not in df.columns:
        return None

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
        utc=True,
    )

    df["Date"] = (
        df["Date"]
        .dt
        .tz_convert("Asia/Tokyo")
        .dt
        .tz_localize(None)
    )

    df = df[
        df["Date"].notna()
    ].copy()

    if df.empty:
        return None

    # --------------------------------------------------------
    # 必要列を数値化
    # --------------------------------------------------------

    numeric_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for col in numeric_columns:

        if col not in df.columns:
            return None

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    )

    if df.empty:
        return None

    df = (
        df
        .sort_values("Date")
        .drop_duplicates(
            subset=["Date"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return df


# ============================================================
# 対象日時点の指標再計算
# ============================================================

def calculate_historical_values(
    history,
    target_date,
):

    target_ts = pd.Timestamp(
        target_date
    )

    # --------------------------------------------------------
    # 対象日までで切る
    #
    # 未来データを絶対に使用しない
    # --------------------------------------------------------

    historical = history[
        history["Date"] <= target_ts
    ].copy()

    if historical.empty:
        return None

    # --------------------------------------------------------
    # 対象日のデータが存在するか
    # --------------------------------------------------------

    latest_date = (
        historical["Date"]
        .iloc[-1]
        .normalize()
    )

    if latest_date != target_ts.normalize():
        return None

    # --------------------------------------------------------
    # 本番と同じ指標関数を使用
    # --------------------------------------------------------

    try:

        calculated = add_indicators(
            historical
        )

    except Exception as e:

        return {
            "_error": str(e)
        }

    if calculated.empty:
        return None

    latest = calculated.iloc[-1]

    # --------------------------------------------------------
    # 本番と同じ初動スコア関数を使用
    # --------------------------------------------------------

    base_score = (
        calculate_initial_score(
            latest,
            None,
        )
    )

    rsi_penalty = (
        calculate_rsi_penalty(
            latest
        )
    )

    final_score = (
        base_score
        + rsi_penalty
    )

    return {
        "ChangePercent":
            latest.get(
                "ChangePercent",
                pd.NA,
            ),

        "VolumeRatio":
            latest.get(
                "VolumeRatio",
                pd.NA,
            ),

        "VolumeRatio20":
            latest.get(
                "VolumeRatio20",
                pd.NA,
            ),

        "BreakoutSignal":
            latest.get(
                "BreakoutSignal",
                False,
            ),

        "New30High":
            latest.get(
                "New30High",
                False,
            ),

        "RSI":
            latest.get(
                "RSI",
                pd.NA,
            ),

        "基本初動スコア":
            base_score,

        "RSI減点":
            rsi_penalty,

        "初動スコア":
            final_score,
    }


# ============================================================
# 保存済み本番結果読込
# ============================================================

def load_saved_result(
    target_date,
):

    file_path = (
        RESULTS_DIR
        / f"{target_date}_stock_result.csv"
    )

    if not file_path.exists():

        print(
            f"結果ファイルなし : "
            f"{file_path}"
        )

        return None

    try:

        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig",
            dtype={
                "コード": str,
            },
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            file_path,
            dtype={
                "コード": str,
            },
        )

    df["コード"] = (
        df["コード"]
        .map(normalize_code)
    )

    return df


# ============================================================
# 1日分検証
# ============================================================

def validate_date(
    target_date,
):

    saved = load_saved_result(
        target_date
    )

    if saved is None:
        return []

    print()
    print(
        "=" * 80
    )

    print(
        f"{target_date} 検証開始"
    )

    print(
        "=" * 80
    )

    rows = []

    total = len(saved)

    for i, (_, saved_row) in enumerate(
        saved.iterrows(),
        1,
    ):

        code = normalize_code(
            saved_row.get(
                "コード",
                "",
            )
        )

        if not code:
            continue

        history = load_history(
            code
        )

        if history is None:

            rows.append({
                "日付": target_date,
                "コード": code,
                "銘柄名":
                    saved_row.get(
                        "銘柄名",
                        "",
                    ),
                "判定": "履歴なし",
            })

            continue

        recalculated = (
            calculate_historical_values(
                history,
                target_date,
            )
        )

        if recalculated is None:

            rows.append({
                "日付": target_date,
                "コード": code,
                "銘柄名":
                    saved_row.get(
                        "銘柄名",
                        "",
                    ),
                "判定": "対象日なし",
            })

            continue

        if "_error" in recalculated:

            rows.append({
                "日付": target_date,
                "コード": code,
                "銘柄名":
                    saved_row.get(
                        "銘柄名",
                        "",
                    ),
                "判定": "計算エラー",
                "エラー":
                    recalculated[
                        "_error"
                    ],
            })

            continue

        # ----------------------------------------------------
        # 保存済み値
        # ----------------------------------------------------

        saved_change = (
            saved_row.get(
                "前日比",
                pd.NA,
            )
        )

        saved_volume = (
            saved_row.get(
                "VolumeRatio",
                pd.NA,
            )
        )

        saved_volume20 = (
            saved_row.get(
                "VolumeRatio20",
                pd.NA,
            )
        )

        saved_breakout = (
            normalize_bool(
                saved_row.get(
                    "BreakoutSignal",
                    False,
                )
            )
        )

        saved_new30 = (
            normalize_bool(
                saved_row.get(
                    "New30High",
                    False,
                )
            )
        )

        saved_rsi = (
            saved_row.get(
                "RSI",
                pd.NA,
            )
        )

        saved_base_score = (
            saved_row.get(
                "基本初動スコア",
                pd.NA,
            )
        )

        saved_penalty = (
            saved_row.get(
                "RSI減点",
                pd.NA,
            )
        )

        saved_final_score = (
            saved_row.get(
                "初動スコア",
                pd.NA,
            )
        )

        # ----------------------------------------------------
        # 一致判定
        # ----------------------------------------------------

        change_ok = numbers_equal(
            saved_change,
            recalculated[
                "ChangePercent"
            ],
        )

        volume_ok = numbers_equal(
            saved_volume,
            recalculated[
                "VolumeRatio"
            ],
        )

        volume20_ok = numbers_equal(
            saved_volume20,
            recalculated[
                "VolumeRatio20"
            ],
        )

        breakout_ok = (
            saved_breakout
            ==
            bool(
                recalculated[
                    "BreakoutSignal"
                ]
            )
        )

        new30_ok = (
            saved_new30
            ==
            bool(
                recalculated[
                    "New30High"
                ]
            )
        )

        rsi_ok = numbers_equal(
            saved_rsi,
            recalculated["RSI"],
        )

        base_score_ok = numbers_equal(
            saved_base_score,
            recalculated[
                "基本初動スコア"
            ],
            tolerance=0,
        )

        penalty_ok = numbers_equal(
            saved_penalty,
            recalculated[
                "RSI減点"
            ],
            tolerance=0,
        )

        final_score_ok = numbers_equal(
            saved_final_score,
            recalculated[
                "初動スコア"
            ],
            tolerance=0,
        )

        all_ok = all([
            change_ok,
            volume_ok,
            volume20_ok,
            breakout_ok,
            new30_ok,
            rsi_ok,
            base_score_ok,
            penalty_ok,
            final_score_ok,
        ])

        judgement = (
            "一致"
            if all_ok
            else "不一致"
        )

        # ----------------------------------------------------
        # 結果保存
        # ----------------------------------------------------

        rows.append({

            "日付":
                target_date,

            "コード":
                code,

            "銘柄名":
                saved_row.get(
                    "銘柄名",
                    "",
                ),

            "判定":
                judgement,

            # -----------------------------
            # 前日比
            # -----------------------------

            "保存_前日比":
                saved_change,

            "再計算_前日比":
                recalculated[
                    "ChangePercent"
                ],

            "前日比一致":
                change_ok,

            # -----------------------------
            # 出来高
            # -----------------------------

            "保存_VolumeRatio":
                saved_volume,

            "再計算_VolumeRatio":
                recalculated[
                    "VolumeRatio"
                ],

            "VolumeRatio一致":
                volume_ok,

            "保存_VolumeRatio20":
                saved_volume20,

            "再計算_VolumeRatio20":
                recalculated[
                    "VolumeRatio20"
                ],

            "VolumeRatio20一致":
                volume20_ok,

            # -----------------------------
            # ブレイク
            # -----------------------------

            "保存_BreakoutSignal":
                saved_breakout,

            "再計算_BreakoutSignal":
                bool(
                    recalculated[
                        "BreakoutSignal"
                    ]
                ),

            "BreakoutSignal一致":
                breakout_ok,

            # -----------------------------
            # 30日高値
            # -----------------------------

            "保存_New30High":
                saved_new30,

            "再計算_New30High":
                bool(
                    recalculated[
                        "New30High"
                    ]
                ),

            "New30High一致":
                new30_ok,

            # -----------------------------
            # RSI
            # -----------------------------

            "保存_RSI":
                saved_rsi,

            "再計算_RSI":
                recalculated["RSI"],

            "RSI一致":
                rsi_ok,

            # -----------------------------
            # 基本初動スコア
            # -----------------------------

            "保存_基本初動スコア":
                saved_base_score,

            "再計算_基本初動スコア":
                recalculated[
                    "基本初動スコア"
                ],

            "基本初動スコア一致":
                base_score_ok,

            # -----------------------------
            # RSI減点
            # -----------------------------

            "保存_RSI減点":
                saved_penalty,

            "再計算_RSI減点":
                recalculated[
                    "RSI減点"
                ],

            "RSI減点一致":
                penalty_ok,

            # -----------------------------
            # 最終初動スコア
            # -----------------------------

            "保存_初動スコア":
                saved_final_score,

            "再計算_初動スコア":
                recalculated[
                    "初動スコア"
                ],

            "初動スコア一致":
                final_score_ok,
        })

        if (
            i % 500 == 0
            or i == total
        ):

            print(
                f"進捗 : "
                f"{i} / {total}"
            )

    return rows


# ============================================================
# 集計表示
# ============================================================

def print_summary(result):

    print()
    print(
        "=" * 90
    )

    print(
        "過去日バックテスト再現性確認"
    )

    print(
        "=" * 90
    )

    if result.empty:

        print(
            "検証結果がありません。"
        )

        return

    for target_date in TARGET_DATES:

        day = result[
            result["日付"]
            ==
            target_date
        ]

        if day.empty:
            continue

        total = len(day)

        match_count = (
            day["判定"]
            .eq("一致")
            .sum()
        )

        mismatch_count = (
            day["判定"]
            .eq("不一致")
            .sum()
        )

        history_missing = (
            day["判定"]
            .eq("履歴なし")
            .sum()
        )

        date_missing = (
            day["判定"]
            .eq("対象日なし")
            .sum()
        )

        error_count = (
            day["判定"]
            .eq("計算エラー")
            .sum()
        )

        print()
        print(
            target_date
        )

        print(
            f"対象       : {total}"
        )

        print(
            f"完全一致   : {match_count}"
        )

        print(
            f"不一致     : {mismatch_count}"
        )

        print(
            f"履歴なし   : {history_missing}"
        )

        print(
            f"対象日なし : {date_missing}"
        )

        print(
            f"計算エラー : {error_count}"
        )

        valid_count = (
            match_count
            + mismatch_count
        )

        if valid_count > 0:

            match_rate = (
                match_count
                / valid_count
                * 100
            )

            print(
                "一致率     : "
                f"{match_rate:.2f}%"
            )

    # ========================================================
    # 項目別一致率
    # ========================================================

    valid = result[
        result["判定"]
        .isin([
            "一致",
            "不一致",
        ])
    ].copy()

    if valid.empty:
        return

    print()
    print(
        "=" * 90
    )

    print(
        "項目別一致率"
    )

    print(
        "=" * 90
    )

    check_columns = [
        "前日比一致",
        "VolumeRatio一致",
        "VolumeRatio20一致",
        "BreakoutSignal一致",
        "New30High一致",
        "RSI一致",
        "基本初動スコア一致",
        "RSI減点一致",
        "初動スコア一致",
    ]

    for col in check_columns:

        if col not in valid.columns:
            continue

        count = (
            valid[col]
            .fillna(False)
            .astype(bool)
            .sum()
        )

        rate = (
            count
            / len(valid)
            * 100
        )

        print(
            f"{col:<24} "
            f"{count:>6} / "
            f"{len(valid):<6} "
            f"{rate:>7.2f}%"
        )

    # ========================================================
    # スコア不一致例
    # ========================================================

    mismatch = valid[
        ~valid[
            "初動スコア一致"
        ]
        .fillna(False)
        .astype(bool)
    ].copy()

    print()
    print(
        "=" * 90
    )

    print(
        "初動スコア不一致例"
    )

    print(
        "=" * 90
    )

    if mismatch.empty:

        print(
            "初動スコアは全件一致しました。"
        )

    else:

        columns = [
            "日付",
            "コード",
            "銘柄名",
            "保存_初動スコア",
            "再計算_初動スコア",
            "保存_前日比",
            "再計算_前日比",
            "保存_VolumeRatio",
            "再計算_VolumeRatio",
            "保存_BreakoutSignal",
            "再計算_BreakoutSignal",
            "保存_New30High",
            "再計算_New30High",
            "保存_RSI",
            "再計算_RSI",
        ]

        columns = [
            col
            for col in columns
            if col in mismatch.columns
        ]

        print(
            mismatch[
                columns
            ]
            .head(30)
            .to_string(
                index=False
            )
        )


# ============================================================
# main
# ============================================================

def main():

    print(
        "=" * 90
    )

    print(
        "現行初動スコア 過去日再現テスト"
    )

    print(
        "=" * 90
    )

    print()
    print(
        "検証期間 : "
        f"{TARGET_DATES[0]}"
        " ～ "
        f"{TARGET_DATES[-1]}"
    )

    all_rows = []

    for target_date in TARGET_DATES:

        rows = validate_date(
            target_date
        )

        all_rows.extend(
            rows
        )

    result = pd.DataFrame(
        all_rows
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print_summary(
        result
    )

    print()
    print(
        "=" * 90
    )

    print(
        "保存 :",
        OUTPUT_FILE
    )

    print(
        "件数 :",
        len(result)
    )

    print(
        "=" * 90
    )


if __name__ == "__main__":
    main()