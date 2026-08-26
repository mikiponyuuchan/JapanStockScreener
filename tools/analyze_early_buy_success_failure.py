from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# パス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_candidate_details.csv"
)

OUTPUT_SUMMARY_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_success_failure_summary.csv"
)

OUTPUT_THRESHOLD_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_success_failure_thresholds.csv"
)

OUTPUT_DETAILS_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_success_failure_details.csv"
)


# ============================================================
# 設定
# ============================================================

TARGET_CONDITION = "E_C_plus_Volume20gt1"

SUCCESS_THRESHOLD = 10.0
FAILURE_THRESHOLD = 5.0


NUMERIC_FEATURES = [
    "初動スコア",
    "基本初動スコア",
    "前日比",
    "5日騰落率",
    "20日騰落率",
    "RSI",
    "VolumeRatio",
    "VolumeRatio20",
    "MA25Deviation",
]


SIGNAL_FEATURES = [
    "BreakoutSignal",
    "New30High",
]


# ============================================================
# 共通
# ============================================================

def print_separator(width=130):
    print("=" * width)


def to_bool_series(series):
    """
    CSVから読み込んだ bool / 文字列 / 数値を
    True / False に統一する。
    """

    if series.dtype == bool:
        return series.fillna(False)

    text = (
        series
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return text.isin(
        [
            "true",
            "1",
            "1.0",
            "yes",
            "y",
            "○",
        ]
    )


def find_column(df, candidates):
    """
    候補名の中から存在する列名を返す。
    """

    for column in candidates:
        if column in df.columns:
            return column

    return None


# ============================================================
# 読み込み
# ============================================================

def load_data():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"入力ファイルがありません : {INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        low_memory=False,
    )

    print(f"読込 : {INPUT_FILE}")
    print(f"行数 : {len(df)}")

    return df


# ============================================================
# P5条件抽出
# ============================================================

def extract_target_condition(df):

    condition_column = find_column(
        df,
        [
            "条件",
            "condition",
            "Condition",
        ],
    )

    if condition_column is None:
        raise KeyError(
            "条件列が見つかりません。\n"
            f"列一覧 : {df.columns.tolist()}"
        )

    target = df[
        df[condition_column].astype(str)
        == TARGET_CONDITION
    ].copy()

    print()
    print_separator()
    print("=== P5条件抽出 ===")
    print_separator()

    print(f"条件 : {TARGET_CONDITION}")
    print(f"件数 : {len(target)}")

    if target.empty:
        print()
        print("P5条件のデータがありません。")
        print("条件列の値を確認します。")

        values = (
            df[condition_column]
            .dropna()
            .astype(str)
            .value_counts()
        )

        print(values.to_string())

        raise ValueError(
            "P5条件を抽出できませんでした。"
        )

    return target


# ============================================================
# Max3列確認
# ============================================================

def prepare_max3(df):

    max3_column = find_column(
        df,
        [
            "Max3",
            "成功Max3",
            "max3",
        ],
    )

    if max3_column is None:
        raise KeyError(
            "Max3列が見つかりません。\n"
            f"列一覧 : {df.columns.tolist()}"
        )

    df = df.copy()

    df["Max3分析値"] = pd.to_numeric(
        df[max3_column],
        errors="coerce",
    )

    return df


# ============================================================
# 成功・失敗・中間
# ============================================================

def classify_result(df):

    df = df.copy()

    df["結果分類"] = np.select(
        [
            df["Max3分析値"] >= SUCCESS_THRESHOLD,
            df["Max3分析値"] < FAILURE_THRESHOLD,
        ],
        [
            "成功",
            "失敗",
        ],
        default="中間",
    )

    df.loc[
        df["Max3分析値"].isna(),
        "結果分類",
    ] = "Max3なし"

    return df


