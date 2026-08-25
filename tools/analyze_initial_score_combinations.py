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

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "initial_score_factor_raw.csv"
)

OUTPUT_DIR = (
    ROOT_DIR
    / "data"
    / "tracking"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "initial_score_combination_analysis.csv"
)


# 最低サンプル数
MIN_SAMPLE_SIZE = 30


# 調べる組み合わせ数
MAX_COMBINATION_SIZE = 4


# ============================================================
# 条件定義
# ============================================================

CONDITIONS = {

    # --------------------------------------------------------
    # 出来高
    # --------------------------------------------------------

    "出来高1.5倍以上": lambda df: (
        pd.to_numeric(
            df["VolumeRatio"],
            errors="coerce"
        ) >= 1.5
    ),

    "出来高2倍以上": lambda df: (
        pd.to_numeric(
            df["VolumeRatio"],
            errors="coerce"
        ) >= 2.0
    ),

    "出来高3倍以上": lambda df: (
        pd.to_numeric(
            df["VolumeRatio"],
            errors="coerce"
        ) >= 3.0
    ),

    "出来高増加1日": lambda df: (
        pd.to_numeric(
            df["VolumeIncreaseDays"],
            errors="coerce"
        ) == 1
    ),

    "出来高増加2日": lambda df: (
        pd.to_numeric(
            df["VolumeIncreaseDays"],
            errors="coerce"
        ) == 2
    ),

    "出来高増加3日": lambda df: (
        pd.to_numeric(
            df["VolumeIncreaseDays"],
            errors="coerce"
        ) == 3
    ),

    # --------------------------------------------------------
    # 前日比
    # --------------------------------------------------------

    "前日比+1%以上": lambda df: (
        pd.to_numeric(
            df["ChangePercent"],
            errors="coerce"
        ) >= 1.0
    ),

    "前日比+3%以上": lambda df: (
        pd.to_numeric(
            df["ChangePercent"],
            errors="coerce"
        ) >= 3.0
    ),

    "前日比+5%以上": lambda df: (
        pd.to_numeric(
            df["ChangePercent"],
            errors="coerce"
        ) >= 5.0
    ),

    # --------------------------------------------------------
    # 5日騰落率
    #
    # 「上がりすぎ」を除外するのではなく、
    # すでに上昇している銘柄を条件として評価する。
    # --------------------------------------------------------

    "5日騰落率+5%以上": lambda df: (
        pd.to_numeric(
            df["Change5Days"],
            errors="coerce"
        ) >= 5.0
    ),

    "5日騰落率+10%以上": lambda df: (
        pd.to_numeric(
            df["Change5Days"],
            errors="coerce"
        ) >= 10.0
    ),

    "5日騰落率+20%以上": lambda df: (
        pd.to_numeric(
            df["Change5Days"],
            errors="coerce"
        ) >= 20.0
    ),

    # --------------------------------------------------------
    # 20日騰落率
    # --------------------------------------------------------

    "20日騰落率+10%以上": lambda df: (
        pd.to_numeric(
            df["Change20Days"],
            errors="coerce"
        ) >= 10.0
    ),

    "20日騰落率+20%以上": lambda df: (
        pd.to_numeric(
            df["Change20Days"],
            errors="coerce"
        ) >= 20.0
    ),

    # --------------------------------------------------------
    # テクニカルイベント
    # --------------------------------------------------------

    "ブレイク": lambda df: (
        df["BreakoutSignal"]
        .fillna(False)
        .astype(bool)
    ),

    "ブレイク初日": lambda df: (
        df["BreakoutFirstDay"]
        .fillna(False)
        .astype(bool)
    ),

    "30日高値更新": lambda df: (
        df["New30High"]
        .fillna(False)
        .astype(bool)
    ),

    "MACD GC": lambda df: (
        df["MACD_GC"]
        .fillna(False)
        .astype(bool)
    ),

    # --------------------------------------------------------
    # MA
    # --------------------------------------------------------

    "MA5上": lambda df: (
        df["AboveMA5"]
        .fillna(False)
        .astype(bool)
    ),

    "MA25上": lambda df: (
        df["AboveMA25"]
        .fillna(False)
        .astype(bool)
    ),

    "MA75上": lambda df: (
        df["AboveMA75"]
        .fillna(False)
        .astype(bool)
    ),

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    "RSI70未満": lambda df: (
        pd.to_numeric(
            df["RSI"],
            errors="coerce"
        ) < 70
    ),

    "RSI80未満": lambda df: (
        pd.to_numeric(
            df["RSI"],
            errors="coerce"
        ) < 80
    ),

    "RSI90未満": lambda df: (
        pd.to_numeric(
            df["RSI"],
            errors="coerce"
        ) < 90
    ),
}


