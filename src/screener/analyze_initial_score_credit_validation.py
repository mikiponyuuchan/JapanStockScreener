from pathlib import Path

import pandas as pd


# ============================================================
# 設定
# ============================================================

INPUT_FILE = Path(
    "data/tracking/initial_score_factor_raw.csv"
)

CREDIT_DIR = Path(
    "data/yahoo_credit"
)

OUTPUT_FILE = Path(
    "data/tracking/initial_score_credit_validation.csv"
)


# ============================================================
# 初動スコア
# ============================================================

def calculate_initial_score(row):
    """
    現在の初動スコア

    前日比 +5%以上 : +3
    出来高 3倍以上 : +2
    ブレイク       : +1
    30日高値更新   : +1

    RSI減点
    85～89.99 : -1
    90～94.99 : -2
    95以上    : -3
    """

    score = 0

    if row["ChangePercent"] >= 5.0:
        score += 3

    if row["VolumeRatio"] >= 3.0:
        score += 2

    if row["BreakoutSignal"]:
        score += 1

    if row["New30High"]:
        score += 1

    rsi = row["RSI"]

    if pd.notna(rsi):
        if 85 <= rsi < 90:
            score -= 1
        elif 90 <= rsi < 95:
            score -= 2
        elif rsi >= 95:
            score -= 3

    return score


# ============================================================
# bool変換
# ============================================================

def to_bool(value):
    if isinstance(value, bool):
        return value

    if pd.isna(value):
        return False

    return str(value).strip().lower() in (
        "true",
        "1",
        "yes",
        "y",
    )


# ============================================================
# 信用CSV読み込み
# ============================================================

