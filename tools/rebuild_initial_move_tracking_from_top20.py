from pathlib import Path
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

RESULTS_DIR = ROOT_DIR / "results"
TRACKING_DIR = ROOT_DIR / "data" / "tracking"

SOURCE_TRACKING = (
    TRACKING_DIR
    / "initial_move_tracking.csv"
)

OUTPUT_FILE = (
    TRACKING_DIR
    / "initial_move_tracking_rebuilt.csv"
)

TARGET_DATES = [
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
]

TRACKING_DAYS = 10


def normalize_code(value):
    return (
        str(value)
        .replace(".0", "")
        .strip()
    )


def load_stock_result(date_text):

    path = (
        RESULTS_DIR
        / f"{date_text}_stock_result.csv"
    )

    if not path.exists():
        return None

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
            f"ERROR : {path.name} : {e}"
        )
        return None

    if "コード" not in df.columns:
        return None

    if "終値" not in df.columns:
        return None

    df["コード"] = (
        df["コード"]
        .apply(normalize_code)
    )

    df["終値"] = pd.to_numeric(
        df["終値"],
        errors="coerce",
    )

    return df


def build_close_map(date_text):

    df = load_stock_result(
        date_text
    )

    if df is None:
        return {}

    result = {}

    for _, row in df.iterrows():

        code = normalize_code(
            row["コード"]
        )

        close = pd.to_numeric(
            row["終値"],
            errors="coerce",
        )

        if not code:
            continue

        if pd.isna(close):
            continue

        result[code] = float(close)

    return result


def main():

    old_df = pd.read_csv(
        SOURCE_TRACKING,
        encoding="utf-8-sig",
        dtype=str,
    )

    old_df["検出日"] = (
        old_df["検出日"]
        .astype(str)
        .str[:10]
    )

    # --------------------------------------------------
    # 8/18より前の履歴はそのまま保持
    # --------------------------------------------------

    before_df = old_df[
        old_df["検出日"] < "2026-08-18"
    ].copy()

    # --------------------------------------------------
    # 全対象日の終値マップを先に作る
    # --------------------------------------------------

    close_maps = {}

    for date_text in TARGET_DATES:

        close_maps[date_text] = (
            build_close_map(
                date_text
            )
        )

        print(
            f"{date_text} stock_result : "
            f"{len(close_maps[date_text])}銘柄"
        )

    rebuilt_rows = []

    # --------------------------------------------------
    # 各日の確定TOP20を正として再構築
    # --------------------------------------------------

    for index, date_text in enumerate(
        TARGET_DATES
    ):

        top20_path = (
            RESULTS_DIR
            / f"{date_text}_top20.csv"
        )

        if not top20_path.exists():

            print(
                f"SKIP : {top20_path.name}"
            )

            continue

        top20 = pd.read_csv(
            top20_path,
            encoding="utf-8-sig",
            dtype={
                "コード": str,
            },
        )

        print()
        print(
            f"{date_text} TOP20 : "
            f"{len(top20)}銘柄"
        )

        for _, row in top20.iterrows():

            code = normalize_code(
                row.get(
                    "コード",
                    "",
                )
            )

            if not code:
                continue

            name = str(
                row.get(
                    "銘柄名",
                    "",
                )
            )

            base_price = pd.to_numeric(
                row.get(
                    "終値",
                    pd.NA,
                ),
                errors="coerce",
            )

            score = pd.to_numeric(
                row.get(
                    "初動スコア",
                    pd.NA,
                ),
                errors="coerce",
            )

            if pd.isna(base_price):
                continue

            if pd.isna(score):
                continue

            base_price = float(
                base_price
            )

            new_row = {
                "検出日":
                    date_text,

                "コード":
                    code,

                "銘柄名":
                    name,

                "検出時株価":
                    round(
                        base_price,
                        2,
                    ),

                "初動スコア":
                    int(score),
            }

            # ------------------------------------------
            # 次の営業日以降をstock_resultから追跡
            # ------------------------------------------

            for day in range(
                1,
                TRACKING_DAYS + 1,
            ):

                future_index = (
                    index + day
                )

                price_col = (
                    f"{day}日後株価"
                )

                return_col = (
                    f"{day}日後騰落率"
                )

                if future_index >= len(
                    TARGET_DATES
                ):

                    new_row[
                        price_col
                    ] = ""

                    new_row[
                        return_col
                    ] = ""

                    continue

                future_date = (
                    TARGET_DATES[
                        future_index
                    ]
                )

                future_price = (
                    close_maps
                    .get(
                        future_date,
                        {},
                    )
                    .get(
                        code
                    )
                )

                if future_price is None:

                    new_row[
                        price_col
                    ] = ""

                    new_row[
                        return_col
                    ] = ""

                    continue

                new_row[
                    price_col
                ] = round(
                    float(
                        future_price
                    ),
                    2,
                )

                new_row[
                    return_col
                ] = round(
                    (
                        float(
                            future_price
                        )
                        / base_price
                        - 1
                    )
                    * 100,
                    2,
                )

            rebuilt_rows.append(
                new_row
            )

    rebuilt_df = pd.DataFrame(
        rebuilt_rows
    )

    final_df = pd.concat(
        [
            before_df,
            rebuilt_df,
        ],
        ignore_index=True,
    )

    final_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "完全再構築完了 :",
        OUTPUT_FILE
    )

    print(
        "8/18以前保持 :",
        len(before_df)
    )

    print(
        "8/18以降再構築 :",
        len(rebuilt_df)
    )

    print(
        "合計件数 :",
        len(final_df)
    )


if __name__ == "__main__":
    main()