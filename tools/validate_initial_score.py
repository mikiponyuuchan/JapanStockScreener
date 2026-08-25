from pathlib import Path

import pandas as pd


# ============================================================
# 設定
# ============================================================

INPUT_FILE = Path(
    "data/tracking/initial_score_factor_raw.csv"
)

OUTPUT_SCORE = Path(
    "data/tracking/initial_score_validation_by_score.csv"
)

OUTPUT_THRESHOLD = Path(
    "data/tracking/initial_score_validation_by_threshold.csv"
)


# ============================================================
# 初動スコア計算
# 現在の正式仕様
# ============================================================

def calculate_initial_score(row):
    score = 0

    # ----------------------------------------
    # 前日比
    # ----------------------------------------
    try:
        change = float(row["ChangePercent"])

        if change >= 5.0:
            score += 3

    except Exception:
        pass

    # ----------------------------------------
    # 出来高
    # ----------------------------------------
    try:
        volume_ratio = float(row["VolumeRatio"])

        if volume_ratio >= 3.0:
            score += 2

    except Exception:
        pass

    # ----------------------------------------
    # ブレイク
    # ----------------------------------------
    if row["BreakoutSignal"] is True:
        score += 1

    # ----------------------------------------
    # 30日高値更新
    # ----------------------------------------
    if row["New30High"] is True:
        score += 1

    # ----------------------------------------
    # RSI減点
    # ----------------------------------------
    try:
        rsi = float(row["RSI"])

        if rsi >= 95.0:
            score -= 3

        elif rsi >= 90.0:
            score -= 2

        elif rsi >= 85.0:
            score -= 1

    except Exception:
        pass

    return score


# ============================================================
# bool変換
# ============================================================

def to_bool(value):
    if isinstance(value, bool):
        return value

    if pd.isna(value):
        return False

    text = str(value).strip().lower()

    return text in (
        "true",
        "1",
        "yes",
        "y",
        "t",
    )


# ============================================================
# メイン
# ============================================================

def main():

    print("=" * 70)
    print("初動スコア検証")
    print("=" * 70)

    print()
    print(f"入力 : {INPUT_FILE}")

    if not INPUT_FILE.exists():
        print()
        print("ERROR: 入力ファイルがありません")
        return

    # ----------------------------------------
    # 読み込み
    # ----------------------------------------

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    print(f"総件数 : {len(df):,}")

    # ----------------------------------------
    # 型変換
    # ----------------------------------------

    df["検出日"] = pd.to_datetime(
        df["検出日"],
        errors="coerce"
    )

    for col in [
        "VolumeRatio",
        "ChangePercent",
        "RSI",
        "5営業日以内最大騰落率",
    ]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    for col in [
        "BreakoutSignal",
        "BreakoutFirstDay",
        "New30High",
        "Hit5",
        "Hit10",
        "Hit20",
    ]:
        df[col] = df[col].apply(to_bool)

    # ----------------------------------------
    # 初動スコア計算
    # ----------------------------------------

    df["検証初動スコア"] = df.apply(
        calculate_initial_score,
        axis=1
    )

    # ----------------------------------------
    # スコア別集計
    # ----------------------------------------

    score_rows = []

    for score in sorted(
        df["検証初動スコア"].dropna().unique()
    ):

        sub = df[
            df["検証初動スコア"] == score
        ].copy()

        count = len(sub)

        if count == 0:
            continue

        hit5_rate = (
            sub["Hit5"].mean() * 100
        )

        hit10_rate = (
            sub["Hit10"].mean() * 100
        )

        hit20_rate = (
            sub["Hit20"].mean() * 100
        )

        avg_max_return = (
            sub["5営業日以内最大騰落率"]
            .mean()
        )

        median_max_return = (
            sub["5営業日以内最大騰落率"]
            .median()
        )

        score_rows.append({
            "初動スコア": int(score),
            "件数": count,
            "5日Hit率": round(
                hit5_rate,
                2
            ),
            "10日Hit率": round(
                hit10_rate,
                2
            ),
            "20日Hit率": round(
                hit20_rate,
                2
            ),
            "平均最大騰落率": round(
                avg_max_return,
                2
            ),
            "中央値最大騰落率": round(
                median_max_return,
                2
            ),
        })

    score_result = pd.DataFrame(
        score_rows
    )

    # ----------------------------------------
    # スコア閾値別
    # ----------------------------------------

    threshold_rows = []

    for threshold in range(0, 8):

        sub = df[
            df["検証初動スコア"] >= threshold
        ].copy()

        count = len(sub)

        if count == 0:
            continue

        threshold_rows.append({
            "スコア条件":
                f"{threshold}点以上",

            "件数":
                count,

            "5日Hit率":
                round(
                    sub["Hit5"].mean() * 100,
                    2
                ),

            "10日Hit率":
                round(
                    sub["Hit10"].mean() * 100,
                    2
                ),

            "20日Hit率":
                round(
                    sub["Hit20"].mean() * 100,
                    2
                ),

            "平均最大騰落率":
                round(
                    sub[
                        "5営業日以内最大騰落率"
                    ].mean(),
                    2
                ),

            "中央値最大騰落率":
                round(
                    sub[
                        "5営業日以内最大騰落率"
                    ].median(),
                    2
                ),
        })

    threshold_result = pd.DataFrame(
        threshold_rows
    )

    # ----------------------------------------
    # 保存
    # ----------------------------------------

    score_result.to_csv(
        OUTPUT_SCORE,
        index=False,
        encoding="utf-8-sig"
    )

    threshold_result.to_csv(
        OUTPUT_THRESHOLD,
        index=False,
        encoding="utf-8-sig"
    )

    # ----------------------------------------
    # 表示
    # ----------------------------------------

    print()
    print("=" * 70)
    print("【スコア別】")
    print("=" * 70)

    print(
        score_result.to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("【スコア閾値別】")
    print("=" * 70)

    print(
        threshold_result.to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("保存完了")
    print("=" * 70)

    print(
        f"スコア別   : {OUTPUT_SCORE}"
    )

    print(
        f"閾値別     : {OUTPUT_THRESHOLD}"
    )


if __name__ == "__main__":
    main()