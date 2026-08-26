from pathlib import Path
import pandas as pd
import yfinance as yf


ROOT_DIR = Path(__file__).resolve().parents[1]

RESULTS_DIR = ROOT_DIR / "results"

TRACKING_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "initial_move_tracking_rebuilt.csv"
)

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "candle_buy_signal_analysis.csv"
)


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
# Yahoo OHLC取得
# ============================================================

def get_ohlc(code, date_text):

    start = pd.Timestamp(date_text)
    end = start + pd.Timedelta(days=1)

    try:

        df = yf.download(
            f"{code}.T",
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=False,
            progress=False,
            threads=False,
        )

    except Exception:

        return None

    if df.empty:

        return None

    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = (
            df.columns
            .get_level_values(0)
        )

    row = df.iloc[0]

    try:

        return {
            "Open":
                float(row["Open"]),

            "High":
                float(row["High"]),

            "Low":
                float(row["Low"]),

            "Close":
                float(row["Close"]),
        }

    except Exception:

        return None


# ============================================================
# 中央値
# ============================================================

def calculate_median(values):

    if not values:

        return None

    series = pd.Series(
        values,
        dtype=float
    )

    return float(
        series.median()
    )


# ============================================================
# 共通集計
# ============================================================

def summarize_groups(
    df,
    group_column,
    group_order=None,
    title=""
):

    work = df.copy()

    work[
        "3日以内最大騰落率"
    ] = pd.to_numeric(
        work[
            "3日以内最大騰落率"
        ],
        errors="coerce"
    )

    work = work.dropna(
        subset=[
            "3日以内最大騰落率"
        ]
    )

    if work.empty:

        return

    if title:

        print()
        print("=" * 70)
        print(title)
        print("=" * 70)

    if group_order is None:

        group_order = (
            work[group_column]
            .dropna()
            .unique()
            .tolist()
        )

    rows = []

    for group_name in group_order:

        group_df = work[
            work[group_column]
            == group_name
        ]

        if group_df.empty:

            continue

        values = (
            group_df[
                "3日以内最大騰落率"
            ]
            .astype(float)
            .tolist()
        )

        count = len(values)

        rows.append({
            "区分":
                group_name,

            "件数":
                count,

            "Max3平均":
                round(
                    sum(values)
                    / count,
                    2
                ),

            "Max3中央値":
                round(
                    calculate_median(
                        values
                    ),
                    2
                ),

            "+5%到達率":
                round(
                    sum(
                        value >= 5
                        for value
                        in values
                    )
                    / count
                    * 100,
                    1
                ),

            "+10%到達率":
                round(
                    sum(
                        value >= 10
                        for value
                        in values
                    )
                    / count
                    * 100,
                    1
                ),

            "+20%到達率":
                round(
                    sum(
                        value >= 20
                        for value
                        in values
                    )
                    / count
                    * 100,
                    1
                ),
        })

    if not rows:

        return

    summary = pd.DataFrame(
        rows
    )

    print(
        summary.to_string(
            index=False
        )
    )


# ============================================================
# ローソク足集計
# ============================================================