def print_group_summary(df):

    print()
    print_separator()
    print("=== P5条件 成功・失敗内訳 ===")
    print_separator()

    print(
        df["結果分類"]
        .value_counts(dropna=False)
        .to_string()
    )

    valid = df[
        df["Max3分析値"].notna()
    ]

    print()
    print(f"Max3有効件数 : {len(valid)}")

    if len(valid) > 0:
        print(
            f"Max3平均     : "
            f"{valid['Max3分析値'].mean():.2f}%"
        )
        print(
            f"Max3中央値   : "
            f"{valid['Max3分析値'].median():.2f}%"
        )


# ============================================================
# 数値特徴比較
# ============================================================

def compare_numeric_features(df):

    rows = []

    success = df[
        df["結果分類"] == "成功"
    ]

    failure = df[
        df["結果分類"] == "失敗"
    ]

    for feature in NUMERIC_FEATURES:

        if feature not in df.columns:
            continue

        success_values = pd.to_numeric(
            success[feature],
            errors="coerce",
        ).dropna()

        failure_values = pd.to_numeric(
            failure[feature],
            errors="coerce",
        ).dropna()

        success_mean = (
            success_values.mean()
            if len(success_values) > 0
            else np.nan
        )

        failure_mean = (
            failure_values.mean()
            if len(failure_values) > 0
            else np.nan
        )

        success_median = (
            success_values.median()
            if len(success_values) > 0
            else np.nan
        )

        failure_median = (
            failure_values.median()
            if len(failure_values) > 0
            else np.nan
        )

        rows.append(
            {
                "特徴": feature,
                "成功件数": len(success_values),
                "成功平均": success_mean,
                "成功中央値": success_median,
                "失敗件数": len(failure_values),
                "失敗平均": failure_mean,
                "失敗中央値": failure_median,
                "平均差": (
                    success_mean
                    - failure_mean
                ),
                "中央値差": (
                    success_median
                    - failure_median
                ),
            }
        )

    result = pd.DataFrame(rows)

    print()
    print_separator()
    print("=== P5条件 成功 vs 失敗 数値特徴比較 ===")
    print_separator()

    if result.empty:
        print("比較可能な数値特徴がありません。")
        return result

    display = result.copy()

    numeric_columns = [
        "成功平均",
        "成功中央値",
        "失敗平均",
        "失敗中央値",
        "平均差",
        "中央値差",
    ]

    for column in numeric_columns:
        display[column] = (
            pd.to_numeric(
                display[column],
                errors="coerce",
            )
            .round(2)
        )

    print(
        display.to_string(
            index=False
        )
    )

    return result


# ============================================================
# シグナル比較
# ============================================================

def compare_signal_features(df):

    rows = []

    success = df[
        df["結果分類"] == "成功"
    ]

    failure = df[
        df["結果分類"] == "失敗"
    ]

    for feature in SIGNAL_FEATURES:

        if feature not in df.columns:
            continue

        success_signal = to_bool_series(
            success[feature]
        )

        failure_signal = to_bool_series(
            failure[feature]
        )

        success_rate = (
            success_signal.mean() * 100
            if len(success_signal) > 0
            else np.nan
        )

        failure_rate = (
            failure_signal.mean() * 100
            if len(failure_signal) > 0
            else np.nan
        )

        rows.append(
            {
                "特徴": feature,
                "成功件数": len(success_signal),
                "成功発生率": success_rate,
                "失敗件数": len(failure_signal),
                "失敗発生率": failure_rate,
                "発生率差": (
                    success_rate
                    - failure_rate
                ),
            }
        )

    result = pd.DataFrame(rows)

    print()
    print_separator()
    print("=== P5条件 成功 vs 失敗 シグナル比較 ===")
    print_separator()

    if result.empty:
        print("比較可能なシグナルがありません。")
        return result

    display = result.copy()

    for column in [
        "成功発生率",
        "失敗発生率",
        "発生率差",
    ]:
        display[column] = (
            pd.to_numeric(
                display[column],
                errors="coerce",
            )
            .round(2)
        )

    print(
        display.to_string(
            index=False
        )
    )

    return result


# ============================================================
# 閾値評価
# ============================================================