# ============================================================
# データ読み込み
# ============================================================

def load_data():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"入力ファイルがありません: {INPUT_FILE}"
        )

    print(
        f"入力ファイル読込: {INPUT_FILE}"
    )

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    if df.empty:

        raise RuntimeError(
            "入力データが空です。"
        )

    print(
        f"検証記録数 : {len(df):,}"
    )

    return df


# ============================================================
# 条件マスク作成
# ============================================================

def build_condition_masks(df):

    masks = {}

    for name, condition_func in CONDITIONS.items():

        try:

            mask = condition_func(
                df
            )

            mask = (
                pd.Series(
                    mask,
                    index=df.index
                )
                .fillna(False)
                .astype(bool)
            )

            masks[name] = mask

        except Exception as e:

            print(
                f"条件作成エラー: "
                f"{name} / {e}"
            )

    return masks


# ============================================================
# 条件適用
# ============================================================

def apply_conditions(
    df,
    masks,
    condition_names
):

    mask = pd.Series(
        True,
        index=df.index
    )

    for name in condition_names:

        mask &= masks[name]

    return df.loc[
        mask
    ]


# ============================================================
# 数値列
# ============================================================

def prepare_numeric_columns(df):

    df = df.copy()

    df["5営業日以内最大騰落率"] = pd.to_numeric(
        df["5営業日以内最大騰落率"],
        errors="coerce"
    )

    return df


# ============================================================
# 統計計算
# ============================================================

def calculate_statistics(
    group,
    total_df
):

    max_return = pd.to_numeric(
        group[
            "5営業日以内最大騰落率"
        ],
        errors="coerce"
    ).dropna()

    if max_return.empty:

        return None

    total_max_return = pd.to_numeric(
        total_df[
            "5営業日以内最大騰落率"
        ],
        errors="coerce"
    ).dropna()

    sample_size = len(
        max_return
    )

    average = (
        max_return.mean()
    )

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

    baseline_plus10 = (
        total_max_return.ge(10)
        .mean()
        * 100
    )

    baseline_plus5 = (
        total_max_return.ge(5)
        .mean()
        * 100
    )

    baseline_plus20 = (
        total_max_return.ge(20)
        .mean()
        * 100
    )

    return {

        "n":
            sample_size,

        "平均最大騰落率":
            average,

        "+5%率":
            plus5_rate,

        "+10%率":
            plus10_rate,

        "+20%率":
            plus20_rate,

        "全体+5%率":
            baseline_plus5,

        "全体+10%率":
            baseline_plus10,

        "全体+20%率":
            baseline_plus20,

        "+5%率差":
            plus5_rate
            - baseline_plus5,

        "+10%率差":
            plus10_rate
            - baseline_plus10,

        "+20%率差":
            plus20_rate
            - baseline_plus20,

        "最大騰落率":
            max_return.max(),
    }


# ============================================================
# 組み合わせ検証
# ============================================================

