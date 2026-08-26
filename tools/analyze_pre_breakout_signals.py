from pathlib import Path

import pandas as pd


# ============================================================
# パス
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

RESULTS_DIR = ROOT_DIR / "results"

CACHE_DIR = (
    ROOT_DIR
    / "data"
    / "cache"
)

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "pre_breakout_signal_analysis.csv"
)


# ============================================================
# 検証対象
#
# target_date は「大きく動いたことを確認した日」
# ============================================================

TARGETS = [
    {
        "code": "6027",
        "name": "弁護士ドットコム",
        "target_date": "2026-08-19",
    },
    {
        "code": "3189",
        "name": "ＡＮＡＰホールディングス",
        "target_date": "2026-08-20",
    },
    {
        "code": "3054",
        "name": "ハイパー",
        "target_date": "2026-08-18",
    },
]


LOOKBACK_DAYS = 10


# ============================================================
# コード正規化
# ============================================================

def normalize_code(value):

    return (
        str(value)
        .replace(".0", "")
        .strip()
    )


# ============================================================
# 数値変換
# ============================================================

def to_number(value):

    return pd.to_numeric(
        value,
        errors="coerce",
    )


# ============================================================
# True / False 変換
# ============================================================

def to_bool(value):

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "yes",
    }


# ============================================================
# 日付別 stock_result 読み込み
# ============================================================

def load_result_file(date_text):

    file_path = (
        RESULTS_DIR
        / f"{date_text}_stock_result.csv"
    )

    if not file_path.exists():
        return None

    try:

        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig",
            dtype={
                "コード": str,
            },
        )

    except Exception as e:

        print(
            f"読込ERROR : "
            f"{file_path.name} / {e}"
        )

        return None

    if "コード" not in df.columns:
        return None

    df["コード"] = (
        df["コード"]
        .map(normalize_code)
    )

    return df


# ============================================================
# キャッシュ株価読み込み
#
# 日付一覧を取得する目的で使用する
# ============================================================

def load_price_history(code):

    file_path = (
        CACHE_DIR
        / f"{code}.csv"
    )

    if not file_path.exists():

        print(
            f"株価キャッシュなし : "
            f"{code}"
        )

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

    except Exception as e:

        print(
            f"株価キャッシュ読込ERROR : "
            f"{code} / {e}"
        )

        return None

    if "Date" not in df.columns:

        print(
            f"Date列なし : {code}"
        )

        return None

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )

    df = (
        df
        .dropna(
            subset=["Date"]
        )
        .sort_values("Date")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# その日のローソク足を取得
# ============================================================

def get_candle_values(
    price_df,
    date_text,
):

    if price_df is None:
        return {}

    target_date = pd.Timestamp(
        date_text
    ).normalize()

    work = price_df[
        price_df["Date"].dt.normalize()
        == target_date
    ]

    if work.empty:
        return {}

    row = work.iloc[-1]

    result = {}

    for column in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]:

        if column in row.index:

            value = to_number(
                row[column]
            )

            if pd.notna(value):
                result[column] = float(
                    value
                )

    return result


# ============================================================
# ローソク足特徴量
# ============================================================

def calculate_candle_features(
    open_price,
    high_price,
    low_price,
    close_price,
):

    result = {
        "足型": "",
        "実体騰落率": pd.NA,
        "終値位置": pd.NA,
        "実体率": pd.NA,
        "上ヒゲ率": pd.NA,
        "下ヒゲ率": pd.NA,
        "高値終値乖離率": pd.NA,
    }

    values = [
        open_price,
        high_price,
        low_price,
        close_price,
    ]

    if any(
        pd.isna(x)
        for x in values
    ):
        return result

    if close_price > open_price:
        result["足型"] = "陽線"

    elif close_price < open_price:
        result["足型"] = "陰線"

    else:
        result["足型"] = "同値"

    if open_price != 0:

        result["実体騰落率"] = (
            (
                close_price
                / open_price
                - 1
            )
            * 100
        )

    if high_price != 0:

        result["高値終値乖離率"] = (
            (
                close_price
                / high_price
                - 1
            )
            * 100
        )

    price_range = (
        high_price
        - low_price
    )

    if price_range <= 0:
        return result

    result["終値位置"] = (
        (
            close_price
            - low_price
        )
        / price_range
    )

    result["実体率"] = (
        abs(
            close_price
            - open_price
        )
        / price_range
    )

    result["上ヒゲ率"] = (
        (
            high_price
            - max(
                open_price,
                close_price,
            )
        )
        / price_range
    )

    result["下ヒゲ率"] = (
        (
            min(
                open_price,
                close_price,
            )
            - low_price
        )
        / price_range
    )

    return result


# ============================================================
# 買い回避アラート判定
#
# 現在使用している条件をそのまま再現
# ============================================================

