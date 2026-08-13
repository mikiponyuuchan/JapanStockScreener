import pandas as pd
from pathlib import Path


file_path = Path("data/jpx_credit/mtdailyk2026081200.xls")

print("ファイル :", file_path)
print("存在     :", file_path.exists())
print()


# Excelファイルのシート一覧
excel = pd.ExcelFile(file_path)

print("シート一覧")
print(excel.sheet_names)
print()


# 各シートの先頭15行を表示
for sheet_name in excel.sheet_names:

    print("=" * 80)
    print(f"シート : {sheet_name}")
    print("=" * 80)

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=None
    )

    print("行数 :", len(df))
    print("列数 :", len(df.columns))
    print()

    print(df.head(15).to_string(index=False, header=False))
    print()