def evaluate_threshold(
    df,
    feature,
    operator_name,
    threshold,
):

    if feature not in df.columns:
        return None

    values = pd.to_numeric(
        df[feature],
        errors="coerce",
    )

    if operator_name == ">=":
        mask = values >= threshold

    elif operator_name == ">":
        mask = values > threshold

    elif operator_name == "<=":
        mask = values <= threshold

    elif operator_name == "<":
        mask = values < threshold

    else:
        raise ValueError(
            f"未対応演算子 : {operator_name}"
        )

    target = df[
        mask
        & df["Max3分析値"].notna()
    ].copy()

    if target.empty:
        return None

    candidate_count = len(target)

    success_count = (
        target["Max3分析値"]
        >= SUCCESS_THRESHOLD
    ).sum()

    failure_count = (
        target["Max3分析値"]
        < FAILURE_THRESHOLD
    ).sum()

    plus5_count = (
        target["Max3分析値"] >= 5
    ).sum()

    plus10_count = (
        target["Max3分析値"] >= 10
    ).sum()

    plus20_count = (
        target["Max3分析値"] >= 20
    ).sum()

    return {
        "特徴": feature,
        "条件": (
            f"{feature} "
            f"{operator_name} "
            f"{threshold}"
        ),
        "候補数": candidate_count,
        "Max3平均": target[
            "Max3分析値"
        ].mean(),
        "Max3中央値": target[
            "Max3分析値"
        ].median(),
        "+5%件数": plus5_count,
        "+5%到達率": (
            plus5_count
            / candidate_count
            * 100
        ),
        "+10%件数": plus10_count,
        "+10%到達率": (
            plus10_count
            / candidate_count
            * 100
        ),
        "+20%件数": plus20_count,
        "+20%到達率": (
            plus20_count
            / candidate_count
            * 100
        ),
        "成功件数": success_count,
        "失敗件数": failure_count,
    }


def analyze_thresholds(df):

    tests = [
        # -------------------------
        # 初動スコア
        # -------------------------
        ("初動スコア", ">=", 3),
        ("初動スコア", ">=", 4),
        ("初動スコア", ">=", 5),

        # -------------------------
        # 前日比
        # -------------------------
        ("前日比", ">", 0),
        ("前日比", ">=", 3),
        ("前日比", ">=", 5),
        ("前日比", ">=", 7),
        ("前日比", ">=", 10),

        # -------------------------
        # 5日騰落率
        # -------------------------
        ("5日騰落率", ">", 0),
        ("5日騰落率", ">=", 5),
        ("5日騰落率", ">=", 10),
        ("5日騰落率", ">=", 20),

        # -------------------------
        # 20日騰落率
        # -------------------------
        ("20日騰落率", ">", 0),
        ("20日騰落率", ">=", 10),
        ("20日騰落率", ">=", 20),
        ("20日騰落率", ">=", 30),

        # -------------------------
        # RSI
        # -------------------------
        ("RSI", ">=", 50),
        ("RSI", ">=", 55),
        ("RSI", ">=", 60),
        ("RSI", ">=", 65),
        ("RSI", ">=", 70),

        # -------------------------
        # VolumeRatio
        # -------------------------
        ("VolumeRatio", ">=", 1),
        ("VolumeRatio", ">=", 1.5),
        ("VolumeRatio", ">=", 2),
        ("VolumeRatio", ">=", 3),

        # -------------------------
        # VolumeRatio20
        # -------------------------
        ("VolumeRatio20", ">=", 1),
        ("VolumeRatio20", ">=", 1.2),
        ("VolumeRatio20", ">=", 1.5),
        ("VolumeRatio20", ">=", 2),
        ("VolumeRatio20", ">=", 3),
        ("VolumeRatio20", ">=", 4),

        # -------------------------
        # MA25乖離率
        # -------------------------
        ("MA25Deviation", ">", 0),
        ("MA25Deviation", ">=", 5),
        ("MA25Deviation", ">=", 10),
        ("MA25Deviation", ">=", 15),
        ("MA25Deviation", ">=", 20),
    ]

    rows = []

    for (
        feature,
        operator_name,
        threshold,
    ) in tests:

        row = evaluate_threshold(
            df,
            feature,
            operator_name,
            threshold,
        )

        if row is not None:
            rows.append(row)

    result = pd.DataFrame(rows)

    print()
    print_separator()
    print("=== P5条件 単独閾値テスト ===")
    print_separator()

    if result.empty:
        print("閾値評価結果がありません。")
        return result

    display = result.copy()

    for column in [
        "Max3平均",
        "Max3中央値",
        "+5%到達率",
        "+10%到達率",
        "+20%到達率",
    ]:
        display[column] = (
            pd.to_numeric(
                display[column],
                errors="coerce",
            )
            .round(2)
        )

    print(
        display.to_string(
            index=False
        )
    )

    return result


