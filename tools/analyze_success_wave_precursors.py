from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# パス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

TRACKING_DIR = (
    ROOT_DIR
    / "data"
    / "tracking"
)

INPUT_FILE = (
    TRACKING_DIR
    / "buy_decision_backtest_panel.csv"
)

EVENT_OUTPUT = (
    TRACKING_DIR
    / "success_wave_events.csv"
)

PRECURSOR_OUTPUT = (
    TRACKING_DIR
    / "success_wave_precursor_comparison.csv"
)


# ============================================================
# 成功判定
# ============================================================

SUCCESS_THRESHOLD = 10.0

# 非成功群はMax3 +5%未満
CONTROL_THRESHOLD = 5.0

# 同一銘柄で成功日が連続している場合、
# 最初の日だけを成功イベントとして採用
#
# 現在のデータは営業日単位なので、
# 「前の保存営業日も成功だったか」で判定する。
# ============================================================


# ============================================================
# 数値列
# ============================================================

FEATURE_COLUMNS = [
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


# ============================================================
# bool変換
# ============================================================

def to_bool(value):

    if isinstance(value, bool):
        return value

    if pd.isna(value):
        return False

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "yes",
        "y",
    }


# ============================================================
# 入力読込
# ============================================================

def load_panel():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"入力ファイルがありません : {INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
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

    numeric_columns = (
        FEATURE_COLUMNS
        + [
            "終値",
            "Day1",
            "Day2",
            "Day3",
            "Max3",
        ]
    )

    for col in numeric_columns:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    bool_columns = [
        "BreakoutSignal",
        "New30High",
        "買い回避",
        "A_STALL",
        "C_SPIKE",
        "D_OVERHEAT",
        "F_DECEL",
        "H2",
    ]

    for col in bool_columns:

        if col in df.columns:

            df[col] = (
                df[col]
                .map(to_bool)
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
# 成功イベントを1上昇波1件にする
# ============================================================

def build_success_events(panel):

    work = panel[
        panel["Max3"].notna()
    ].copy()

    work["成功候補"] = (
        work["Max3"]
        >= SUCCESS_THRESHOLD
    )

    # --------------------------------------------------------
    # 同一銘柄の前の観測行が成功候補だったか
    # --------------------------------------------------------

    work["前回成功候補"] = (
        work.groupby(
            "コード"
        )["成功候補"]
        .shift(1)
        .fillna(False)
        .astype(bool)
    )

    # --------------------------------------------------------
    # 成功が始まった最初の日だけ採用
    # --------------------------------------------------------

    work["成功波開始"] = (
        work["成功候補"]
        &
        (~work["前回成功候補"])
    )

    events = work[
        work["成功波開始"]
    ].copy()

    events = (
        events
        .sort_values(
            [
                "検出日",
                "コード",
            ]
        )
        .reset_index(drop=True)
    )

    events["イベントID"] = [
        f"W{i:04d}"
        for i in range(
            1,
            len(events) + 1
        )
    ]

    return events


# ============================================================
# 成功イベント前の状態を抽出
# ============================================================

def build_success_precursors(
    panel,
    events,
):

    rows = []

    groups = {
        code:
            group.reset_index(drop=True)
        for code, group
        in panel.groupby(
            "コード",
            sort=False,
        )
    }

    for _, event in events.iterrows():

        code = event["コード"]

        history = groups.get(code)

        if history is None:
            continue

        event_date = event["検出日"]

        matches = history.index[
            history["検出日"]
            == event_date
        ].tolist()

        if not matches:
            continue

        event_index = matches[0]

        for lead in [
            3,
            2,
            1,
            0,
        ]:

            source_index = (
                event_index
                - lead
            )

            if source_index < 0:
                continue

            source = history.iloc[
                source_index
            ]

            row = {
                "イベントID":
                    event["イベントID"],

                "成功基準日":
                    event_date,

                "コード":
                    code,

                "銘柄名":
                    event["銘柄名"],

                "成功Max3":
                    event["Max3"],

                "何営業日前":
                    lead,

                "観測日":
                    source["検出日"],

                "群":
                    "成功",
            }

            for col in FEATURE_COLUMNS:

                row[col] = (
                    source.get(
                        col,
                        pd.NA,
                    )
                )

            for col in [
                "BreakoutSignal",
                "New30High",
                "買い回避",
                "A_STALL",
                "C_SPIKE",
                "D_OVERHEAT",
                "F_DECEL",
                "H2",
            ]:

                row[col] = (
                    source.get(
                        col,
                        False,
                    )
                )

            row["買い回避理由"] = (
                source.get(
                    "買い回避理由",
                    "",
                )
            )

            rows.append(row)
            
    return pd.DataFrame(rows)


# ============================================================
# 非成功群
#
# 成功イベントの各観測日と同じ日について
# Max3 < +5% の銘柄を比較対象にする。
# ============================================================

def build_control_rows(
    panel,
    success_precursors,
):

    rows = []

    if success_precursors.empty:
        return pd.DataFrame()

    for lead in [
        3,
        2,
        1,
        0,
    ]:

        success_part = (
            success_precursors[
                success_precursors[
                    "何営業日前"
                ]
                == lead
            ]
        )

        observation_dates = (
            success_part[
                "観測日"
            ]
            .dropna()
            .unique()
        )

        for observation_date in observation_dates:

            # ------------------------------------------------
            # この観測日の成功群コード
            # ------------------------------------------------

            success_codes = set(
                success_part[
                    success_part[
                        "観測日"
                    ]
                    == observation_date
                ]["コード"]
                .astype(str)
            )

            day_panel = panel[
                panel["検出日"]
                == observation_date
            ].copy()

            # ------------------------------------------------
            # Max3が確定しており、
            # +5%未満だったもの
            # ------------------------------------------------

            controls = day_panel[
                (
                    day_panel[
                        "Max3"
                    ].notna()
                )
                &
                (
                    day_panel[
                        "Max3"
                    ]
                    < CONTROL_THRESHOLD
                )
                &
                (
                    ~day_panel[
                        "コード"
                    ]
                    .astype(str)
                    .isin(
                        success_codes
                    )
                )
            ]

            for _, source in controls.iterrows():

                row = {
                    "イベントID":
                        "",

                    "成功基準日":
                        pd.NaT,

                    "コード":
                        source["コード"],

                    "銘柄名":
                        source["銘柄名"],

                    "成功Max3":
                        source["Max3"],

                    "何営業日前":
                        lead,

                    "観測日":
                        observation_date,

                    "群":
                        "非成功",
                }

                for col in FEATURE_COLUMNS:

                    row[col] = (
                        source.get(
                            col,
                            pd.NA,
                        )
                    )

                for col in [
                    "BreakoutSignal",
                    "New30High",
                    "買い回避",
                    "A_STALL",
                    "C_SPIKE",
                    "D_OVERHEAT",
                    "F_DECEL",
                    "H2",
                ]:

                    row[col] = (
                        source.get(
                            col,
                            False,
                        )
                    )

                row["買い回避理由"] = (
                    source.get(
                        "買い回避理由",
                        "",
                    )
                )

                rows.append(row)                

    return pd.DataFrame(rows)


# ============================================================
# 数値特徴比較
# ============================================================

def numeric_feature_summary(
    combined,
):

    rows = []

    for lead in [
        3,
        2,
        1,
        0,
    ]:

        lead_data = combined[
            combined[
                "何営業日前"
            ]
            == lead
        ]

        for feature in FEATURE_COLUMNS:

            success_values = (
                pd.to_numeric(
                    lead_data[
                        lead_data["群"]
                        == "成功"
                    ][feature],
                    errors="coerce",
                )
                .dropna()
            )

            control_values = (
                pd.to_numeric(
                    lead_data[
                        lead_data["群"]
                        == "非成功"
                    ][feature],
                    errors="coerce",
                )
                .dropna()
            )

            if (
                success_values.empty
                or control_values.empty
            ):
                continue

            success_mean = (
                success_values.mean()
            )

            control_mean = (
                control_values.mean()
            )

            rows.append({

                "何営業日前":
                    lead,

                "特徴":
                    feature,

                "成功件数":
                    len(success_values),

                "成功平均":
                    round(
                        success_mean,
                        2,
                    ),

                "成功中央値":
                    round(
                        success_values.median(),
                        2,
                    ),

                "非成功件数":
                    len(control_values),

                "非成功平均":
                    round(
                        control_mean,
                        2,
                    ),

                "非成功中央値":
                    round(
                        control_values.median(),
                        2,
                    ),

                "平均差":
                    round(
                        success_mean
                        - control_mean,
                        2,
                    ),
            })

    return pd.DataFrame(rows)


# ============================================================
# bool特徴比較
# ============================================================

def bool_feature_summary(
    combined,
):

    bool_features = [
        "BreakoutSignal",
        "New30High",
        "買い回避",
        "A_STALL",
        "C_SPIKE",
        "D_OVERHEAT",
        "F_DECEL",
        "H2",
    ]

    rows = []

    for lead in [
        3,
        2,
        1,
        0,
    ]:

        lead_data = combined[
            combined[
                "何営業日前"
            ]
            == lead
        ]

        for feature in bool_features:

            if feature not in lead_data:
                continue

            success_values = (
                lead_data[
                    lead_data["群"]
                    == "成功"
                ][feature]
                .map(to_bool)
            )

            control_values = (
                lead_data[
                    lead_data["群"]
                    == "非成功"
                ][feature]
                .map(to_bool)
            )

            if (
                success_values.empty
                or control_values.empty
            ):
                continue

            success_rate = (
                success_values.mean()
                * 100
            )

            control_rate = (
                control_values.mean()
                * 100
            )

            rows.append({

                "何営業日前":
                    lead,

                "特徴":
                    feature,

                "成功件数":
                    len(success_values),

                "成功発生率":
                    round(
                        success_rate,
                        1,
                    ),

                "非成功件数":
                    len(control_values),

                "非成功発生率":
                    round(
                        control_rate,
                        1,
                    ),

                "差":
                    round(
                        success_rate
                        - control_rate,
                        1,
                    ),
            })

    return pd.DataFrame(rows)


# ============================================================
# スコア帯比較
# ============================================================

def score_band_summary(
    combined,
):

    rows = []

    for lead in [
        3,
        2,
        1,
        0,
    ]:

        part = combined[
            combined[
                "何営業日前"
            ]
            == lead
        ].copy()

        score = pd.to_numeric(
            part["初動スコア"],
            errors="coerce",
        )

        part["スコア帯"] = np.select(
            [
                score >= 6,
                score >= 5,
                score >= 3,
                score >= 1,
            ],
            [
                "6点以上",
                "5点",
                "3-4点",
                "1-2点",
            ],
            default="0点以下",
        )

        for band in [
            "6点以上",
            "5点",
            "3-4点",
            "1-2点",
            "0点以下",
        ]:

            success_count = len(
                part[
                    (
                        part["群"]
                        == "成功"
                    )
                    &
                    (
                        part["スコア帯"]
                        == band
                    )
                ]
            )

            control_count = len(
                part[
                    (
                        part["群"]
                        == "非成功"
                    )
                    &
                    (
                        part["スコア帯"]
                        == band
                    )
                ]
            )

            success_total = len(
                part[
                    part["群"]
                    == "成功"
                ]
            )

            control_total = len(
                part[
                    part["群"]
                    == "非成功"
                ]
            )

            success_rate = (
                success_count
                / success_total
                * 100
                if success_total
                else 0
            )

            control_rate = (
                control_count
                / control_total
                * 100
                if control_total
                else 0
            )

            rows.append({

                "何営業日前":
                    lead,

                "スコア帯":
                    band,

                "成功件数":
                    success_count,

                "成功構成率":
                    round(
                        success_rate,
                        1,
                    ),

                "非成功件数":
                    control_count,

                "非成功構成率":
                    round(
                        control_rate,
                        1,
                    ),

                "構成率差":
                    round(
                        success_rate
                        - control_rate,
                        1,
                    ),
            })

    return pd.DataFrame(rows)


# ============================================================
# 低スコア成功候補を詳しく表示
#
# 今回の本命。
# 成功1日前にScore 0～5だった銘柄を見る。
# ============================================================

def print_low_score_winners(
    success_precursors,
):

    print()
    print("=" * 120)
    print(
        "=== 成功1営業日前：初動スコア5点以下 ==="
    )
    print("=" * 120)

    part = success_precursors[
        (
            success_precursors[
                "何営業日前"
            ]
            == 1
        )
        &
        (
            pd.to_numeric(
                success_precursors[
                    "初動スコア"
                ],
                errors="coerce",
            )
            <= 5
        )
    ].copy()

    if part.empty:

        print("該当なし")
        return

    columns = [
        "イベントID",
        "成功基準日",
        "コード",
        "銘柄名",
        "成功Max3",
        "観測日",
        "初動スコア",
        "買い回避",
        "買い回避理由",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "BreakoutSignal",
        "New30High",
    ]

    print(
        part[
            columns
        ]
        .sort_values(
            "成功Max3",
            ascending=False,
        )
        .to_string(
            index=False
        )
    )


# ============================================================
# 買い回避なし低スコア成功
# ============================================================

def print_early_buy_candidates(
    success_precursors,
):

    print()
    print("=" * 120)
    print(
        "=== 早期買い候補：成功1日前 × Score1～5 × 買い回避なし ==="
    )
    print("=" * 120)

    score = pd.to_numeric(
        success_precursors[
            "初動スコア"
        ],
        errors="coerce",
    )

    part = success_precursors[
        (
            success_precursors[
                "何営業日前"
            ]
            == 1
        )
        &
        (
            score >= 1
        )
        &
        (
            score <= 5
        )
        &
        (
            ~success_precursors[
                "買い回避"
            ]
            .map(to_bool)
        )
    ].copy()

    if part.empty:

        print("該当なし")
        return

    columns = [
        "成功基準日",
        "コード",
        "銘柄名",
        "成功Max3",
        "観測日",
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
    ]

    print(
        part[
            columns
        ]
        .sort_values(
            "成功Max3",
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
    print("=" * 120)
    print(
        "成功上昇波 予兆比較バックテスト"
    )
    print("=" * 120)

    panel = load_panel()

    events = build_success_events(
        panel
    )

    print()
    print(
        "Max3 +10%以上を成功と定義"
    )

    print(
        "成功上昇波イベント数 :",
        len(events),
    )

    print(
        "成功銘柄数           :",
        events[
            "コード"
        ].nunique(),
    )

    # --------------------------------------------------------
    # 成功イベント一覧
    # --------------------------------------------------------

    event_columns = [
        "イベントID",
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "買い回避",
        "買い回避理由",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "BreakoutSignal",
        "New30High",
        "Day1",
        "Day2",
        "Day3",
        "Max3",
    ]

    print()
    print("=" * 120)
    print("=== 成功上昇波イベント ===")
    print("=" * 120)

    print(
        events[
            event_columns
        ]
        .sort_values(
            "Max3",
            ascending=False,
        )
        .to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # 予兆
    # --------------------------------------------------------

    success_precursors = (
        build_success_precursors(
            panel,
            events,
        )
    )

    controls = (
        build_control_rows(
            panel,
            success_precursors,
        )
    )

    combined = pd.concat(
        [
            success_precursors,
            controls,
        ],
        ignore_index=True,
    )

    # --------------------------------------------------------
    # 数値比較
    # --------------------------------------------------------

    numeric_summary = (
        numeric_feature_summary(
            combined
        )
    )

    print()
    print("=" * 120)
    print(
        "=== 成功 vs 非成功 数値特徴比較 ==="
    )
    print("=" * 120)

    print(
        numeric_summary.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # bool比較
    # --------------------------------------------------------

    bool_summary = (
        bool_feature_summary(
            combined
        )
    )

    print()
    print("=" * 120)
    print(
        "=== 成功 vs 非成功 シグナル発生率 ==="
    )
    print("=" * 120)

    print(
        bool_summary.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # スコア帯
    # --------------------------------------------------------

    score_summary = (
        score_band_summary(
            combined
        )
    )

    print()
    print("=" * 120)
    print(
        "=== 成功 vs 非成功 スコア帯 ==="
    )
    print("=" * 120)

    print(
        score_summary.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # 本命
    # --------------------------------------------------------

    print_low_score_winners(
        success_precursors
    )

    print_early_buy_candidates(
        success_precursors
    )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    TRACKING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    events.to_csv(
        EVENT_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    combined.to_csv(
        PRECURSOR_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 120)

    print(
        "イベント保存 :",
        EVENT_OUTPUT,
    )

    print(
        "比較データ保存 :",
        PRECURSOR_OUTPUT,
    )

    print("=" * 120)


if __name__ == "__main__":
    main()