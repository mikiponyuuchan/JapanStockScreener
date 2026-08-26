from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 設定
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
    / "early_buy_candidate_backtest.csv"
)

DETAIL_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "early_buy_candidate_details.csv"
)


# ============================================================
# 成功判定
#
# 今回は「その後3営業日の最大上昇率 Max3」を使用する。
#
# +5%以上
# +10%以上
# +20%以上
#
# をそれぞれ集計する。
# ============================================================

SUCCESS_LEVELS = [
    5.0,
    10.0,
    20.0,
]


# ============================================================
# 列名候補
# ============================================================

COLUMN_ALIASES = {
    "score": [
        "初動スコア",
    ],
    "change5": [
        "5日騰落率",
    ],
    "rsi": [
        "RSI",
    ],
    "volume20": [
        "VolumeRatio20",
    ],
    "ma25dev": [
        "MA25Deviation",
    ],
    "avoid": [
        "買い回避",
    ],
    "avoid_reason": [
        "買い回避理由",
    ],
    "max3": [
        "Max3",
        "成功Max3",
    ],
    "date": [
        "検出日",
        "観測日",
        "日付",
    ],
    "code": [
        "コード",
    ],
    "name": [
        "銘柄名",
    ],
}


# ============================================================
# 列取得
# ============================================================

def find_column(df, key, required=True):

    candidates = COLUMN_ALIASES[key]

    for column in candidates:

        if column in df.columns:
            return column

    if required:
        raise KeyError(
            f"{key} に対応する列がありません。"
            f" 候補={candidates}"
        )

    return None


# ============================================================
# bool変換
# ============================================================

def to_bool_series(series):

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
            "yes",
            "y",
            "○",
        ]
    )


# ============================================================
# 数値変換
# ============================================================

def to_numeric(df, column):

    if column is None:
        return pd.Series(
            np.nan,
            index=df.index,
            dtype=float,
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    )


# ============================================================
# 危険回避判定
#
# H2 は「未成熟」とみなし、
# 今回は危険回避理由から除外して検証する。
#
# 危険判定：
#
# A_STALL
# C_SPIKE
# D_OVERHEAT
# F_DECEL
# ============================================================

def make_danger_avoid(df, reason_column):

    if reason_column is None:

        return pd.Series(
            False,
            index=df.index,
        )

    reasons = (
        df[reason_column]
        .fillna("")
        .astype(str)
    )

    danger = (
        reasons.str.contains(
            "A_STALL",
            regex=False,
        )
        |
        reasons.str.contains(
            "C_SPIKE",
            regex=False,
        )
        |
        reasons.str.contains(
            "D_OVERHEAT",
            regex=False,
        )
        |
        reasons.str.contains(
            "F_DECEL",
            regex=False,
        )
    )

    return danger


# ============================================================
# 条件作成
# ============================================================

def build_conditions(
    score,
    change5,
    rsi,
    volume20,
    ma25dev,
    danger_avoid,
):

    no_danger = ~danger_avoid

    score_3_5 = (
        score.ge(3)
        &
        score.le(5)
    )

    score_3_4 = (
        score.ge(3)
        &
        score.le(4)
    )

    conditions = {
        "A_Score3to5_NoDanger": (
            score_3_5
            &
            no_danger
        ),

        "B_Score3to4_NoDanger": (
            score_3_4
            &
            no_danger
        ),

        "C_B_plus_Change5Positive": (
            score_3_4
            &
            no_danger
            &
            change5.gt(0)
        ),

        "D_C_plus_RSI55to80": (
            score_3_4
            &
            no_danger
            &
            change5.gt(0)
            &
            rsi.ge(55)
            &
            rsi.le(80)
        ),

        "E_C_plus_Volume20gt1": (
            score_3_4
            &
            no_danger
            &
            change5.gt(0)
            &
            volume20.gt(1)
        ),

        "F_C_plus_MA25DevPositive": (
            score_3_4
            &
            no_danger
            &
            change5.gt(0)
            &
            ma25dev.gt(0)
        ),
    }

    return conditions


# ============================================================
# 条件集計
# ============================================================