# ============================================================
# RSIレンジ評価
# ============================================================

def analyze_rsi_ranges(df):

    if "RSI" not in df.columns:
        return pd.DataFrame()

    rsi = pd.to_numeric(
        df["RSI"],
        errors="coerce",
    )

    ranges = [
        (40, 60),
        (45, 65),
        (50, 70),
        (50, 75),
        (50, 80),
        (55, 70),
        (55, 75),
        (55, 80),
        (60, 75),
        (60, 80),
        (65, 80),
        (70, 85),
    ]

    rows = []

    for lower, upper in ranges:

        target = df[
            (rsi >= lower)
            & (rsi <= upper)
            & df["Max3分析値"].notna()
        ]

        if target.empty:
            continue

        count = len(target)

        plus10 = (
            target["Max3分析値"]
            >= SUCCESS_THRESHOLD
        ).sum()

        plus20 = (
            target["Max3分析値"]
            >= 20
        ).sum()

        rows.append(
            {
                "条件": (
                    f"RSI {lower}～{upper}"
                ),
                "候補数": count,
                "Max3平均": (
                    target[
                        "Max3分析値"
                    ].mean()
                ),
                "Max3中央値": (
                    target[
                        "Max3分析値"
                    ].median()
                ),
                "+10%件数": plus10,
                "+10%到達率": (
                    plus10
                    / count
                    * 100
                ),
                "+20%件数": plus20,
                "+20%到達率": (
                    plus20
                    / count
                    * 100
                ),
            }
        )

    result = pd.DataFrame(rows)

    print()
    print_separator()
    print("=== P5条件 RSIレンジテスト ===")
    print_separator()

    if result.empty:
        print("RSIレンジ評価結果がありません。")
        return result

    display = result.copy()

    for column in [
        "Max3平均",
        "Max3中央値",
        "+10%到達率",
        "+20%到達率",
    ]:
        display[column] = (
            pd.to_numeric(
                display[column],
                errors="coerce",
            )
            .round(2)
        )

    print(
        display.to_string(
            index=False
        )
    )

    return result


# ============================================================
# 複合条件
# ============================================================