def calculate_avoid_alerts(
    score,
    chg1,
    chg5,
    chg20,
    rsi,
    volume_ratio,
    volume_ratio20,
    ma25_deviation,
    prev_chg1,
):

    alerts = []

    # --------------------------------------------------------
    # A_STALL
    # 高値圏まで来たのに勢いが弱い
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # C_SPIKE
    # 単日の吹き上がり
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # D_OVERHEAT
    # 極端な過熱
    # --------------------------------------------------------

    d_overheat = False

    if (
        pd.notna(rsi)
        and pd.notna(chg5)
        and rsi >= 95
        and chg5 >= 40
    ):
        d_overheat = True

    if (
        pd.notna(ma25_deviation)
        and ma25_deviation >= 80
    ):
        d_overheat = True

    if d_overheat:
        alerts.append(
            "D_OVERHEAT"
        )

    # --------------------------------------------------------
    # F_DECEL
    # 前日急騰 → 当日急減速
    # --------------------------------------------------------

    if (
        pd.notna(prev_chg1)
        and pd.notna(chg1)
        and prev_chg1 >= 10
        and chg1 < 8
    ):
        alerts.append(
            "F_DECEL"
        )

    # --------------------------------------------------------
    # H2
    # 初動スコア低位 + 20日出来高弱い
    # --------------------------------------------------------

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


# ============================================================
# 1銘柄分析
# ============================================================

def analyze_target(target):

    code = target["code"]
    name = target["name"]

    target_date = pd.Timestamp(
        target["target_date"]
    ).normalize()

    price_df = load_price_history(
        code
    )

    if price_df is None:
        return []

    # --------------------------------------------------------
    # 対象日以前だけを使用
    #
    # 未来の日付を使わない
    # --------------------------------------------------------

    past_dates = (
        price_df[
            price_df["Date"].dt.normalize()
            <= target_date
        ]["Date"]
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
    )

    past_dates = list(
        past_dates.tail(
            LOOKBACK_DAYS + 1
        )
    )

    rows = []

    previous_change = pd.NA

    for date_value in past_dates:

        date_text = (
            pd.Timestamp(
                date_value
            )
            .strftime("%Y-%m-%d")
        )

        result_df = load_result_file(
            date_text
        )

        if result_df is None:
            continue

        stock_row = result_df[
            result_df["コード"]
            == code
        ]

        if stock_row.empty:
            continue

        r = stock_row.iloc[0]

        # ----------------------------------------------------
        # stock_result の数値
        # ----------------------------------------------------

        score = to_number(
            r.get(
                "初動スコア"
            )
        )

        base_score = to_number(
            r.get(
                "基本初動スコア"
            )
        )

        chg1 = to_number(
            r.get(
                "前日比"
            )
        )

        chg5 = to_number(
            r.get(
                "5日騰落率"
            )
        )

        chg20 = to_number(
            r.get(
                "20日騰落率"
            )
        )

        rsi = to_number(
            r.get(
                "RSI"
            )
        )

        volume_ratio = to_number(
            r.get(
                "VolumeRatio"
            )
        )

        volume_ratio20 = to_number(
            r.get(
                "VolumeRatio20"
            )
        )

        ma25_deviation = to_number(
            r.get(
                "MA25Deviation"
            )
        )

        close_saved = to_number(
            r.get(
                "終値"
            )
        )

        # ----------------------------------------------------
        # OHLC
        # ----------------------------------------------------

        candle = get_candle_values(
            price_df,
            date_text,
        )

        open_price = to_number(
            candle.get(
                "Open"
            )
        )

        high_price = to_number(
            candle.get(
                "High"
            )
        )

        low_price = to_number(
            candle.get(
                "Low"
            )
        )

        close_price = to_number(
            candle.get(
                "Close"
            )
        )

        candle_features = (
            calculate_candle_features(
                open_price,
                high_price,
                low_price,
                close_price,
            )
        )

        # ----------------------------------------------------
        # 買い回避
        # ----------------------------------------------------

        alerts = calculate_avoid_alerts(
            score=score,
            chg1=chg1,
            chg5=chg5,
            chg20=chg20,
            rsi=rsi,
            volume_ratio=volume_ratio,
            volume_ratio20=volume_ratio20,
            ma25_deviation=ma25_deviation,
            prev_chg1=previous_change,
        )

        # ----------------------------------------------------
        # 対象日まで何営業日前か
        # ----------------------------------------------------

        days_before = (
            len(past_dates)
            - 1
            - past_dates.index(
                date_value
            )
        )

        # ----------------------------------------------------
        # 対象日の株価との比較
        #
        # これは検証結果用。
        # シグナル判定には使わない。
        # ----------------------------------------------------

        target_price_rows = (
            price_df[
                price_df[
                    "Date"
                ].dt.normalize()
                == target_date
            ]
        )

        future_to_target = pd.NA

        if (
            not target_price_rows.empty
            and pd.notna(close_price)
        ):

            target_close = to_number(
                target_price_rows.iloc[-1]
                .get(
                    "Close"
                )
            )

            if (
                pd.notna(target_close)
                and close_price != 0
            ):

                future_to_target = (
                    (
                        target_close
                        / close_price
                        - 1
                    )
                    * 100
                )

        # ----------------------------------------------------
        # 出力
        # ----------------------------------------------------

        rows.append({

            "対象コード":
                code,

            "対象銘柄":
                name,

            "大幅上昇確認日":
                target["target_date"],

            "日付":
                date_text,

            "何営業日前":
                days_before,

            "終値":
                round(
                    close_saved,
                    2
                )
                if pd.notna(
                    close_saved
                )
                else "",

            "基本初動スコア":
                int(base_score)
                if pd.notna(
                    base_score
                )
                else "",

            "初動スコア":
                int(score)
                if pd.notna(
                    score
                )
                else "",

            "前日比":
                round(
                    chg1,
                    2
                )
                if pd.notna(
                    chg1
                )
                else "",

            "5日騰落率":
                round(
                    chg5,
                    2
                )
                if pd.notna(
                    chg5
                )
                else "",

            "20日騰落率":
                round(
                    chg20,
                    2
                )
                if pd.notna(
                    chg20
                )
                else "",

            "RSI":
                round(
                    rsi,
                    2
                )
                if pd.notna(
                    rsi
                )
                else "",

            "VolumeRatio":
                round(
                    volume_ratio,
                    2
                )
                if pd.notna(
                    volume_ratio
                )
                else "",

            "VolumeRatio20":
                round(
                    volume_ratio20,
                    2
                )
                if pd.notna(
                    volume_ratio20
                )
                else "",

            "MA25Deviation":
                round(
                    ma25_deviation,
                    2
                )
                if pd.notna(
                    ma25_deviation
                )
                else "",

            "BreakoutSignal":
                to_bool(
                    r.get(
                        "BreakoutSignal"
                    )
                ),

            "BreakoutFirstDay":
                to_bool(
                    r.get(
                        "BreakoutFirstDay"
                    )
                ),

            "New30High":
                to_bool(
                    r.get(
                        "New30High"
                    )
                ),

            "InitialMoveSignal":
                to_bool(
                    r.get(
                        "InitialMoveSignal"
                    )
                ),

            "足型":
                candle_features[
                    "足型"
                ],

            "実体騰落率":
                round(
                    candle_features[
                        "実体騰落率"
                    ],
                    2,
                )
                if pd.notna(
                    candle_features[
                        "実体騰落率"
                    ]
                )
                else "",

            "終値位置":
                round(
                    candle_features[
                        "終値位置"
                    ],
                    4,
                )
                if pd.notna(
                    candle_features[
                        "終値位置"
                    ]
                )
                else "",

            "実体率":
                round(
                    candle_features[
                        "実体率"
                    ],
                    4,
                )
                if pd.notna(
                    candle_features[
                        "実体率"
                    ]
                )
                else "",

            "上ヒゲ率":
                round(
                    candle_features[
                        "上ヒゲ率"
                    ],
                    4,
                )
                if pd.notna(
                    candle_features[
                        "上ヒゲ率"
                    ]
                )
                else "",

            "高値終値乖離率":
                round(
                    candle_features[
                        "高値終値乖離率"
                    ],
                    2,
                )
                if pd.notna(
                    candle_features[
                        "高値終値乖離率"
                    ]
                )
                else "",

            "買い回避":
                len(alerts) > 0,

            "買い回避理由":
                " / ".join(
                    alerts
                ),

            "対象日まで騰落率":
                round(
                    future_to_target,
                    2,
                )
                if pd.notna(
                    future_to_target
                )
                else "",
        })

        # ----------------------------------------------------
        # 次の日の F_DECEL 判定用
        # ----------------------------------------------------

        previous_change = chg1

    return rows