def summarize_condition(
    condition_name,
    mask,
    df,
    max3,
    success_base,
):

    selected = df.loc[mask].copy()

    selected_max3 = max3.loc[mask]

    valid_max3 = selected_max3.dropna()

    row = {
        "条件": condition_name,
        "候補数": int(mask.sum()),
        "Max3有効件数": int(valid_max3.shape[0]),
    }

    if len(valid_max3) == 0:

        row["Max3平均"] = np.nan
        row["Max3中央値"] = np.nan

        for level in SUCCESS_LEVELS:
            row[f"+{int(level)}%到達件数"] = 0
            row[f"+{int(level)}%到達率"] = np.nan

        row["成功捕捉件数"] = 0
        row["成功捕捉率"] = np.nan

        return row

    row["Max3平均"] = round(
        float(valid_max3.mean()),
        2,
    )

    row["Max3中央値"] = round(
        float(valid_max3.median()),
        2,
    )

    for level in SUCCESS_LEVELS:

        hit_count = int(
            valid_max3.ge(level).sum()
        )

        hit_rate = (
            hit_count
            /
            len(valid_max3)
            *
            100
        )

        row[f"+{int(level)}%到達件数"] = (
            hit_count
        )

        row[f"+{int(level)}%到達率"] = round(
            hit_rate,
            2,
        )

    # --------------------------------------------------------
    # 成功捕捉率
    #
    # success_base = Max3 >= 10%
    #
    # 全成功イベントのうち、
    # この条件で何件拾えたかを見る。
    # --------------------------------------------------------

    success_total = int(
        success_base.sum()
    )

    success_captured = int(
        (
            mask
            &
            success_base
        ).sum()
    )

    row["成功捕捉件数"] = (
        success_captured
    )

    if success_total > 0:

        row["成功捕捉率"] = round(
            success_captured
            /
            success_total
            *
            100,
            2,
        )

    else:

        row["成功捕捉率"] = np.nan

    return row


# ============================================================
# 詳細データ作成
# ============================================================

def build_detail_rows(
    df,
    conditions,
    date_col,
    code_col,
    name_col,
    score_col,
    max3_col,
):

    rows = []

    optional_columns = [
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "BreakoutSignal",
        "New30High",
        "買い回避",
        "買い回避理由",
    ]

    for condition_name, mask in conditions.items():

        selected = df.loc[mask].copy()

        if selected.empty:
            continue

        selected.insert(
            0,
            "条件",
            condition_name,
        )

        keep_columns = [
            "条件",
        ]

        for column in [
            date_col,
            code_col,
            name_col,
            score_col,
            max3_col,
        ]:

            if (
                column is not None
                and
                column in selected.columns
                and
                column not in keep_columns
            ):
                keep_columns.append(column)

        for column in optional_columns:

            if (
                column in selected.columns
                and
                column not in keep_columns
            ):
                keep_columns.append(column)

        rows.append(
            selected[keep_columns]
        )

    if not rows:

        return pd.DataFrame()

    return pd.concat(
        rows,
        ignore_index=True,
    )


# ============================================================
# 表示
# ============================================================

def print_summary(summary):

    print()
    print("=" * 130)
    print(
        "=== 早期買い候補 条件別バックテスト ==="
    )
    print("=" * 130)

    display_columns = [
        "条件",
        "候補数",
        "Max3有効件数",
        "Max3平均",
        "Max3中央値",
        "+5%到達率",
        "+10%到達率",
        "+20%到達率",
        "成功捕捉件数",
        "成功捕捉率",
    ]

    print(
        summary[
            display_columns
        ].to_string(
            index=False
        )
    )


# ============================================================
# 条件説明
# ============================================================

def print_condition_description():

    print()
    print("=" * 130)
    print("=== 条件定義 ===")
    print("=" * 130)

    print(
        "A : Score 3～5 ＆ 危険回避なし"
    )

    print(
        "B : Score 3～4 ＆ 危険回避なし"
    )

    print(
        "C : B ＋ 5日騰落率 > 0"
    )

    print(
        "D : C ＋ RSI 55～80"
    )

    print(
        "E : C ＋ VolumeRatio20 > 1"
    )

    print(
        "F : C ＋ MA25Deviation > 0"
    )

    print()
    print(
        "危険回避対象 : "
        "A_STALL / C_SPIKE / "
        "D_OVERHEAT / F_DECEL"
    )

    print(
        "H2 は今回、危険回避から除外"
    )

    print(
        "成功捕捉率の成功基準 : Max3 >= 10%"
    )


# ============================================================
# main
# ============================================================