def analyze_combinations(df):

    numeric = {}

    for feature in NUMERIC_FEATURES:
        if feature in df.columns:
            numeric[feature] = pd.to_numeric(
                df[feature],
                errors="coerce",
            )

    tests = []

    # --------------------------------------------------------
    # VolumeRatio20中心
    # --------------------------------------------------------

    if (
        "VolumeRatio20" in numeric
        and "5日騰落率" in numeric
    ):
        tests.append(
            (
                "Vol20>=1.5 + 5日>0",
                (
                    (numeric["VolumeRatio20"] >= 1.5)
                    &
                    (numeric["5日騰落率"] > 0)
                ),
            )
        )

    if (
        "VolumeRatio20" in numeric
        and "RSI" in numeric
    ):
        tests.append(
            (
                "Vol20>=1.5 + RSI55～80",
                (
                    (numeric["VolumeRatio20"] >= 1.5)
                    &
                    (numeric["RSI"] >= 55)
                    &
                    (numeric["RSI"] <= 80)
                ),
            )
        )

    if (
        "VolumeRatio20" in numeric
        and "20日騰落率" in numeric
    ):
        tests.append(
            (
                "Vol20>=1.5 + 20日>0",
                (
                    (numeric["VolumeRatio20"] >= 1.5)
                    &
                    (numeric["20日騰落率"] > 0)
                ),
            )
        )

    if (
        "VolumeRatio20" in numeric
        and "MA25Deviation" in numeric
    ):
        tests.append(
            (
                "Vol20>=1.5 + MA25乖離>0",
                (
                    (numeric["VolumeRatio20"] >= 1.5)
                    &
                    (numeric["MA25Deviation"] > 0)
                ),
            )
        )

    # --------------------------------------------------------
    # 3条件
    # --------------------------------------------------------

    if all(
        feature in numeric
        for feature in [
            "VolumeRatio20",
            "5日騰落率",
            "RSI",
        ]
    ):
        tests.append(
            (
                "Vol20>=1.5 + 5日>0 + RSI55～80",
                (
                    (numeric["VolumeRatio20"] >= 1.5)
                    &
                    (numeric["5日騰落率"] > 0)
                    &
                    (numeric["RSI"] >= 55)
                    &
                    (numeric["RSI"] <= 80)
                ),
            )
        )

    if all(
        feature in numeric
        for feature in [
            "VolumeRatio20",
            "5日騰落率",
            "20日騰落率",
        ]
    ):
        tests.append(
            (
                "Vol20>=1.5 + 5日>0 + 20日>0",
                (
                    (numeric["VolumeRatio20"] >= 1.5)
                    &
                    (numeric["5日騰落率"] > 0)
                    &
                    (numeric["20日騰落率"] > 0)
                ),
            )
        )

    if all(
        feature in numeric
        for feature in [
            "VolumeRatio20",
            "RSI",
            "MA25Deviation",
        ]
    ):
        tests.append(
            (
                "Vol20>=1.5 + RSI55～80 + MA25乖離>0",
                (
                    (numeric["VolumeRatio20"] >= 1.5)
                    &
                    (numeric["RSI"] >= 55)
                    &
                    (numeric["RSI"] <= 80)
                    &
                    (numeric["MA25Deviation"] > 0)
                ),
            )
        )

    rows = []

    for name, mask in tests:

        target = df[
            mask
            & df["Max3分析値"].notna()
        ]

        if target.empty:
            continue

        count = len(target)

        plus5 = (
            target["Max3分析値"] >= 5
        ).sum()

        plus10 = (
            target["Max3分析値"] >= 10
        ).sum()

        plus20 = (
            target["Max3分析値"] >= 20
        ).sum()

        rows.append(
            {
                "条件": name,
                "候補数": count,
                "Max3平均": (
                    target[
                        "Max3分析値"
                    ].mean()
                ),
                "Max3中央値": (
                    target[
                        "Max3分析値"
                    ].median()
                ),
                "+5%件数": plus5,
                "+5%到達率": (
                    plus5
                    / count
                    * 100
                ),
                "+10%件数": plus10,
                "+10%到達率": (
                    plus10
                    / count
                    * 100
                ),
                "+20%件数": plus20,
                "+20%到達率": (
                    plus20
                    / count
                    * 100
                ),
            }
        )

    result = pd.DataFrame(rows)

    print()
    print_separator()
    print("=== P5条件 複合条件テスト ===")
    print_separator()

    if result.empty:
        print("複合条件評価結果がありません。")
        return result

    display = result.copy()

    for column in [
        "Max3平均",
        "Max3中央値",
        "+5%到達率",
        "+10%到達率",
        "+20%到達率",
    ]:
        display[column] = (
            pd.to_numeric(
                display[column],
                errors="coerce",
            )
            .round(2)
        )

    print(
        display.to_string(
            index=False
        )
    )

    return result


