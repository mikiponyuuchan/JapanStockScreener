from pathlib import Path

import pandas as pd


# ============================================================
# パス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

RESULTS_DIR = ROOT_DIR / "results"

TRACKING_DIR = (
    ROOT_DIR
    / "data"
    / "tracking"
)

PANEL_OUTPUT = (
    TRACKING_DIR
    / "buy_decision_backtest_panel.csv"
)

PRECURSOR_OUTPUT = (
    TRACKING_DIR
    / "buy_decision_success_precursors.csv"
)


# ============================================================
# 検証期間
# ============================================================

START_DATE = "2026-08-17"
END_DATE = "2026-08-26"


# ============================================================
# 補助関数
# ============================================================

def normalize_code(value):

    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def to_number(value):

    return pd.to_numeric(
        value,
        errors="coerce",
    )


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


def safe_round(value, digits=2):

    value = to_number(value)

    if pd.isna(value):
        return pd.NA

    return round(
        float(value),
        digits,
    )


# ============================================================
# stock_result一覧
# ============================================================

def get_result_files():

    files = sorted(
        RESULTS_DIR.glob(
            "*_stock_result.csv"
        )
    )

    selected = []

    for path in files:

        file_date = path.name[:10]

        if (
            START_DATE
            <= file_date
            <= END_DATE
        ):
            selected.append(path)

    return selected


# ============================================================
# 1日分読み込み
# ============================================================