def load_credit_data():
    files = sorted(CREDIT_DIR.glob("*.csv"))

    if not files:
        raise FileNotFoundError(
            f"信用CSVがありません: {CREDIT_DIR}"
        )

    frames = []

    for file in files:
        try:
            df = pd.read_csv(file)
        except Exception as e:
            print(f"読み込み失敗: {file} / {e}")
            continue

        required = {
            "コード",
            "日付",
            "売残",
            "買残",
            "売残増減",
            "買残増減",
            "信用倍率",
        }

        if not required.issubset(df.columns):
            print(f"必要列不足: {file}")
            continue

        frames.append(
            df[
                [
                    "コード",
                    "日付",
                    "売残",
                    "買残",
                    "売残増減",
                    "買残増減",
                    "信用倍率",
                ]
            ].copy()
        )

    if not frames:
        raise RuntimeError(
            "有効な信用CSVがありません。"
        )

    credit = pd.concat(
        frames,
        ignore_index=True
    )

    credit["コード"] = (
        credit["コード"]
        .astype(str)
        .str.strip()
    )

    credit["日付"] = pd.to_datetime(
        credit["日付"],
        errors="coerce"
    )

    numeric_cols = [
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    for col in numeric_cols:
        credit[col] = pd.to_numeric(
            credit[col],
            errors="coerce"
        )

    credit = credit.dropna(
        subset=["コード", "日付"]
    )

    credit = credit.drop_duplicates(
        subset=["コード", "日付"],
        keep="last"
    )

    credit = credit.sort_values(
        ["コード", "日付"]
    )

    return credit


# ============================================================
# 信用情報を「検出日時点で利用可能な最新情報」で結合
# ============================================================

def merge_latest_credit(raw, credit):
    """
    検出日以前で、利用可能だった最新の信用情報を結合する。

    重要:
    - コードが一致
    - 信用情報の日付 <= 検出日
    - その中で最も新しい信用情報を採用
    - 検出日より後の信用情報は絶対に使用しない
    """

    raw = raw.copy()
    credit = credit.copy()

    raw["コード"] = (
        raw["コード"]
        .astype(str)
        .str.strip()
    )

    credit["コード"] = (
        credit["コード"]
        .astype(str)
        .str.strip()
    )

    raw["検出日"] = pd.to_datetime(
        raw["検出日"],
        errors="coerce"
    )

    credit["日付"] = pd.to_datetime(
        credit["日付"],
        errors="coerce"
    )

    raw = raw.dropna(
        subset=["コード", "検出日"]
    )

    credit = credit.dropna(
        subset=["コード", "日付"]
    )

    # --------------------------------------------------------
    # 信用情報をコード・日付順に整理
    # --------------------------------------------------------

    credit = credit.sort_values(
        ["コード", "日付"]
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # 検出データを元の順番で保持
    # --------------------------------------------------------

    raw["_original_index"] = range(
        len(raw)
    )

    # --------------------------------------------------------
    # コードごとに処理
    # --------------------------------------------------------

    merged_parts = []

    credit_groups = {
        code: group
        for code, group
        in credit.groupby("コード")
    }

    for code, group in raw.groupby(
        "コード",
        sort=False
    ):

        target = group.copy()

        credit_group = credit_groups.get(
            code
        )

        if credit_group is None:
            # 信用情報なし
            for col in [
                "日付",
                "売残",
                "買残",
                "売残増減",
                "買残増減",
                "信用倍率",
            ]:
                target[col] = pd.NA

            merged_parts.append(target)
            continue

        credit_group = credit_group.sort_values(
            "日付"
        )

        # ----------------------------------------------------
        # searchsortedで
        # 「検出日以下の最新日」を取得
        # ----------------------------------------------------

        credit_dates = (
            credit_group["日付"]
            .values
        )

        positions = credit_dates.searchsorted(
            target["検出日"].values,
            side="right"
        ) - 1

        # 信用情報を持つ行
        valid = positions >= 0

        # 結合用列を初期化
        for col in [
            "日付",
            "売残",
            "買残",
            "売残増減",
            "買残増減",
            "信用倍率",
        ]:
            target[col] = pd.NA

        if valid.any():

            valid_target = target.loc[
                valid
            ].copy()

            valid_positions = positions[
                valid
            ]

            selected = credit_group.iloc[
                valid_positions
            ]

            for col in [
                "日付",
                "売残",
                "買残",
                "売残増減",
                "買残増減",
                "信用倍率",
            ]:
                target.loc[
                    valid_target.index,
                    col
                ] = selected[
                    col
                ].to_numpy()

        merged_parts.append(
            target
        )

    # --------------------------------------------------------
    # 結合結果
    # --------------------------------------------------------

    merged = pd.concat(
        merged_parts,
        ignore_index=True
    )

    # 元の順番に戻す
    merged = merged.sort_values(
        "_original_index"
    ).drop(
        columns="_original_index"
    )

    merged = merged.reset_index(
        drop=True
    )

    return merged


# ============================================================
# 信用条件
# ============================================================

def add_credit_conditions(df):

    df["信用倍率<1"] = (
        df["信用倍率"] < 1.0
    )

    df["売残増加"] = (
        df["売残増減"] > 0
    )

    df["信用倍率<1_かつ_売残増加"] = (
        df["信用倍率<1"]
        & df["売残増加"]
    )

    df["信用情報あり"] = (
        df["日付"].notna()
    )

    return df


# ============================================================
# 検証
# ============================================================

def calc_result(df):

    if len(df) == 0:
        return {
            "件数": 0,
            "5日Hit率": 0.0,
            "10日Hit率": 0.0,
            "20日Hit率": 0.0,
            "平均最大騰落率": 0.0,
            "中央値最大騰落率": 0.0,
        }

    return {
        "件数": len(df),

        "5日Hit率": round(
            df["Hit5"].mean() * 100,
            2
        ),

        "10日Hit率": round(
            df["Hit10"].mean() * 100,
            2
        ),

        "20日Hit率": round(
            df["Hit20"].mean() * 100,
            2
        ),

        "平均最大騰落率": round(
            df["5営業日以内最大騰落率"].mean(),
            2
        ),

        "中央値最大騰落率": round(
            df["5営業日以内最大騰落率"].median(),
            2
        ),
    }


# ============================================================
# メイン
# ============================================================

def main():

    print("=" * 70)
    print("初動スコア × 信用情報 検証")
    print("=" * 70)

    print()
    print(f"入力 : {INPUT_FILE}")
    print(f"信用 : {CREDIT_DIR}")

    # --------------------------------------------------------
    # 初動データ
    # --------------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE
    )

    print(
        f"初動データ件数 : {len(df):,}"
    )

    # bool変換
    for col in [
        "BreakoutSignal",
        "BreakoutFirstDay",
        "New30High",
        "NewYearHigh",
        "MACD_GC",
        "AboveMA5",
        "AboveMA25",
        "AboveMA75",
        "Hit5",
        "Hit10",
        "Hit20",
    ]:
        if col in df.columns:
            df[col] = df[col].apply(to_bool)

    # 数値変換
    numeric_cols = [
        "VolumeRatio",
        "ChangePercent",
        "RSI",
        "5営業日以内最大騰落率",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # --------------------------------------------------------
    # 初動スコア計算
    # --------------------------------------------------------

    df["初動スコア"] = df.apply(
        calculate_initial_score,
        axis=1
    )

    # --------------------------------------------------------
    # 信用情報読み込み
    # --------------------------------------------------------

    credit = load_credit_data()

    print(
        f"信用データ件数 : {len(credit):,}"
    )

    # --------------------------------------------------------
    # 最新信用情報を結合
    # --------------------------------------------------------

    df = merge_latest_credit(
        df,
        credit
    )

    df = add_credit_conditions(
        df
    )

    credit_count = (
        df["信用情報あり"]
        .sum()
    )

    print(
        f"信用情報取得件数 : {credit_count:,}"
    )

    print(
        f"信用情報なし     : "
        f"{len(df) - credit_count:,}"
    )


    # --------------------------------------------------------
    # 初動スコア × 信用条件 クロス集計
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("【初動スコア × 信用条件 クロス集計】")
    print("=" * 70)

    cross_rows = []

    for score in range(-3, 8):

        all_df = df[
            df["初動スコア"] == score
        ]

        credit_df = all_df[
            all_df["信用倍率<1"]
        ]

        sell_df = all_df[
            all_df["売残増加"]
        ]

        both_df = all_df[
            all_df["信用倍率<1_かつ_売残増加"]
        ]

        cross_rows.append(
            {
                "初動スコア": score,
                "全件": len(all_df),
                "信用倍率<1": len(credit_df),
                "売残増加": len(sell_df),
                "両方": len(both_df),
            }
        )

    cross_df = pd.DataFrame(
        cross_rows
    )

    print(
        cross_df.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # 検証条件
    # --------------------------------------------------------

    conditions = [

        (
            "全件",
            df
        ),

        (
            "信用倍率<1",
            df[
                df["信用倍率<1"]
            ]
        ),

        (
            "売残増加",
            df[
                df["売残増加"]
            ]
        ),

        (
            "信用倍率<1_かつ_売残増加",
            df[
                df["信用倍率<1_かつ_売残増加"]
            ]
        ),
    ]

    results = []

    # --------------------------------------------------------
    # スコア × 信用条件
    # --------------------------------------------------------

    for condition_name, condition_df in conditions:

        for score in range(-3, 8):

            target = condition_df[
                condition_df["初動スコア"] == score
            ]

            result = calc_result(
                target
            )

            result["信用条件"] = condition_name
            result["スコア条件"] = (
                f"{score}点"
            )

            results.append(
                result
            )

        # ----------------------------------------------------
        # スコア閾値
        # ----------------------------------------------------

        for score in range(0, 8):

            target = condition_df[
                condition_df["初動スコア"] >= score
            ]

            result = calc_result(
                target
            )

            result["信用条件"] = condition_name
            result["スコア条件"] = (
                f"{score}点以上"
            )

            results.append(
                result
            )

    result_df = pd.DataFrame(
        results
    )

    # 列順
    result_df = result_df[
        [
            "信用条件",
            "スコア条件",
            "件数",
            "5日Hit率",
            "10日Hit率",
            "20日Hit率",
            "平均最大騰落率",
            "中央値最大騰落率",
        ]
    ]

    # --------------------------------------------------------
    # 表示
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("【初動スコア × 信用条件】")
    print("=" * 70)

    print(
        result_df.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 70)
    print("保存完了")
    print("=" * 70)
    print(
        f"結果 : {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()