# ============================================================
# 成功銘柄一覧
# ============================================================

def print_success_details(df):

    success = df[
        df["結果分類"] == "成功"
    ].copy()

    print()
    print_separator()
    print("=== P5条件 Max3 >= 10% 成功銘柄 ===")
    print_separator()

    if success.empty:
        print("成功銘柄はありません。")
        return

    success = success.sort_values(
        "Max3分析値",
        ascending=False,
    )

    preferred_columns = [
        "日付",
        "観測日",
        "コード",
        "銘柄名",
        "初動スコア",
        "基本初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "BreakoutSignal",
        "New30High",
        "Max3分析値",
    ]

    columns = [
        column
        for column in preferred_columns
        if column in success.columns
    ]

    print(
        success[
            columns
        ].to_string(
            index=False
        )
    )


# ============================================================
# 保存
# ============================================================

def save_results(
    numeric_result,
    signal_result,
    threshold_result,
    rsi_result,
    combination_result,
    details,
):

    OUTPUT_SUMMARY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_frames = []

    if not numeric_result.empty:
        temp = numeric_result.copy()
        temp.insert(
            0,
            "分析種類",
            "数値特徴比較",
        )
        summary_frames.append(temp)

    if not signal_result.empty:
        temp = signal_result.copy()
        temp.insert(
            0,
            "分析種類",
            "シグナル比較",
        )
        summary_frames.append(temp)

    if summary_frames:
        summary = pd.concat(
            summary_frames,
            ignore_index=True,
            sort=False,
        )

        summary.to_csv(
            OUTPUT_SUMMARY_FILE,
            index=False,
            encoding="utf-8-sig",
        )

    threshold_frames = []

    if not threshold_result.empty:
        temp = threshold_result.copy()
        temp.insert(
            0,
            "分析種類",
            "単独閾値",
        )
        threshold_frames.append(temp)

    if not rsi_result.empty:
        temp = rsi_result.copy()
        temp.insert(
            0,
            "分析種類",
            "RSIレンジ",
        )
        threshold_frames.append(temp)

    if not combination_result.empty:
        temp = combination_result.copy()
        temp.insert(
            0,
            "分析種類",
            "複合条件",
        )
        threshold_frames.append(temp)

    if threshold_frames:
        thresholds = pd.concat(
            threshold_frames,
            ignore_index=True,
            sort=False,
        )

        thresholds.to_csv(
            OUTPUT_THRESHOLD_FILE,
            index=False,
            encoding="utf-8-sig",
        )

    details.to_csv(
        OUTPUT_DETAILS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print_separator()
    print("=== 保存 ===")
    print_separator()

    if summary_frames:
        print(
            f"比較結果 : "
            f"{OUTPUT_SUMMARY_FILE}"
        )

    if threshold_frames:
        print(
            f"閾値結果 : "
            f"{OUTPUT_THRESHOLD_FILE}"
        )

    print(
        f"詳細結果 : "
        f"{OUTPUT_DETAILS_FILE}"
    )


# ============================================================
# main
# ============================================================

def main():

    print()
    print_separator()
    print("早期買い候補 P5条件 成功・失敗比較")
    print_separator()
    print()

    df = load_data()

    target = extract_target_condition(
        df
    )

    target = prepare_max3(
        target
    )

    target = classify_result(
        target
    )

    print_group_summary(
        target
    )

    numeric_result = (
        compare_numeric_features(
            target
        )
    )

    signal_result = (
        compare_signal_features(
            target
        )
    )

    threshold_result = (
        analyze_thresholds(
            target
        )
    )

    rsi_result = (
        analyze_rsi_ranges(
            target
        )
    )

    combination_result = (
        analyze_combinations(
            target
        )
    )

    print_success_details(
        target
    )

    save_results(
        numeric_result,
        signal_result,
        threshold_result,
        rsi_result,
        combination_result,
        target,
    )

    print()
    print_separator()
    print("分析完了")
    print_separator()


if __name__ == "__main__":
    main()