def load_result_file(path):

    file_date = path.name[:10]

    try:

        df = pd.read_csv(
            path,
            encoding="utf-8-sig",
            dtype={
                "コード": str,
            },
        )

    except Exception as e:

        print(
            f"読込ERROR : "
            f"{path.name} / {e}"
        )

        return None

    required = [
        "コード",
        "銘柄名",
        "終値",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "基本初動スコア",
        "RSI減点",
        "初動スコア",
        "BreakoutSignal",
        "New30High",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "_data_date",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:

        print(
            f"SKIP {file_date} : "
            f"必要列なし {missing}"
        )

        return None

    df["コード"] = (
        df["コード"]
        .map(normalize_code)
    )

    df["_data_date"] = (
        df["_data_date"]
        .astype(str)
        .str[:10]
    )

    # --------------------------------------------------------
    # 重要
    #
    # 8/23のように休日に実行したファイルは、
    # ファイル日付と実際の株価基準日が異なる。
    #
    # 同じ市場データを二重計上しないため、
    # file_date == _data_date の行だけ採用する。
    # --------------------------------------------------------

    valid = df[
        df["_data_date"]
        == file_date
    ].copy()

    if valid.empty:

        data_dates = sorted(
            df["_data_date"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        print(
            f"除外 {file_date} : "
            f"市場データ日={data_dates}"
        )

        return None

    valid["検出日"] = file_date

    return valid


# ============================================================
# 日次パネル作成
# ============================================================

def build_panel():

    files = get_result_files()

    frames = []

    print()
    print("=" * 90)
    print("日次データ読込")
    print("=" * 90)

    for path in files:

        df = load_result_file(
            path
        )

        if df is None:
            continue

        print(
            f"{path.name[:10]} : "
            f"{len(df)}銘柄"
        )

        frames.append(df)

    if not frames:
        return pd.DataFrame()

    panel = pd.concat(
        frames,
        ignore_index=True,
    )

    # --------------------------------------------------------
    # 重複排除
    # --------------------------------------------------------

    panel = (
        panel
        .drop_duplicates(
            subset=[
                "検出日",
                "コード",
            ],
            keep="last",
        )
        .copy()
    )

    # --------------------------------------------------------
    # 数値化
    # --------------------------------------------------------

    numeric_columns = [
        "終値",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "基本初動スコア",
        "RSI減点",
        "初動スコア",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
    ]

    for col in numeric_columns:

        panel[col] = pd.to_numeric(
            panel[col],
            errors="coerce",
        )

    # --------------------------------------------------------
    # bool
    # --------------------------------------------------------

    for col in [
        "BreakoutSignal",
        "New30High",
    ]:

        panel[col] = (
            panel[col]
            .map(to_bool)
        )

    panel = panel.sort_values(
        [
            "コード",
            "検出日",
        ]
    ).reset_index(drop=True)

    return panel


# ============================================================
# 前営業日の値を追加
# ============================================================

def add_previous_values(panel):

    panel = panel.copy()

    grouped = panel.groupby(
        "コード",
        sort=False,
    )

    panel["PREV_CHG1"] = (
        grouped["前日比"]
        .shift(1)
    )

    panel["PREV_SCORE"] = (
        grouped["初動スコア"]
        .shift(1)
    )

    panel["PREV_CLOSE"] = (
        grouped["終値"]
        .shift(1)
    )

    return panel


# ============================================================
# 買い回避
# ============================================================

def calculate_avoid_row(row):

    score = row["初動スコア"]

    chg1 = row["前日比"]
    chg5 = row["5日騰落率"]
    chg20 = row["20日騰落率"]

    rsi = row["RSI"]

    volume_ratio = (
        row["VolumeRatio"]
    )

    volume_ratio20 = (
        row["VolumeRatio20"]
    )

    ma25_dev = (
        row["MA25Deviation"]
    )

    prev_chg1 = (
        row["PREV_CHG1"]
    )

    alerts = []

    # ========================================================
    # A_STALL
    # ========================================================

    if (
        pd.notna(chg20)
        and pd.notna(chg1)
        and pd.notna(rsi)
        and pd.notna(volume_ratio)
        and chg20 >= 25
        and chg1 < 8
        and rsi >= 75
        and volume_ratio <= 2.5
    ):
        alerts.append(
            "A_STALL"
        )

    # ========================================================
    # C_SPIKE
    # ========================================================

    if (
        pd.notna(chg1)
        and pd.notna(chg5)
        and pd.notna(rsi)
        and pd.notna(volume_ratio)
        and chg1 >= 12
        and chg5 < 15
        and rsi < 60
        and volume_ratio >= 4
    ):
        alerts.append(
            "C_SPIKE"
        )

    # ========================================================
    # D_OVERHEAT
    # ========================================================

    d_overheat = False

    if (
        pd.notna(rsi)
        and pd.notna(chg5)
        and rsi >= 95
        and chg5 >= 40
    ):
        d_overheat = True

    if (
        pd.notna(ma25_dev)
        and ma25_dev >= 80
    ):
        d_overheat = True

    if d_overheat:

        alerts.append(
            "D_OVERHEAT"
        )

    # ========================================================
    # F_DECEL
    # ========================================================

    if (
        pd.notna(prev_chg1)
        and pd.notna(chg1)
        and prev_chg1 >= 10
        and chg1 < 8
    ):
        alerts.append(
            "F_DECEL"
        )

    # ========================================================
    # H2
    # ========================================================

    if (
        pd.notna(score)
        and pd.notna(volume_ratio20)
        and score <= 2
        and volume_ratio20 < 3
    ):
        alerts.append(
            "H2"
        )

    return alerts


def add_avoid_alerts(panel):

    panel = panel.copy()

    alerts = panel.apply(
        calculate_avoid_row,
        axis=1,
    )

    panel["買い回避理由"] = (
        alerts.map(
            lambda x:
                " / ".join(x)
        )
    )

    panel["買い回避"] = (
        alerts.map(
            lambda x:
                len(x) > 0
        )
    )

    for alert_name in [
        "A_STALL",
        "C_SPIKE",
        "D_OVERHEAT",
        "F_DECEL",
        "H2",
    ]:

        panel[alert_name] = (
            alerts.map(
                lambda x:
                    alert_name in x
            )
        )

    return panel


# ============================================================
# 将来騰落率
#
# 同じ銘柄の次の保存営業日を使う
# ============================================================

def add_future_returns(panel):

    panel = panel.copy()

    grouped = panel.groupby(
        "コード",
        sort=False,
    )

    for day in range(1, 6):

        future_close = (
            grouped["終値"]
            .shift(-day)
        )

        panel[
            f"Day{day}"
        ] = (
            (
                future_close
                / panel["終値"]
                - 1
            )
            * 100
        ).round(2)

    # --------------------------------------------------------
    # Max3は3営業日すべて揃った場合だけ確定
    # --------------------------------------------------------

    complete = (
        panel[
            [
                "Day1",
                "Day2",
                "Day3",
            ]
        ]
        .notna()
        .all(axis=1)
    )

    panel["Max3"] = pd.NA

    panel.loc[
        complete,
        "Max3"
    ] = (
        panel.loc[
            complete,
            [
                "Day1",
                "Day2",
                "Day3",
            ]
        ]
        .max(axis=1)
        .round(2)
    )

    panel["Max3"] = pd.to_numeric(
        panel["Max3"],
        errors="coerce",
    )

    return panel


# ============================================================
# 集計共通
# ============================================================

def summarize(
    name,
    df,
):

    values = (
        pd.to_numeric(
            df["Max3"],
            errors="coerce",
        )
        .dropna()
    )

    if values.empty:
        return None

    return {
        "区分":
            name,

        "件数":
            len(values),

        "Max3平均":
            round(
                values.mean(),
                2,
            ),

        "Max3中央値":
            round(
                values.median(),
                2,
            ),

        "+5%到達率":
            round(
                values.ge(5)
                .mean()
                * 100,
                1,
            ),

        "+10%到達率":
            round(
                values.ge(10)
                .mean()
                * 100,
                1,
            ),

        "+20%到達率":
            round(
                values.ge(20)
                .mean()
                * 100,
                1,
            ),
    }


# ============================================================
# 初動スコア別集計
# ============================================================

def print_score_summary(panel):

    confirmed = panel[
        panel["Max3"]
        .notna()
    ].copy()

    print()
    print("=" * 100)
    print("=== 初動スコア別成績 ===")
    print("=" * 100)

    rows = []

    scores = sorted(
        confirmed[
            "初動スコア"
        ]
        .dropna()
        .unique(),
        reverse=True,
    )

    for score in scores:

        part = confirmed[
            confirmed["初動スコア"]
            == score
        ]

        summary = summarize(
            f"{int(score)}点",
            part,
        )

        if summary is not None:

            rows.append(
                summary
            )

    if rows:

        print(
            pd.DataFrame(
                rows
            ).to_string(
                index=False
            )
        )


# ============================================================
# 買い回避集計
# ============================================================

def print_avoid_summary(panel):

    confirmed = panel[
        panel["Max3"]
        .notna()
    ].copy()

    print()
    print("=" * 100)
    print("=== 買い回避 成績比較 ===")
    print("=" * 100)

    rows = []

    rows.append(
        summarize(
            "買い回避なし",
            confirmed[
                ~confirmed[
                    "買い回避"
                ]
            ],
        )
    )

    rows.append(
        summarize(
            "買い回避あり",
            confirmed[
                confirmed[
                    "買い回避"
                ]
            ],
        )
    )

    rows = [
        row
        for row in rows
        if row is not None
    ]

    if rows:

        print(
            pd.DataFrame(
                rows
            ).to_string(
                index=False
            )
        )

    print()
    print("=" * 100)
    print("=== 買い回避理由別 ===")
    print("=" * 100)

    alert_rows = []

    for alert in [
        "A_STALL",
        "C_SPIKE",
        "D_OVERHEAT",
        "F_DECEL",
        "H2",
    ]:

        part = confirmed[
            confirmed[alert]
        ]

        summary = summarize(
            alert,
            part,
        )

        if summary is not None:

            alert_rows.append(
                summary
            )

    if alert_rows:

        print(
            pd.DataFrame(
                alert_rows
            ).to_string(
                index=False
            )
        )

    else:

        print(
            "該当なし"
        )


# ============================================================
# 高スコア × 買い回避通過
# ============================================================

def print_high_score_summary(panel):

    confirmed = panel[
        panel["Max3"]
        .notna()
    ].copy()

    print()
    print("=" * 100)
    print(
        "=== 初動6・7点 × 買い回避通過 ==="
    )
    print("=" * 100)

    part = confirmed[
        (
            confirmed["初動スコア"]
            >= 6
        )
        &
        (
            ~confirmed["買い回避"]
        )
    ].copy()

    summary = summarize(
        "6・7点 / 回避なし",
        part,
    )

    if summary is not None:

        print(
            pd.DataFrame(
                [summary]
            ).to_string(
                index=False
            )
        )

    print()
    print(
        "個別銘柄"
    )

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "基本初動スコア",
        "RSI減点",
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
    ]

    if part.empty:

        print(
            "該当なし"
        )

    else:

        print(
            part[
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
# 大幅上昇銘柄抽出
# ============================================================

def print_big_winners(panel):

    confirmed = panel[
        panel["Max3"]
        .notna()
    ].copy()

    winners = confirmed[
        confirmed["Max3"]
        >= 10
    ].copy()

    print()
    print("=" * 100)
    print(
        "=== 3営業日以内 +10%以上銘柄 ==="
    )
    print("=" * 100)

    if winners.empty:

        print(
            "該当なし"
        )

        return

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "終値",
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

    print(
        winners[
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
# 成功銘柄の1～3営業日前を逆向きに抽出
#
# 「大きく上がる前に何が見えていたか」
# ============================================================

def build_precursors(panel):

    confirmed = panel[
        panel["Max3"]
        .notna()
    ].copy()

    # --------------------------------------------------------
    # 成功イベント
    #
    # まず +10%以上を対象にする
    # --------------------------------------------------------

    winners = confirmed[
        confirmed["Max3"]
        >= 10
    ].copy()

    precursor_rows = []

    panel_by_code = {
        code:
            group.reset_index(
                drop=True
            )
        for code, group
        in panel.groupby(
            "コード",
            sort=False,
        )
    }

    for _, winner in winners.iterrows():

        code = winner["コード"]

        history = panel_by_code.get(
            code
        )

        if history is None:
            continue

        winner_date = (
            winner["検出日"]
        )

        matches = history.index[
            history["検出日"]
            == winner_date
        ].tolist()

        if not matches:
            continue

        winner_index = matches[0]

        for lead in [
            3,
            2,
            1,
            0,
        ]:

            source_index = (
                winner_index
                - lead
            )

            if source_index < 0:
                continue

            source = (
                history.iloc[
                    source_index
                ]
            )

            precursor_rows.append({

                "成功基準日":
                    winner_date,

                "成功コード":
                    code,

                "成功銘柄名":
                    winner[
                        "銘柄名"
                    ],

                "成功Max3":
                    winner[
                        "Max3"
                    ],

                "何営業日前":
                    lead,

                "観測日":
                    source[
                        "検出日"
                    ],

                "終値":
                    source[
                        "終値"
                    ],

                "基本初動スコア":
                    source[
                        "基本初動スコア"
                    ],

                "RSI減点":
                    source[
                        "RSI減点"
                    ],

                "初動スコア":
                    source[
                        "初動スコア"
                    ],

                "買い回避":
                    source[
                        "買い回避"
                    ],

                "買い回避理由":
                    source[
                        "買い回避理由"
                    ],

                "PREV_CHG1":
                    source[
                        "PREV_CHG1"
                    ],

                "前日比":
                    source[
                        "前日比"
                    ],

                "5日騰落率":
                    source[
                        "5日騰落率"
                    ],

                "20日騰落率":
                    source[
                        "20日騰落率"
                    ],

                "RSI":
                    source[
                        "RSI"
                    ],

                "VolumeRatio":
                    source[
                        "VolumeRatio"
                    ],

                "VolumeRatio20":
                    source[
                        "VolumeRatio20"
                    ],

                "MA25Deviation":
                    source[
                        "MA25Deviation"
                    ],

                "BreakoutSignal":
                    source[
                        "BreakoutSignal"
                    ],

                "New30High":
                    source[
                        "New30High"
                    ],
            })

    return pd.DataFrame(
        precursor_rows
    )


# ============================================================
# 成功前予兆を表示
# ============================================================

def print_precursors(
    precursors
):

    print()
    print("=" * 110)
    print(
        "=== +10%以上成功銘柄 3営業日前からの状態 ==="
    )
    print("=" * 110)

    if precursors.empty:

        print(
            "該当なし"
        )

        return

    columns = [
        "成功基準日",
        "成功コード",
        "成功銘柄名",
        "成功Max3",
        "何営業日前",
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
        precursors[
            columns
        ]
        .sort_values(
            [
                "成功基準日",
                "成功コード",
                "何営業日前",
            ],
            ascending=[
                True,
                True,
                False,
            ],
        )
        .to_string(
            index=False
        )
    )


# ============================================================
# 何日前からスコアが上がったか
# ============================================================

def print_early_signal_summary(
    precursors
):

    if precursors.empty:
        return

    print()
    print("=" * 100)
    print(
        "=== 成功銘柄 事前スコア分布 ==="
    )
    print("=" * 100)

    rows = []

    for lead in [
        3,
        2,
        1,
        0,
    ]:

        part = precursors[
            precursors[
                "何営業日前"
            ]
            == lead
        ].copy()

        if part.empty:
            continue

        scores = pd.to_numeric(
            part[
                "初動スコア"
            ],
            errors="coerce",
        )

        rows.append({

            "何営業日前":
                lead,

            "件数":
                len(part),

            "平均スコア":
                round(
                    scores.mean(),
                    2,
                ),

            "中央値":
                round(
                    scores.median(),
                    2,
                ),

            "3点以上率":
                round(
                    scores.ge(3)
                    .mean()
                    * 100,
                    1,
                ),

            "5点以上率":
                round(
                    scores.ge(5)
                    .mean()
                    * 100,
                    1,
                ),

            "6点以上率":
                round(
                    scores.ge(6)
                    .mean()
                    * 100,
                    1,
                ),

            "買い回避なし率":
                round(
                    (
                        ~part[
                            "買い回避"
                        ]
                    )
                    .mean()
                    * 100,
                    1,
                ),
        })

    print(
        pd.DataFrame(
            rows
        ).to_string(
            index=False
        )
    )


# ============================================================
# 特定銘柄確認
#
# 弁護士ドットコム等が期間内にどう推移したか
# ============================================================

def print_watch_codes(panel):

    watch_codes = [
        "6027",
        "3189",
        "3054",
    ]

    print()
    print("=" * 110)
    print(
        "=== 注目3銘柄 日次推移 ==="
    )
    print("=" * 110)

    columns = [
        "検出日",
        "コード",
        "銘柄名",
        "終値",
        "基本初動スコア",
        "RSI減点",
        "初動スコア",
        "買い回避",
        "買い回避理由",
        "PREV_CHG1",
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

    work = panel[
        panel["コード"]
        .isin(
            watch_codes
        )
    ]

    if work.empty:

        print(
            "該当なし"
        )

        return

    print(
        work[
            columns
        ]
        .sort_values(
            [
                "コード",
                "検出日",
            ]
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
    print("=" * 100)
    print(
        "買い判断バックテスト"
    )
    print("=" * 100)

    print(
        f"期間 : "
        f"{START_DATE} ～ {END_DATE}"
    )

    panel = build_panel()

    if panel.empty:

        print(
            "分析対象がありません。"
        )

        return

    panel = add_previous_values(
        panel
    )

    panel = add_avoid_alerts(
        panel
    )

    panel = add_future_returns(
        panel
    )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    TRACKING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    panel.to_csv(
        PANEL_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 基本情報
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("=== バックテスト概要 ===")
    print("=" * 100)

    dates = sorted(
        panel[
            "検出日"
        ].unique()
    )

    print(
        "採用営業日数 :",
        len(dates)
    )

    print(
        "採用営業日     :",
        " / ".join(
            dates
        )
    )

    print(
        "延べ銘柄数     :",
        len(panel)
    )

    print(
        "銘柄数         :",
        panel[
            "コード"
        ].nunique()
    )

    print(
        "Max3確定件数   :",
        panel[
            "Max3"
        ].notna()
        .sum()
    )

    # --------------------------------------------------------
    # 各種集計
    # --------------------------------------------------------

    print_score_summary(
        panel
    )

    print_avoid_summary(
        panel
    )

    print_high_score_summary(
        panel
    )

    print_big_winners(
        panel
    )

    # --------------------------------------------------------
    # 成功銘柄遡及分析
    # --------------------------------------------------------

    precursors = (
        build_precursors(
            panel
        )
    )

    precursors.to_csv(
        PRECURSOR_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print_precursors(
        precursors
    )

    print_early_signal_summary(
        precursors
    )

    print_watch_codes(
        panel
    )

    print()
    print("=" * 100)

    print(
        "パネル保存 :",
        PANEL_OUTPUT
    )

    print(
        "予兆保存   :",
        PRECURSOR_OUTPUT
    )

    print("=" * 100)


if __name__ == "__main__":
    main()