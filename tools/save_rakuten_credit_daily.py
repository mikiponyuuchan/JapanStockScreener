from pathlib import Path
from datetime import datetime
import csv
import math

import win32com.client


ROOT = Path(__file__).resolve().parents[1]

WORKBOOK_NAME = "rakuten_rss_morning.xlsx"
SHEET_NAME = "信用残テスト"

OUTPUT_DIR = ROOT / "data" / "credit_daily"

HEADERS = [
    "CapturedAt",
    "EstimatedDataDate",
    "Code",
    "Name",
    "ShortBalance",
    "ShortChange1D",
    "LongBalance",
    "LongChange1D",
    "CreditRatio",
]


def is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def main():

    print("==============================")
    print(" 楽天RSS 信用残 日次保存 Ver1")
    print("==============================")

    excel = win32com.client.GetActiveObject(
        "Excel.Application"
    )

    book = excel.Workbooks.Item(WORKBOOK_NAME)
    sheet = book.Worksheets.Item(SHEET_NAME)

    captured_at = datetime.now().astimezone()

    rows = sheet.Range("A2:G21").Value

    results = []
    errors = []

    for row in rows:

        code, name, short, short_diff, long, long_diff, ratio = row

        if not code:
            continue

        if not all(
            is_number(v)
            for v in (
                short,
                short_diff,
                long,
                long_diff,
                ratio,
            )
        ):
            errors.append(str(code))
            continue

        results.append({
            "CapturedAt": captured_at.isoformat(
                timespec="seconds"
            ),
            # RSSから基準日を直接取得できないため未確定
            "EstimatedDataDate": "",
            "Code": str(code).replace(".T", ""),
            "Name": name,
            "ShortBalance": int(short),
            "ShortChange1D": int(short_diff),
            "LongBalance": int(long),
            "LongChange1D": int(long_diff),
            "CreditRatio": float(ratio),
        })

    print("取得成功 :", len(results))
    print("取得失敗 :", len(errors))

    if errors:
        print("失敗銘柄 :", ", ".join(errors))

    # 欠損した状態で正常な日次ファイルとして保存しない
    if len(results) != 20:
        print("20銘柄が揃っていないため保存を中止")
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        captured_at.strftime("%Y-%m-%d_%H%M%S")
        + "_credit_daily.csv"
    )

    output_path = OUTPUT_DIR / filename

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=HEADERS
        )

        writer.writeheader()
        writer.writerows(results)

    print()
    print("CSV保存 :", output_path)
    print("保存件数 :", len(results))
    print("==============================")


if __name__ == "__main__":
    main()