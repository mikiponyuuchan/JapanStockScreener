from pathlib import Path
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

CANDLE_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "candle_buy_signal_analysis.csv"
)

RESULTS_DIR = ROOT_DIR / "results"

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "high_score_buy_factor_analysis.csv"
)


def normalize_code(value):
    return (
        str(value)
        .replace(".0", "")
        .strip()
    )


def load_stock_result(date_text):
    path = RESULTS_DIR / f"{date_text}_stock_result.csv"

    if not path.exists():
        return None

    try:
        df = pd.read_csv(
            path,
            encoding="utf-8-sig",
            dtype={"コード": str},
        )
    except Exception as e:
        print(
            f"読込ERROR {date_text} : {e}"
        )
        return None

    df["コード"] = (
        df["コード"]
        .apply(normalize_code)
    )

    return df


def to_number(value):
    return pd.to_numeric(
        value,
        errors="coerce",
    )


def get_value(row, column):
    if column not in row.index:
        return pd.NA

    return row[column]


def main():

    if not CANDLE_FILE.exists():
        print(
            "ローソク足分析CSVがありません :",
            CANDLE_FILE,
        )
        return

    candle = pd.read_csv(
        CANDLE_FILE,
        encoding="utf-8-sig",
        dtype={"コード": str},
    )

    candle["コード"] = (
        candle["コード"]
        .apply(normalize_code)
    )

    candle["初動スコア"] = pd.to_numeric(
        candle["初動スコア"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # 今回は初動スコア6・7点だけ
    # --------------------------------------------------------

    candle = candle[
        candle["初動スコア"] >= 6
    ].copy()

    rows = []

    result_cache = {}

    total = len(candle)

    for i, (_, c) in enumerate(
        candle.iterrows(),
        1,
    ):

        date_text = str(
            c["検出日"]
        )[:10]

        code = normalize_code(
            c["コード"]
        )

        if date_text not in result_cache:

            result_cache[date_text] = (
                load_stock_result(
                    date_text
                )
            )

        stock_result = (
            result_cache[
                date_text
            ]
        )

        if stock_result is None:
            print(
                f"SKIP {date_text} {code} "
                f": stock_resultなし"
            )
            continue

        matched = stock_result[
            stock_result["コード"]
            == code
        ]

        if matched.empty:
            print(
                f"SKIP {date_text} {code} "
                f": 銘柄なし"
            )
            continue

        s = matched.iloc[0]

        # ----------------------------------------------------
        # ローソク足
        # ----------------------------------------------------

        open_price = to_number(
            get_value(c, "始値")
        )

        close_price = to_number(
            get_value(c, "終値")
        )

        candle_type = "同値"

        if (
            pd.notna(open_price)
            and pd.notna(close_price)
        ):

            if close_price > open_price:
                candle_type = "陽線"

            elif close_price < open_price:
                candle_type = "陰線"

        # ----------------------------------------------------
        # スコア条件
        # ----------------------------------------------------

        change = to_number(
            get_value(
                s,
                "前日比",
            )
        )

        volume_ratio = to_number(
            get_value(
                s,
                "VolumeRatio",
            )
        )

        volume_ratio20 = to_number(
            get_value(
                s,
                "VolumeRatio20",
            )
        )

        breakout = get_value(
            s,
            "BreakoutSignal",
        )

        new30 = get_value(
            s,
            "New30High",
        )

        # ----------------------------------------------------
        # 直近上昇状況
        # ----------------------------------------------------

        return5 = to_number(
            get_value(
                s,
                "5日騰落率",
            )
        )

        return20 = to_number(
            get_value(
                s,
                "20日騰落率",
            )
        )

        rsi = to_number(
            get_value(
                s,
                "RSI",
            )
        )

        ma25_dev = to_number(
            get_value(
                s,
                "MA25Deviation",
            )
        )

        # ----------------------------------------------------
        # その後の結果
        # ----------------------------------------------------

        day1 = to_number(
            get_value(
                c,
                "1日後騰落率",
            )
        )

        day2 = to_number(
            get_value(
                c,
                "2日後騰落率",
            )
        )

        day3 = to_number(
            get_value(
                c,
                "3日後騰落率",
            )
        )

        max3 = to_number(
            get_value(
                c,
                "3日以内最大騰落率",
            )
        )

        rows.append({

            "検出日":
                date_text,

            "コード":
                code,

            "銘柄名":
                get_value(
                    c,
                    "銘柄名",
                ),

            "初動スコア":
                int(
                    c["初動スコア"]
                ),

            # ------------------------------
            # スコア要因
            # ------------------------------

            "ChangePercent":
                change,

            "VolumeRatio":
                volume_ratio,

            "VolumeRatio20":
                volume_ratio20,

            "BreakoutSignal":
                breakout,

            "New30High":
                new30,

            # ------------------------------
            # 上昇状況
            # ------------------------------

            "5日騰落率":
                return5,

            "20日騰落率":
                return20,

            "RSI":
                rsi,

            "MA25Deviation":
                ma25_dev,

            # ------------------------------
            # ローソク足
            # ------------------------------

            "足型":
                candle_type,

            "実体騰落率":
                get_value(
                    c,
                    "実体騰落率",
                ),

            "終値位置":
                get_value(
                    c,
                    "終値位置",
                ),

            "上ヒゲ率":
                get_value(
                    c,
                    "上ヒゲ率",
                ),

            "高値終値乖離率":
                get_value(
                    c,
                    "高値終値乖離率",
                ),

            # ------------------------------
            # 結果
            # ------------------------------

            "Day1":
                day1,

            "Day2":
                day2,

            "Day3":
                day3,

            "Max3":
                max3,
        })

        if (
            i % 10 == 0
            or i == total
        ):
            print(
                f"進捗 : {i} / {total}"
            )

    result = pd.DataFrame(
        rows
    )

    if result.empty:
        print(
            "分析対象がありません。"
        )
        return

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 100)
    print(
        "初動スコア6・7点 "
        "買い判断要因分析"
    )
    print("=" * 100)

    display_columns = [
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "ChangePercent",
        "VolumeRatio",
        "VolumeRatio20",
        "5日騰落率",
        "20日騰落率",
        "RSI",
        "MA25Deviation",
        "足型",
        "終値位置",
        "上ヒゲ率",
        "Max3",
    ]

    print(
        result[
            display_columns
        ]
        .to_string(
            index=False
        )
    )

    print()
    print(
        "保存 :",
        OUTPUT_FILE,
    )

    print(
        "対象件数 :",
        len(result),
    )


if __name__ == "__main__":
    main()