def analyze_combinations(
    df,
    masks
):

    total_df = df.copy()

    condition_names = list(
        CONDITIONS.keys()
    )

    results = []

    total_combinations = 0

    for size in range(
        2,
        MAX_COMBINATION_SIZE + 1
    ):

        total_combinations += len(
            list(
                combinations(
                    condition_names,
                    size
                )
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
        f"{MAX_COMBINATION_SIZE}条件"
    )

    print(
        f"検証組み合わせ総数 : "
        f"{total_combinations:,}"
    )

    processed = 0

    for size in range(
        2,
        MAX_COMBINATION_SIZE + 1
    ):

        print()
        print(
            f"--- {size}条件組み合わせ ---"
        )

        for combo in combinations(
            condition_names,
            size
        ):

            processed += 1

            group = apply_conditions(
                df,
                masks,
                combo
            )

            if len(group) < MIN_SAMPLE_SIZE:

                continue

            stats = calculate_statistics(
                group,
                total_df
            )

            if stats is None:
                continue

            row = {

                "条件数":
                    size,

                "条件":
                    " + ".join(combo),

                "n":
                    stats["n"],

                "平均最大騰落率":
                    stats["平均最大騰落率"],

                "+5%率":
                    stats["+5%率"],

                "+10%率":
                    stats["+10%率"],

                "+20%率":
                    stats["+20%率"],

                "全体+5%率":
                    stats["全体+5%率"],

                "全体+10%率":
                    stats["全体+10%率"],

                "全体+20%率":
                    stats["全体+20%率"],

                "+5%率差":
                    stats["+5%率差"],

                "+10%率差":
                    stats["+10%率差"],

                "+20%率差":
                    stats["+20%率差"],

                "最大騰落率":
                    stats["最大騰落率"],
            }

            results.append(
                row
            )

        print(
            f"{size}条件完了"
        )

    print()
    print(
        f"有効な組み合わせ数 : "
        f"{len(results):,}"
    )

    return pd.DataFrame(
        results
    )


# ============================================================
# 上位表示
# ============================================================

def print_top_results(
    result_df
):

    if result_df.empty:

        print(
            "有効な組み合わせがありません。"
        )

        return

    # --------------------------------------------------------
    # +10%率
    # --------------------------------------------------------

    print()
    print(
        "============================================================"
    )
    print(
        "=== +10%率 上位組み合わせ ==="
    )
    print(
        "============================================================"
    )

    top10 = (
        result_df
        .sort_values(
            [
                "+10%率",
                "n",
            ],
            ascending=[
                False,
                False,
            ]
        )
        .head(30)
    )

    for _, row in top10.iterrows():

        print(
            f"n={int(row['n']):4d} / "
            f"+10%率={row['+10%率']:.1f}% / "
            f"差={row['+10%率差']:+.1f}pt / "
            f"+20%率={row['+20%率']:.1f}% / "
            f"平均最大={row['平均最大騰落率']:+.2f}% / "
            f"{row['条件']}"
        )

    # --------------------------------------------------------
    # +20%率
    # --------------------------------------------------------

    print()
    print(
        "============================================================"
    )
    print(
        "=== +20%率 上位組み合わせ ==="
    )
    print(
        "============================================================"
    )

    top20 = (
        result_df
        .sort_values(
            [
                "+20%率",
                "n",
            ],
            ascending=[
                False,
                False,
            ]
        )
        .head(30)
    )

    for _, row in top20.iterrows():

        print(
            f"n={int(row['n']):4d} / "
            f"+20%率={row['+20%率']:.1f}% / "
            f"差={row['+20%率差']:+.1f}pt / "
            f"+10%率={row['+10%率']:.1f}% / "
            f"平均最大={row['平均最大騰落率']:+.2f}% / "
            f"{row['条件']}"
        )

    # --------------------------------------------------------
    # +10%率差
    # --------------------------------------------------------

    print()
    print(
        "============================================================"
    )
    print(
        "=== 全体との差（+10%率）上位 ==="
    )
    print(
        "============================================================"
    )

    top_diff = (
        result_df
        .sort_values(
            [
                "+10%率差",
                "n",
            ],
            ascending=[
                False,
                False,
            ]
        )
        .head(30)
    )

    for _, row in top_diff.iterrows():

        print(
            f"n={int(row['n']):4d} / "
            f"+10%率={row['+10%率']:.1f}% / "
            f"差={row['+10%率差']:+.1f}pt / "
            f"+20%率={row['+20%率']:.1f}% / "
            f"{row['条件']}"
        )


# ============================================================
# 保存
# ============================================================

def save_results(
    result_df
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result_df = result_df.copy()

    result_df = result_df.sort_values(
        [
            "+10%率差",
            "+20%率差",
            "n",
        ],
        ascending=[
            False,
            False,
            False,
        ]
    )

    result_df = result_df.reset_index(
        drop=True
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
        "=== 初動スコア・条件組み合わせ全銘柄検証 ==="
    )
    print(
        "============================================================"
    )

    print(
        f"入力: {INPUT_FILE}"
    )

    print(
        f"最低サンプル数: {MIN_SAMPLE_SIZE}"
    )

    print(
        f"最大条件数: {MAX_COMBINATION_SIZE}"
    )

    # --------------------------------------------------------
    # データ
    # --------------------------------------------------------

    df = load_data()

    df = prepare_numeric_columns(
        df
    )

    # --------------------------------------------------------
    # 条件
    # --------------------------------------------------------

    masks = build_condition_masks(
        df
    )

    print()
    print(
        f"利用可能条件数: {len(masks)}"
    )

    # --------------------------------------------------------
    # 組み合わせ分析
    # --------------------------------------------------------

    result_df = analyze_combinations(
        df,
        masks
    )

    if result_df.empty:

        raise RuntimeError(
            "分析結果が0件です。"
        )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    save_results(
        result_df
    )

    # --------------------------------------------------------
    # 上位表示
    # --------------------------------------------------------

    print_top_results(
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
        "=== 組み合わせ検証完了 ==="
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
        f"保存先 : {OUTPUT_FILE}"
    )

    print(
        f"処理時間 : {total_time:.1f} 秒"
    )


if __name__ == "__main__":
    main()