# ============================================================
# 表示
# ============================================================

def print_target_table(
    result,
    code,
):

    work = result[
        result["対象コード"]
        == code
    ].copy()

    if work.empty:
        return

    name = (
        work.iloc[0][
            "対象銘柄"
        ]
    )

    print()
    print(
        "=" * 120
    )

    print(
        f"{code} {name}"
    )

    print(
        "=" * 120
    )

    columns = [
        "日付",
        "何営業日前",
        "終値",
        "初動スコア",
        "前日比",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "足型",
        "終値位置",
        "上ヒゲ率",
        "BreakoutSignal",
        "New30High",
        "買い回避理由",
        "対象日まで騰落率",
    ]

    print(
        work[
            columns
        ].to_string(
            index=False
        )
    )


# ============================================================
# main
# ============================================================

def main():

    all_rows = []

    print(
        "=" * 120
    )

    print(
        "成功銘柄 初動予兆遡及分析"
    )

    print(
        "=" * 120
    )

    for target in TARGETS:

        print()
        print(
            "分析開始 : "
            f"{target['code']} "
            f"{target['name']}"
        )

        rows = analyze_target(
            target
        )

        all_rows.extend(
            rows
        )

    result = pd.DataFrame(
        all_rows
    )

    if result.empty:

        print()
        print(
            "分析データがありません。"
        )

        return

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    for target in TARGETS:

        print_target_table(
            result,
            target["code"],
        )

    print()
    print(
        "=" * 120
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
        "=" * 120
    )


if __name__ == "__main__":
    main()