import pandas as pd
from datetime import datetime
from pathlib import Path



def save_result(df):


    # 保存フォルダ

    folder = Path("results")

    folder.mkdir(
        exist_ok=True
    )



    # 日付

    today = (
        datetime.now()
        .strftime("%Y-%m-%d")
    )



    filename = (
        folder
        /
        f"{today}_stock_result.csv"
    )



    # 保存

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig"
    )



    print()
    print(
        "結果保存:",
        filename
    )