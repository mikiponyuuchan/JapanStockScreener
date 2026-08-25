import sys
import time
from itertools import combinations
from pathlib import Path

import pandas as pd


# ============================================================
# プロジェクトパス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ============================================================
# 設定
# ============================================================

TRACKING_DIR = ROOT_DIR / "data" / "tracking"

INPUT_FILE = (
    TRACKING_DIR
    / "initial_score_factor_raw.csv"
)

OUTPUT_FILE = (
    TRACKING_DIR
    / "initial_score_early_combination_analysis.csv"
)


# ------------------------------------------------------------
# 検証設定
# ------------------------------------------------------------

MIN_SAMPLES = 30

MAX_CONDITIONS = 4


# ============================================================
# 初動候補条件
#
# 「すでに大きく上昇している」ことを直接示す
# 5日・20日騰落率条件は意図的に除外する。
# ============================================================

CONDITIONS = {

    # --------------------------------------------------------
    # 出来高
    # --------------------------------------------------------

    "出来高1.5倍以上":
        lambda df:
            pd.to_numeric(
                df["VolumeRatio"],
                errors="coerce"
            ) >= 1.5,

    "出来高2倍以上":
        lambda df:
            pd.to_numeric(
                df["VolumeRatio"],
                errors="coerce"
            ) >= 2.0,

    "出来高3倍以上":
        lambda df:
            pd.to_numeric(
                df["VolumeRatio"],
                errors="coerce"
            ) >= 3.0,

    "出来高増加1日":
        lambda df:
            pd.to_numeric(
                df["VolumeIncreaseDays"],
                errors="coerce"
            ) >= 1,

    "出来高増加2日":
        lambda df:
            pd.to_numeric(
                df["VolumeIncreaseDays"],
                errors="coerce"
            ) >= 2,

    "出来高増加3日":
        lambda df:
            pd.to_numeric(
                df["VolumeIncreaseDays"],
                errors="coerce"
            ) >= 3,

    # --------------------------------------------------------
    # 当日の値動き
    # --------------------------------------------------------

    "前日比+1%以上":
        lambda df:
            pd.to_numeric(
                df["ChangePercent"],
                errors="coerce"
            ) >= 1.0,

    "前日比+3%以上":
        lambda df:
            pd.to_numeric(
                df["ChangePercent"],
                errors="coerce"
            ) >= 3.0,

    "前日比+5%以上":
        lambda df:
            pd.to_numeric(
                df["ChangePercent"],
                errors="coerce"
            ) >= 5.0,

    # --------------------------------------------------------
    # ブレイク
    # --------------------------------------------------------

    "ブレイク":
        lambda df:
            df["BreakoutSignal"]
            .fillna(False)
            .astype(bool),

    "ブレイク初日":
        lambda df:
            df["BreakoutFirstDay"]
            .fillna(False)
            .astype(bool),

    # --------------------------------------------------------
    # 高値更新
    # --------------------------------------------------------

    "30日高値更新":
        lambda df:
            df["New30High"]
            .fillna(False)
            .astype(bool),

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    "MACD GC":
        lambda df:
            df["MACD_GC"]
            .fillna(False)
            .astype(bool),

    # --------------------------------------------------------
    # 移動平均
    # --------------------------------------------------------

    "MA5上":
        lambda df:
            df["AboveMA5"]
            .fillna(False)
            .astype(bool),

    "MA25上":
        lambda df:
            df["AboveMA25"]
            .fillna(False)
            .astype(bool),

    "MA75上":
        lambda df:
            df["AboveMA75"]
            .fillna(False)
            .astype(bool),

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    "RSI70未満":
        lambda df:
            pd.to_numeric(
                df["RSI"],
                errors="coerce"
            ) < 70,

    "RSI80未満":
        lambda df:
            pd.to_numeric(
                df["RSI"],
                errors="coerce"
            ) < 80,

    "RSI90未満":
        lambda df:
            pd.to_numeric(
                df["RSI"],
                errors="coerce"
            ) < 90,
}


# ============================================================
# 条件評価
# ============================================================

def evaluate_condition(
    df,
    condition_name,
    condition_func
):

    try:

        mask = condition_func(df)

        return (
            pd.Series(
                mask,
                index=df.index
            )
            .fillna(False)
            .astype(bool)
        )

    except Exception as e:

        print(
            f"条件評価エラー: "
            f"{condition_name} / {e}"
        )

        return pd.Series(
            False,
            index=df.index
        )


# ============================================================
# 組み合わせ評価
# ============================================================

def evaluate_combination(
    df,
    condition_names,
    condition_masks
):

    mask = pd.Series(
        True,
        index=df.index
    )

    for condition_name in condition_names:

        mask &= condition_masks[
            condition_name
        ]

    return mask


# ============================================================
# 統計計算
# ============================================================

