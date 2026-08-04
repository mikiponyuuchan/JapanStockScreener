import pandas as pd
from datetime import datetime
from pathlib import Path


def save_result(df):

    # 保存フォルダ
    folder = Path("results")
    folder.mkdir(exist_ok=True)

    # 日付
    today = datetime.now().strftime("%Y-%m-%d")

    csv_file = folder / f"{today}_stock_result.csv"
    excel_file = folder / f"{today}_stock_result.xlsx"

    # -----------------------------
    # CSV保存
    # -----------------------------
    df.to_csv(
        csv_file,
        index=False,
        encoding="utf-8-sig"
    )

    # -----------------------------
    # Excel保存
    # -----------------------------
    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl"
    ) as writer:

        # 全銘柄
        df.to_excel(
            writer,
            sheet_name="全銘柄",
            index=False
        )

        # TOP20
        top20 = df.sort_values(
            "強気度",
            ascending=False
        ).head(20)

        top20.to_excel(
            writer,
            sheet_name="TOP20",
            index=False
        )

        # 買い候補
        buy_df = df[
            df["総合判定"] == "買い候補"
        ]

        buy_df.to_excel(
            writer,
            sheet_name="買い候補",
            index=False
        )

    print()
    print("CSV保存 :", csv_file)
    print("Excel保存 :", excel_file)