def print_candle_analysis(result):

    work = result.copy()

    work[
        "初動スコア"
    ] = pd.to_numeric(
        work["初動スコア"],
        errors="coerce"
    )

    work[
        "終値位置"
    ] = pd.to_numeric(
        work["終値位置"],
        errors="coerce"
    )

    work[
        "上ヒゲ率"
    ] = pd.to_numeric(
        work["上ヒゲ率"],
        errors="coerce"
    )

    work[
        "高値終値乖離率"
    ] = pd.to_numeric(
        work["高値終値乖離率"],
        errors="coerce"
    )

    # ========================================================
    # 1. 陽線 / 陰線
    # ========================================================

    def candle_type(row):

        if row["陽線"] is True:

            return "陽線"

        if row["陰線"] is True:

            return "陰線"

        return "同値"

    work[
        "ローソク区分"
    ] = work.apply(
        candle_type,
        axis=1
    )

    summarize_groups(
        work,
        "ローソク区分",
        [
            "陽線",
            "陰線",
            "同値",
        ],
        "=== 陽線・陰線 ==="
    )

    # ========================================================
    # 2. 終値位置
    # ========================================================

    def close_position_group(value):

        if pd.isna(value):

            return None

        if value >= 0.75:

            return "0.75以上"

        if value >= 0.50:

            return "0.50-0.75"

        if value >= 0.25:

            return "0.25-0.50"

        return "0.25未満"

    work[
        "終値位置区分"
    ] = work[
        "終値位置"
    ].apply(
        close_position_group
    )

    summarize_groups(
        work,
        "終値位置区分",
        [
            "0.75以上",
            "0.50-0.75",
            "0.25-0.50",
            "0.25未満",
        ],
        "=== 終値位置 ==="
    )

    # ========================================================
    # 3. 上ヒゲ率
    # ========================================================

    def upper_wick_group(value):

        if pd.isna(value):

            return None

        if value < 0.20:

            return "0.20未満"

        if value < 0.40:

            return "0.20-0.40"

        if value < 0.60:

            return "0.40-0.60"

        return "0.60以上"

    work[
        "上ヒゲ区分"
    ] = work[
        "上ヒゲ率"
    ].apply(
        upper_wick_group
    )

    summarize_groups(
        work,
        "上ヒゲ区分",
        [
            "0.20未満",
            "0.20-0.40",
            "0.40-0.60",
            "0.60以上",
        ],
        "=== 上ヒゲ率 ==="
    )

    # ========================================================
    # 4. 高値から終値までの下落率
    #
    # 高値終値乖離率はマイナス値なので
    # 絶対値にして分かりやすく分類する
    # ========================================================

    work[
        "高値からの下落率"
    ] = (
        work[
            "高値終値乖離率"
        ]
        .abs()
    )

    def high_drop_group(value):

        if pd.isna(value):

            return None

        if value < 3:

            return "3%未満"

        if value < 6:

            return "3-6%"

        if value < 10:

            return "6-10%"

        return "10%以上"

    work[
        "高値下落区分"
    ] = work[
        "高値からの下落率"
    ].apply(
        high_drop_group
    )

    summarize_groups(
        work,
        "高値下落区分",
        [
            "3%未満",
            "3-6%",
            "6-10%",
            "10%以上",
        ],
        "=== 高値から終値までの下落率 ==="
    )

    # ========================================================
    # 5. 初動スコア × 終値位置
    #
    # 現時点では
    # 6点以上 / 5点以下
    # ×
    # 終値位置0.75以上 / 0.75未満
    #
    # で比較する
    # ========================================================

    def score_close_group(row):

        score = row[
            "初動スコア"
        ]

        close_position = row[
            "終値位置"
        ]

        if (
            pd.isna(score)
            or
            pd.isna(close_position)
        ):

            return None

        if score >= 6:

            if close_position >= 0.75:

                return (
                    "6点以上 × 高値圏"
                )

            return (
                "6点以上 × 高値圏外"
            )

        if close_position >= 0.75:

            return (
                "5点以下 × 高値圏"
            )

        return (
            "5点以下 × 高値圏外"
        )

    work[
        "スコア終値位置区分"
    ] = work.apply(
        score_close_group,
        axis=1
    )

    summarize_groups(
        work,
        "スコア終値位置区分",
        [
            "6点以上 × 高値圏",
            "6点以上 × 高値圏外",
            "5点以下 × 高値圏",
            "5点以下 × 高値圏外",
        ],
        "=== 初動スコア × 終値位置 ==="
    )


# ============================================================
# メイン
# ============================================================