def calculate_statistics(
    group,
    condition_names
):

    n = len(group)

    if n < MIN_SAMPLES:
        return None

    max_return = pd.to_numeric(
        group[
            "5営業日以内最大騰落率"
        ],
        errors="coerce"
    ).dropna()

    if max_return.empty:
        return None

    plus5_rate = (
        max_return.ge(5)
        .mean()
        * 100
    )

    plus10_rate = (
        max_return.ge(10)
        .mean()
        * 100
    )

    plus20_rate = (
        max_return.ge(20)
        .mean()
        * 100
    )

    return {

        "条件数":
            len(condition_names),

        "条件":
            " + ".join(
                condition_names
            ),

        "n":
            n,

        "平均最大騰落率":
            max_return.mean(),

        "+5%率":
            plus5_rate,

        "+10%率":
            plus10_rate,

        "+20%率":
            plus20_rate,

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
        "=== 初動スコア・初動条件組み合わせ全銘柄検証 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"入力: {INPUT_FILE}"
    )

    print(
        f"最低サンプル数: {MIN_SAMPLES}"
    )

    print(
        f"最大条件数: {MAX_CONDITIONS}"
    )

    print(
        "※ 5日・20日騰落率条件は除外"
    )

    # --------------------------------------------------------
    # 入力
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"入力ファイルがありません: "
            f"{INPUT_FILE}"
        )

    print()
    print(
        f"入力ファイル読込: {INPUT_FILE}"
    )

    df = pd.read_csv(
        INPUT_FILE
    )

    print(
        f"検証記録数 : {len(df):,}"
    )

    if df.empty:

        raise RuntimeError(
            "入力データが空です。"
        )

    # --------------------------------------------------------
    # 必須列確認
    # --------------------------------------------------------

    required_columns = [

        "VolumeRatio",
        "VolumeIncreaseDays",

        "ChangePercent",

        "BreakoutSignal",
        "BreakoutFirstDay",

        "New30High",

        "MACD_GC",

        "AboveMA5",
        "AboveMA25",
        "AboveMA75",

        "RSI",

        "5営業日以内最大騰落率",
    ]

    missing_columns = [

        column
        for column in required_columns
        if column not in df.columns

    ]

    if missing_columns:

        raise ValueError(
            "必要列がありません: "
            + ", ".join(
                missing_columns
            )
        )

    # --------------------------------------------------------
    # 条件数
    # --------------------------------------------------------

    condition_names = list(
        CONDITIONS.keys()
    )

    print()
    print(
        f"利用可能な初動条件数: "
        f"{len(condition_names)}"
    )

    print()

    for i, name in enumerate(
        condition_names,
        start=1
    ):

        print(
            f"{i:2d}. {name}"
        )

    # --------------------------------------------------------
    # 条件マスク作成
    # --------------------------------------------------------

    print()
    print(
        "============================================================"
    )
    print(
        "=== 条件マスク作成 ==="
    )
    print(
        "============================================================"
    )

    condition_masks = {}

    for condition_name in condition_names:

        mask = evaluate_condition(
            df,
            condition_name,
            CONDITIONS[
                condition_name
            ]
        )

        condition_masks[
            condition_name
        ] = mask

        print(
            f"{condition_name:20s} "
            f"n={mask.sum():,}"
        )

    # --------------------------------------------------------
    # 組み合わせ総数
    # --------------------------------------------------------

    total_combinations = 0

    for count in range(
        2,
        MAX_CONDITIONS + 1
    ):

        total_combinations += (
            __import__("math")
            .comb(
                len(condition_names),
                count
            )
        )

    print()
    print(
        "============================================================"
    )
    print(
        "=== 組み合わせ検証開始 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"条件数 : {len(condition_names)}"
    )

    print(
        f"最大組み合わせ : "
        f"{MAX_CONDITIONS}条件"
    )

    print(
        f"検証組み合わせ総数 : "
        f"{total_combinations:,}"
    )

    # --------------------------------------------------------
    # 検証
    # --------------------------------------------------------

    results = []

    processed = 0

    process_start = time.time()

    for condition_count in range(
        2,
        MAX_CONDITIONS + 1
    ):

        print()
        print(
            f"--- {condition_count}条件組み合わせ ---"
        )

        count_start = time.time()

        for combination in combinations(
            condition_names,
            condition_count
        ):

            processed += 1

            mask = evaluate_combination(
                df,
                combination,
                condition_masks
            )

            n = int(
                mask.sum()
            )

            if n < MIN_SAMPLES:
                continue

            group = df.loc[
                mask
            ]

            statistics = (
                calculate_statistics(
                    group,
                    combination
                )
            )

            if statistics is None:
                continue

            results.append(
                statistics
            )

        elapsed = (
            time.time()
            - count_start
        )

        print(
            f"{condition_count}条件完了 "
            f"/ "
            f"有効 {len(results):,}件 "
            f"/ "
            f"{elapsed:.1f}秒"
        )

    # --------------------------------------------------------
    # DataFrame
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        results
    )

    if result_df.empty:

        raise RuntimeError(
            "有効な組み合わせがありません。"
        )

    # --------------------------------------------------------
    # 全体基準
    # --------------------------------------------------------

    all_max_return = pd.to_numeric(
        df[
            "5営業日以内最大騰落率"
        ],
        errors="coerce"
    ).dropna()

    baseline_plus10 = (
        all_max_return.ge(10)
        .mean()
        * 100
    )

    baseline_plus20 = (
        all_max_return.ge(20)
        .mean()
        * 100
    )

    result_df[
        "全体+10%率"
    ] = baseline_plus10

    result_df[
        "全体+20%率"
    ] = baseline_plus20

    result_df[
        "+10%率差"
    ] = (
        result_df["+10%率"]
        - baseline_plus10
    )

    result_df[
        "+20%率差"
    ] = (
        result_df["+20%率"]
        - baseline_plus20
    )

    # --------------------------------------------------------
    # 信頼度用の補助指標
    #
    # 少数サンプルを単純に上位にしないため、
    # n=100以上を優先して比較できるようにする。
    # --------------------------------------------------------

    result_df[
        "n100以上"
    ] = (
        result_df["n"]
        >= 100
    )

    # --------------------------------------------------------
    # 並び順
    # --------------------------------------------------------

    result_df = result_df.sort_values(
        [
            "+10%率",
            "+20%率",
            "平均最大騰落率",
            "n",
        ],
        ascending=[
            False,
            False,
            False,
            False,
        ]
    )

    result_df = result_df.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # CSV保存
    # --------------------------------------------------------

    TRACKING_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(
        f"分析結果保存: {OUTPUT_FILE}"
    )

    # ========================================================
    # 上位表示
    # ========================================================

    def print_top(
        title,
        sort_column,
        limit=30
    ):

        print()
        print(
            "============================================================"
        )

        print(
            title
        )

        print(
            "============================================================"
        )

        top = (
            result_df
            .sort_values(
                [
                    sort_column,
                    "+20%率",
                    "n",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ]
            )
            .head(limit)
        )

        for _, row in top.iterrows():

            print(
                f"n={int(row['n']):4d} / "
                f"+10%率={row['+10%率']:.1f}% / "
                f"差={row['+10%率差']:+.1f}pt / "
                f"+20%率={row['+20%率']:.1f}% / "
                f"平均最大={row['平均最大騰落率']:+.2f}% / "
                f"{row['条件']}"
            )

    # --------------------------------------------------------
    # 全件上位
    # --------------------------------------------------------

    print_top(
        "=== +10%率 上位組み合わせ ===",
        "+10%率"
    )

    # --------------------------------------------------------
    # n>=100
    # --------------------------------------------------------

    stable_df = result_df[
        result_df["n"]
        >= 100
    ]

    print()
    print(
        "============================================================"
    )

    print(
        "=== n>=100 安定性重視・+10%率上位 ==="
    )

    print(
        "============================================================"
    )

    if stable_df.empty:

        print(
            "n>=100の組み合わせはありません。"
        )

    else:

        top = (
            stable_df
            .sort_values(
                [
                    "+10%率",
                    "+20%率",
                    "平均最大騰落率",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ]
            )
            .head(30)
        )

        for _, row in top.iterrows():

            print(
                f"n={int(row['n']):4d} / "
                f"+10%率={row['+10%率']:.1f}% / "
                f"差={row['+10%率差']:+.1f}pt / "
                f"+20%率={row['+20%率']:.1f}% / "
                f"平均最大={row['平均最大騰落率']:+.2f}% / "
                f"{row['条件']}"
            )

    # --------------------------------------------------------
    # +20%率上位
    # --------------------------------------------------------

    print_top(
        "=== +20%率 上位組み合わせ ===",
        "+20%率"
    )

    # --------------------------------------------------------
    # 全体との差
    # --------------------------------------------------------

    print_top(
        "=== 全体との差（+10%率）上位 ===",
        "+10%率差"
    )

    # --------------------------------------------------------
    # 終了
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
        "=== 初動条件組み合わせ検証完了 ==="
    )

    print(
        "============================================================"
    )

    print(
        f"検証記録数 : {len(df):,}"
    )

    print(
        f"有効組み合わせ : "
        f"{len(result_df):,}"
    )

    print(
        f"全体+10%率 : "
        f"{baseline_plus10:.1f}%"
    )

    print(
        f"全体+20%率 : "
        f"{baseline_plus20:.1f}%"
    )

    print(
        f"保存先 : {OUTPUT_FILE}"
    )

    print(
        f"処理時間 : {total_time:.1f} 秒"
    )


if __name__ == "__main__":
    main()