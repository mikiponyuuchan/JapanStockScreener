from pathlib import Path

import pandas as pd


# ============================================================
# パス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

PANEL_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "buy_decision_backtest_panel.csv"
)

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_cross_condition_analysis.csv"
)


# ============================================================
# 基準
# ============================================================

SUCCESS_THRESHOLD = 10.0


CHANGE1_THRESHOLDS = [
    3,
    5,
    7,
    10,
    15,
]

CHANGE5_THRESHOLDS = [
    0,
    5,
    10,
    15,
    20,
]


# ============================================================
# 補助
# ============================================================

def to_bool(value):

    if isinstance(value, bool):
        return value

    if pd.isna(value):
        return False

    return (
        str(value)
        .strip()
        .lower()
        in {
            "true",
            "1",
            "yes",
            "y",
        }
    )


# ============================================================
# データ読込
# ============================================================

def load_panel():

    if not PANEL_FILE.exists():

        raise FileNotFoundError(
            f"入力ファイルなし : {PANEL_FILE}"
        )

    df = pd.read_csv(
        PANEL_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
        low_memory=False,
    )

    df["コード"] = (
        df["コード"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    df["検出日"] = pd.to_datetime(
        df["検出日"],
        errors="coerce",
    )

    numeric_columns = [
        "初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "Max3",
    ]

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = (
        df
        .sort_values(
            [
                "コード",
                "検出日",
            ]
        )
        .reset_index(drop=True)
    )

    return df


# ============================================================
# 危険回避
#
# H2は除外
# ============================================================

def add_danger_flag(df):

    df = df.copy()

    reason = (
        df["買い回避理由"]
        .fillna("")
        .astype(str)
    )

    danger = (
        reason.str.contains(
            "A_STALL",
            regex=False,
        )
        |
        reason.str.contains(
            "C_SPIKE",
            regex=False,
        )
        |
        reason.str.contains(
            "D_OVERHEAT",
            regex=False,
        )
        |
        reason.str.contains(
            "F_DECEL",
            regex=False,
        )
    )

    df["危険回避"] = danger

    return df


# ============================================================
# P5条件
#
# Score 3～4
# 5日騰落率 > 0
# VolumeRatio20 > 1
# 危険回避なし
# ============================================================

def make_p5_condition(df):

    return (
        df["初動スコア"]
        .between(
            3,
            4,
            inclusive="both",
        )
        &
        (
            df["5日騰落率"]
            > 0
        )
        &
        (
            df["VolumeRatio20"]
            > 1
        )
        &
        (
            ~df["危険回避"]
        )
    )


# ============================================================
# 成功上昇波ID
#
# Max3 >= 10 が同一銘柄で連続する場合、
# ひとつの上昇波として扱う。
# ============================================================

def add_success_wave(df):

    df = df.copy()

    df["成功"] = (
        df["Max3"]
        >= SUCCESS_THRESHOLD
    )

    df["前行成功"] = (
        df.groupby(
            "コード"
        )["成功"]
        .shift(1)
        .fillna(False)
        .astype(bool)
    )

    # 成功波の開始
    df["成功波開始"] = (
        df["成功"]
        &
        (~df["前行成功"])
    )

    # --------------------------------------------------------
    # 銘柄ごとに波番号を付ける
    # --------------------------------------------------------

    df["成功波番号"] = (
        df.groupby(
            "コード"
        )["成功波開始"]
        .cumsum()
    )

    # 成功でない行には波IDを付けない
    df["成功波ID"] = ""

    success_mask = df["成功"]

    df.loc[
        success_mask,
        "成功波ID"
    ] = (
        df.loc[
            success_mask,
            "コード"
        ]
        +
        "_W"
        +
        df.loc[
            success_mask,
            "成功波番号"
        ]
        .astype(int)
        .astype(str)
    )

    return df


# ============================================================
# 全成功上昇波数
# ============================================================

def count_all_success_waves(df):

    wave_ids = (
        df.loc[
            df["成功"],
            "成功波ID"
        ]
        .replace(
            "",
            pd.NA,
        )
        .dropna()
        .unique()
    )

    return len(wave_ids)


# ============================================================
# 1条件集計
# ============================================================

def summarize_condition(
    df,
    mask,
    condition_name,
    total_success_waves,
):

    target = df[
        mask
        &
        df["Max3"].notna()
    ].copy()

    if target.empty:
        return None

    count = len(target)

    max3 = target["Max3"]

    hit5 = int(
        (max3 >= 5).sum()
    )

    hit10 = int(
        (max3 >= 10).sum()
    )

    hit20 = int(
        (max3 >= 20).sum()
    )

    # --------------------------------------------------------
    # 重複あり成功数
    # --------------------------------------------------------

    success_rows = target[
        target["成功"]
    ]

    # --------------------------------------------------------
    # 重複除外成功上昇波数
    # --------------------------------------------------------

    success_waves = (
        success_rows[
            "成功波ID"
        ]
        .replace(
            "",
            pd.NA,
        )
        .dropna()
        .nunique()
    )

    wave_capture_rate = (
        success_waves
        / total_success_waves
        * 100
        if total_success_waves
        else 0
    )

    return {
        "条件":
            condition_name,

        "候補数":
            count,

        "Max3平均":
            round(
                max3.mean(),
                2,
            ),

        "Max3中央値":
            round(
                max3.median(),
                2,
            ),

        "+5%件数":
            hit5,

        "+5%到達率":
            round(
                hit5
                / count
                * 100,
                2,
            ),

        "+10%件数_重複あり":
            hit10,

        "+10%到達率_重複あり":
            round(
                hit10
                / count
                * 100,
                2,
            ),

        "+20%件数":
            hit20,

        "+20%到達率":
            round(
                hit20
                / count
                * 100,
                2,
            ),

        "成功上昇波数_重複除外":
            success_waves,

        "成功上昇波捕捉率":
            round(
                wave_capture_rate,
                2,
            ),
    }


# ============================================================
# クロス条件
# ============================================================

def analyze_cross_conditions(df):

    p5_mask = make_p5_condition(
        df
    )

    valid_e = (
        p5_mask
        &
        df["Max3"].notna()
    )

    base = df[
        valid_e
    ].copy()

    print()
    print("=" * 120)
    print("P5条件 基本情報")
    print("=" * 120)

    print(
        "P5条件 Max3有効件数 :",
        len(base)
    )

    print(
        "P5条件 +10%件数     :",
        int(
            (
                base["Max3"]
                >= 10
            ).sum()
        )
    )

    print(
        "P5条件 +20%件数     :",
        int(
            (
                base["Max3"]
                >= 20
            ).sum()
        )
    )

    total_success_waves = (
        count_all_success_waves(
            df
        )
    )

    print(
        "全成功上昇波数     :",
        total_success_waves
    )

    rows = []

    for chg1 in CHANGE1_THRESHOLDS:

        for chg5 in CHANGE5_THRESHOLDS:

            condition_mask = (
                p5_mask
                &
                (
                    df["前日比"]
                    >= chg1
                )
                &
                (
                    df["5日騰落率"]
                    >= chg5
                )
            )

            name = (
                f"前日比>={chg1}%"
                f" × "
                f"5日>={chg5}%"
            )

            result = summarize_condition(
                df=df,
                mask=condition_mask,
                condition_name=name,
                total_success_waves=(
                    total_success_waves
                ),
            )

            if result is not None:

                result[
                    "前日比閾値"
                ] = chg1

                result[
                    "5日騰落率閾値"
                ] = chg5

                rows.append(
                    result
                )

    return pd.DataFrame(
        rows
    )


# ============================================================
# 実用候補を抽出
# ============================================================

def print_practical_candidates(result):

    print()
    print("=" * 140)
    print(
        "実用候補"
    )
    print("=" * 140)

    # --------------------------------------------------------
    # 少数すぎる条件を除外
    #
    # まず候補20件以上を目安にする
    # --------------------------------------------------------

    practical = result[
        result["候補数"]
        >= 20
    ].copy()

    practical = (
        practical
        .sort_values(
            [
                "+10%到達率_重複あり",
                "成功上昇波捕捉率",
                "候補数",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        )
    )

    columns = [
        "条件",
        "候補数",
        "Max3平均",
        "Max3中央値",
        "+5%到達率",
        "+10%件数_重複あり",
        "+10%到達率_重複あり",
        "+20%到達率",
        "成功上昇波数_重複除外",
        "成功上昇波捕捉率",
    ]

    print(
        practical[
            columns
        ]
        .head(20)
        .to_string(
            index=False
        )
    )


# ============================================================
# 松屋を落とさない条件
# ============================================================

def print_sub_7_candidates(
    df,
):

    p5_mask = make_p5_condition(
        df
    )

    work = df[
        p5_mask
        &
        df["Max3"].notna()
        &
        (
            df["前日比"]
            >= 5
        )
        &
        (
            df["前日比"]
            < 7
        )
        &
        (
            df["Max3"]
            >= 10
        )
    ].copy()

    print()
    print("=" * 140)
    print(
        "前日比5%以上7%未満でも +10%以上成功した銘柄"
    )
    print("=" * 140)

    if work.empty:

        print(
            "該当なし"
        )

        return

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "BreakoutSignal",
        "New30High",
        "Max3",
        "成功波ID",
    ]

    print(
        work[
            columns
        ]
        .sort_values(
            "Max3",
            ascending=False,
        )
        .to_string(
            index=False
        )
    )


# ============================================================
# 成功波の代表行
# ============================================================

def print_unique_success_waves(
    df,
):

    p5_mask = make_p5_condition(
        df
    )

    work = df[
        p5_mask
        &
        df["成功"]
    ].copy()

    if work.empty:
        return

    # --------------------------------------------------------
    # 同一波の中で最初にP5条件へ入った日だけ残す
    # --------------------------------------------------------

    work = (
        work
        .sort_values(
            [
                "コード",
                "検出日",
            ]
        )
        .drop_duplicates(
            subset=[
                "成功波ID",
            ],
            keep="first",
        )
    )

    print()
    print("=" * 150)
    print(
        "P5条件で捕捉できた成功上昇波 "
        "― 各波の最初の候補日"
    )
    print("=" * 150)

    columns = [
        "成功波ID",
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "Max3",
    ]

    print(
        work[
            columns
        ]
        .sort_values(
            "Max3",
            ascending=False,
        )
        .to_string(
            index=False
        )
    )


# ============================================================
# main
# ============================================================

def main():

    print()
    print("=" * 140)
    print(
        "早期買い候補 "
        "前日比 × 5日騰落率 "
        "クロス検証"
    )
    print("=" * 140)

    df = load_panel()

    df = add_danger_flag(
        df
    )

    df = add_success_wave(
        df
    )

    result = analyze_cross_conditions(
        df
    )

    if result.empty:

        print(
            "分析結果なし"
        )

        return

    print()
    print("=" * 160)
    print(
        "全クロス条件"
    )
    print("=" * 160)

    display_columns = [
        "条件",
        "候補数",
        "Max3平均",
        "Max3中央値",
        "+5%到達率",
        "+10%件数_重複あり",
        "+10%到達率_重複あり",
        "+20%到達率",
        "成功上昇波数_重複除外",
        "成功上昇波捕捉率",
    ]

    print(
        result
        .sort_values(
            [
                "前日比閾値",
                "5日騰落率閾値",
            ]
        )[
            display_columns
        ]
        .to_string(
            index=False
        )
    )    

    print_practical_candidates(
        result
    )

    print_sub_7_candidates(
        df
    )

    print_unique_success_waves(
        df
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

    print()
    print("=" * 140)

    print(
        "保存 :",
        OUTPUT_FILE
    )

    print("=" * 140)


if __name__ == "__main__":
    main()