def main():

    print("=" * 130)
    print(
        "早期買い候補 全候補バックテスト"
    )
    print("=" * 130)

    if not PANEL_FILE.exists():

        raise FileNotFoundError(
            f"パネルがありません : "
            f"{PANEL_FILE}"
        )

    df = pd.read_csv(
        PANEL_FILE,
        encoding="utf-8-sig",
        low_memory=False,
    )

    print()
    print(
        f"読込 : {PANEL_FILE}"
    )

    print(
        f"行数 : {len(df)}"
    )

    # --------------------------------------------------------
    # 列確認
    # --------------------------------------------------------

    score_col = find_column(
        df,
        "score",
    )

    change5_col = find_column(
        df,
        "change5",
    )

    rsi_col = find_column(
        df,
        "rsi",
    )

    volume20_col = find_column(
        df,
        "volume20",
    )

    ma25dev_col = find_column(
        df,
        "ma25dev",
    )

    avoid_col = find_column(
        df,
        "avoid",
        required=False,
    )

    reason_col = find_column(
        df,
        "avoid_reason",
        required=False,
    )

    max3_col = find_column(
        df,
        "max3",
    )

    date_col = find_column(
        df,
        "date",
        required=False,
    )

    code_col = find_column(
        df,
        "code",
        required=False,
    )

    name_col = find_column(
        df,
        "name",
        required=False,
    )

    # --------------------------------------------------------
    # 数値化
    # --------------------------------------------------------

    score = to_numeric(
        df,
        score_col,
    )

    change5 = to_numeric(
        df,
        change5_col,
    )

    rsi = to_numeric(
        df,
        rsi_col,
    )

    volume20 = to_numeric(
        df,
        volume20_col,
    )

    ma25dev = to_numeric(
        df,
        ma25dev_col,
    )

    max3 = to_numeric(
        df,
        max3_col,
    )

    # --------------------------------------------------------
    # 買い回避情報確認
    # --------------------------------------------------------

    if avoid_col is not None:

        original_avoid = to_bool_series(
            df[avoid_col]
        )

    else:

        original_avoid = pd.Series(
            False,
            index=df.index,
        )

    danger_avoid = make_danger_avoid(
        df,
        reason_col,
    )

    # --------------------------------------------------------
    # H2件数確認
    # --------------------------------------------------------

    if reason_col is not None:

        reason_text = (
            df[reason_col]
            .fillna("")
            .astype(str)
        )

        h2 = reason_text.str.contains(
            "H2",
            regex=False,
        )

    else:

        h2 = pd.Series(
            False,
            index=df.index,
        )

    print()
    print("=" * 130)
    print("=== 買い回避内訳 ===")
    print("=" * 130)

    print(
        f"元の買い回避       : "
        f"{int(original_avoid.sum())}"
    )

    print(
        f"H2                : "
        f"{int(h2.sum())}"
    )

    print(
        f"危険回避4条件     : "
        f"{int(danger_avoid.sum())}"
    )

    # --------------------------------------------------------
    # 条件
    # --------------------------------------------------------

    conditions = build_conditions(
        score=score,
        change5=change5,
        rsi=rsi,
        volume20=volume20,
        ma25dev=ma25dev,
        danger_avoid=danger_avoid,
    )

    # --------------------------------------------------------
    # 成功基準
    #
    # 今回の比較では
    # Max3 >= 10%
    # を成功とする。
    # --------------------------------------------------------

    success_base = (
        max3.ge(10)
        &
        max3.notna()
    )

    print()
    print(
        f"Max3有効件数      : "
        f"{int(max3.notna().sum())}"
    )

    print(
        f"Max3 >= 5%        : "
        f"{int(max3.ge(5).sum())}"
    )

    print(
        f"Max3 >= 10%       : "
        f"{int(max3.ge(10).sum())}"
    )

    print(
        f"Max3 >= 20%       : "
        f"{int(max3.ge(20).sum())}"
    )

    # --------------------------------------------------------
    # 集計
    # --------------------------------------------------------

    summary_rows = []

    for condition_name, mask in conditions.items():

        mask = (
            mask
            .fillna(False)
            .astype(bool)
        )

        row = summarize_condition(
            condition_name=condition_name,
            mask=mask,
            df=df,
            max3=max3,
            success_base=success_base,
        )

        summary_rows.append(row)

    summary = pd.DataFrame(
        summary_rows
    )

    # --------------------------------------------------------
    # 表示
    # --------------------------------------------------------

    print_condition_description()

    print_summary(
        summary
    )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    details = build_detail_rows(
        df=df,
        conditions=conditions,
        date_col=date_col,
        code_col=code_col,
        name_col=name_col,
        score_col=score_col,
        max3_col=max3_col,
    )

    details.to_csv(
        DETAIL_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 130)

    print(
        f"集計保存 : {OUTPUT_FILE}"
    )

    print(
        f"詳細保存 : {DETAIL_FILE}"
    )

    print(
        f"詳細件数 : {len(details)}"
    )

    print("=" * 130)


if __name__ == "__main__":
    main()