def main():

    tracking = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
    )

    tracking = tracking[
        tracking["検出日"]
        >=
        "2026-08-18"
    ].copy()

    rows = []

    total = len(
        tracking
    )

    for i, (_, r) in enumerate(
        tracking.iterrows(),
        1,
    ):

        code = normalize_code(
            r["コード"]
        )

        date_text = str(
            r["検出日"]
        )[:10]

        ohlc = get_ohlc(
            code,
            date_text,
        )

        if ohlc is None:

            print(
                f"[{i}/{total}] SKIP "
                f"{date_text} {code}"
            )

            continue

        open_price = (
            ohlc["Open"]
        )

        high_price = (
            ohlc["High"]
        )

        low_price = (
            ohlc["Low"]
        )

        close_price = (
            ohlc["Close"]
        )

        price_range = (
            high_price
            -
            low_price
        )

        body_change = (
            (
                close_price
                /
                open_price
                -
                1
            )
            *
            100
            if open_price != 0
            else pd.NA
        )

        range_pct = (
            (
                high_price
                /
                low_price
                -
                1
            )
            *
            100
            if low_price != 0
            else pd.NA
        )

        high_to_close = (
            (
                close_price
                /
                high_price
                -
                1
            )
            *
            100
            if high_price != 0
            else pd.NA
        )

        if price_range > 0:

            close_position = (
                (
                    close_price
                    -
                    low_price
                )
                /
                price_range
            )

            upper_wick = (
                high_price
                -
                max(
                    open_price,
                    close_price,
                )
            ) / price_range

            lower_wick = (
                min(
                    open_price,
                    close_price,
                )
                -
                low_price
            ) / price_range

            body_ratio = (
                abs(
                    close_price
                    -
                    open_price
                )
                /
                price_range
            )

        else:

            close_position = pd.NA
            upper_wick = pd.NA
            lower_wick = pd.NA
            body_ratio = pd.NA

        future = []

        for day in range(
            1,
            4
        ):

            value = pd.to_numeric(
                r.get(
                    f"{day}日後騰落率"
                ),
                errors="coerce",
            )

            if pd.notna(value):

                future.append(
                    float(value)
                )

        max3 = (
            max(future)
            if len(future) == 3
            else pd.NA
        )

        rows.append({

            "検出日":
                date_text,

            "コード":
                code,

            "銘柄名":
                r["銘柄名"],

            "初動スコア":
                r["初動スコア"],

            "始値":
                round(
                    open_price,
                    2
                ),

            "高値":
                round(
                    high_price,
                    2
                ),

            "安値":
                round(
                    low_price,
                    2
                ),

            "終値":
                round(
                    close_price,
                    2
                ),

            "陽線":
                close_price
                >
                open_price,

            "陰線":
                close_price
                <
                open_price,

            "実体騰落率":
                round(
                    body_change,
                    2
                ),

            "当日値幅率":
                round(
                    range_pct,
                    2
                ),

            "高値終値乖離率":
                round(
                    high_to_close,
                    2
                ),

            "終値位置":
                round(
                    close_position,
                    4
                )
                if pd.notna(
                    close_position
                )
                else "",

            "実体率":
                round(
                    body_ratio,
                    4
                )
                if pd.notna(
                    body_ratio
                )
                else "",

            "上ヒゲ率":
                round(
                    upper_wick,
                    4
                )
                if pd.notna(
                    upper_wick
                )
                else "",

            "下ヒゲ率":
                round(
                    lower_wick,
                    4
                )
                if pd.notna(
                    lower_wick
                )
                else "",

            "3日以内最大騰落率":
                round(
                    max3,
                    2
                )
                if pd.notna(
                    max3
                )
                else "",
        })

        if (
            i % 20 == 0
            or
            i == total
        ):

            print(
                f"進捗 : "
                f"{i} / {total}"
            )

    result = pd.DataFrame(
        rows
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "保存 :",
        OUTPUT_FILE
    )

    print(
        "件数 :",
        len(result)
    )

    # ========================================================
    # 買い判断材料の集計
    # ========================================================

    print_candle_analysis(
        result
    )


if __name__ == "__main__":
    main()