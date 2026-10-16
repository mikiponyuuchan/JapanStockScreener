from pathlib import Path
from datetime import datetime
import csv
import math
import time

import pandas as pd
import win32com.client


ROOT = Path(__file__).resolve().parents[1]

WORKBOOK_NAME = "rakuten_rss_morning.xlsx"
SHEET_NAME = "信用残テスト"

RESULTS_DIR = ROOT / "results"
H1_TRACKING = ROOT / "data" / "tracking" / "h1_top10_tracking.csv"
OUTPUT_DIR = ROOT / "data" / "credit_daily"

RSS_WAIT_SECONDS = 5


HEADERS = [
    "CapturedAt",
    "SelectionDate",
    "Code",
    "Name",

    "InitialTop20",
    "InitialRank",
    "InitialScore",
    "InitialPrice",

    "H1Top10",
    "H1Rank",
    "H1RankGroup",
    "H1Price",
    "H1Change",
    "H1VolumeRatio",
    "H1CxV",

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


def normalize_code(value):
    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    if code.endswith(".T"):
        code = code[:-2]

    return code


def load_initial_top20_files():
    files = sorted(
        RESULTS_DIR.glob("*_top20.csv"),
        reverse=True,
    )

    result = {}

    for path in files:
        try:
            df = pd.read_csv(
                path,
                dtype={"コード": str},
            )
        except Exception:
            continue

        required = {
            "コード",
            "銘柄名",
            "終値",
            "初動スコア",
            "_data_date",
        }

        if not required.issubset(df.columns):
            continue

        dates = (
            df["_data_date"]
            .dropna()
            .astype(str)
            .str[:10]
            .unique()
        )

        if len(dates) != 1:
            continue

        data_date = dates[0]

        result[data_date] = (
            path,
            df.head(20).copy(),
        )

    return result


def load_h1_tracking():
    df = pd.read_csv(
        H1_TRACKING,
        dtype={"Code": str},
    )

    required = {
        "DetectionDate",
        "Code",
        "Name",
        "Rank",
        "RankGroup",
        "SnapshotPrice",
        "Change",
        "VolumeRatio",
        "CxV",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "H1 TOP10 必須列不足 : "
            + ", ".join(sorted(missing))
        )

    df["DetectionDate"] = (
        df["DetectionDate"]
        .astype(str)
        .str[:10]
    )

    return df


def find_common_latest_date(initial_map, h1_df):
    initial_dates = set(initial_map.keys())

    h1_dates = set(
        h1_df["DetectionDate"]
        .dropna()
        .astype(str)
    )

    common = sorted(
        initial_dates & h1_dates
    )

    if not common:
        raise ValueError(
            "初動TOP20とH1 TOP10で共通の日付がありません"
        )

    return common[-1]


def build_selection(initial_df, h1_df, selection_date):
    rows = {}

    # ==========================
    # 初動TOP20
    # ==========================

    for rank, (_, row) in enumerate(
        initial_df.head(20).iterrows(),
        start=1,
    ):
        code = normalize_code(
            row["コード"]
        )

        rows[code] = {
            "SelectionDate": selection_date,
            "Code": code,
            "Name": row["銘柄名"],

            "InitialTop20": True,
            "InitialRank": rank,
            "InitialScore": row["初動スコア"],
            "InitialPrice": row["終値"],

            "H1Top10": False,
            "H1Rank": "",
            "H1RankGroup": "",
            "H1Price": "",
            "H1Change": "",
            "H1VolumeRatio": "",
            "H1CxV": "",
        }

    # ==========================
    # H1 TOP10
    # ==========================

    day_h1 = h1_df[
        h1_df["DetectionDate"]
        == selection_date
    ].copy()

    day_h1["Rank"] = pd.to_numeric(
        day_h1["Rank"],
        errors="coerce",
    )

    day_h1 = (
        day_h1
        .dropna(subset=["Rank"])
        .sort_values("Rank")
        .head(10)
    )

    if len(day_h1) != 10:
        raise ValueError(
            f"H1 TOP10 が10銘柄揃っていません : {len(day_h1)}"
        )

    for _, row in day_h1.iterrows():
        code = normalize_code(
            row["Code"]
        )

        if code not in rows:
            rows[code] = {
                "SelectionDate": selection_date,
                "Code": code,
                "Name": row["Name"],

                "InitialTop20": False,
                "InitialRank": "",
                "InitialScore": "",
                "InitialPrice": "",

                "H1Top10": True,
                "H1Rank": int(row["Rank"]),
                "H1RankGroup": row["RankGroup"],
                "H1Price": row["SnapshotPrice"],
                "H1Change": row["Change"],
                "H1VolumeRatio": row["VolumeRatio"],
                "H1CxV": row["CxV"],
            }

        else:
            rows[code]["H1Top10"] = True
            rows[code]["H1Rank"] = int(
                row["Rank"]
            )
            rows[code]["H1RankGroup"] = (
                row["RankGroup"]
            )
            rows[code]["H1Price"] = (
                row["SnapshotPrice"]
            )
            rows[code]["H1Change"] = (
                row["Change"]
            )
            rows[code]["H1VolumeRatio"] = (
                row["VolumeRatio"]
            )
            rows[code]["H1CxV"] = (
                row["CxV"]
            )

    result = list(rows.values())

    result.sort(
        key=lambda x: (
            0 if x["InitialTop20"] else 1,
            (
                x["InitialRank"]
                if x["InitialRank"] != ""
                else 999
            ),
            (
                x["H1Rank"]
                if x["H1Rank"] != ""
                else 999
            ),
        )
    )

    return result


def write_rss_sheet(sheet, selections):
    count = len(selections)

    # 過去のテスト値・数式をクリア
    sheet.Range("A2:G100").ClearContents()

    for excel_row, item in enumerate(
        selections,
        start=2,
    ):
        rss_code = (
            f'{item["Code"]}.T'
        )

        sheet.Cells(
            excel_row,
            1,
        ).Value = rss_code

        sheet.Cells(
            excel_row,
            2,
        ).Formula = (
            f'=RssMarket($A{excel_row},"銘柄名称")'
        )

        sheet.Cells(
            excel_row,
            3,
        ).Formula = (
            f'=RssMarket($A{excel_row},"信用売残")'
        )

        sheet.Cells(
            excel_row,
            4,
        ).Formula = (
            f'=RssMarket($A{excel_row},"信用売残前日比")'
        )

        sheet.Cells(
            excel_row,
            5,
        ).Formula = (
            f'=RssMarket($A{excel_row},"信用買残")'
        )

        sheet.Cells(
            excel_row,
            6,
        ).Formula = (
            f'=RssMarket($A{excel_row},"信用買残前日比")'
        )

        sheet.Cells(
            excel_row,
            7,
        ).Formula = (
            f'=RssMarket($A{excel_row},"信用倍率")'
        )

    return count



def write_rss_sheet_with_retry(sheet, selections):
    import pywintypes

    max_retries = 20

    for attempt in range(1, max_retries + 1):
        try:
            result = write_rss_sheet(sheet, selections)

            if attempt > 1:
                print(
                    "Credit RSS write recovered "
                    f"after {attempt - 1} retries"
                )

            return result

        except pywintypes.com_error as exc:
            if exc.hresult not in (
                -2147418111,
                -2147417846,
            ):
                raise

            if attempt == max_retries:
                raise

            if attempt == 1:
                print(
                    "Credit RSS Excel busy - retrying..."
                )

            time.sleep(0.5)


def read_rss_rows(sheet, count):
    end_row = count + 1

    return sheet.Range(
        f"A2:G{end_row}"
    ).Value


def main():
    print("==============================")
    print(" 楽天RSS 信用残 統合保存 Ver2")
    print(" 初動TOP20 + H1 TOP10")
    print("==============================")

    initial_map = (
        load_initial_top20_files()
    )

    h1_df = load_h1_tracking()

    selection_date = (
        find_common_latest_date(
            initial_map,
            h1_df,
        )
    )

    top20_path, initial_df = (
        initial_map[selection_date]
    )

    print(
        "対象日       :",
        selection_date,
    )

    print(
        "初動TOP20    :",
        top20_path.name,
    )

    selections = build_selection(
        initial_df,
        h1_df,
        selection_date,
    )

    initial_count = sum(
        1
        for x in selections
        if x["InitialTop20"]
    )

    h1_count = sum(
        1
        for x in selections
        if x["H1Top10"]
    )

    overlap_count = sum(
        1
        for x in selections
        if (
            x["InitialTop20"]
            and x["H1Top10"]
        )
    )

    print(
        "初動TOP20件数 :",
        initial_count,
    )

    print(
        "H1 TOP10件数  :",
        h1_count,
    )

    print(
        "重複銘柄数    :",
        overlap_count,
    )

    print(
        "RSS実取得数   :",
        len(selections),
    )

    # ==========================
    # Excel接続
    # ==========================

    excel = (
        win32com.client
        .GetActiveObject(
            "Excel.Application"
        )
    )

    book = excel.Workbooks.Item(
        WORKBOOK_NAME
    )

    sheet = book.Worksheets.Item(
        SHEET_NAME
    )

    count = write_rss_sheet_with_retry(
        sheet,
        selections,
    )

    excel.Calculate()

    print(
        f"楽天RSS取得待機 : {RSS_WAIT_SECONDS}秒"
    )

    time.sleep(
        RSS_WAIT_SECONDS
    )

    excel.Calculate()

    rss_rows = read_rss_rows(
        sheet,
        count,
    )

    captured_at = (
        datetime.now().astimezone()
    )

    results = []
    errors = []

    for item, rss_row in zip(
        selections,
        rss_rows,
    ):
        (
            rss_code,
            rss_name,
            short_balance,
            short_change,
            long_balance,
            long_change,
            ratio,
        ) = rss_row

        # 楽天RSSでは信用売残が存在しない銘柄などで
        # "-" が返ることがある。
        # 非数値項目は欠損として保存し、銘柄自体は取得成功とする。
        #
        # ただし5項目すべて非数値ならRSS未取得と判断する。
        values = (
            short_balance,
            short_change,
            long_balance,
            long_change,
            ratio,
        )

        if not any(
            is_number(v)
            for v in values
        ):
            errors.append(
                item["Code"]
            )
            continue

        short_balance_value = (
            int(short_balance)
            if is_number(short_balance)
            else ""
        )

        short_change_value = (
            int(short_change)
            if is_number(short_change)
            else ""
        )

        long_balance_value = (
            int(long_balance)
            if is_number(long_balance)
            else ""
        )

        long_change_value = (
            int(long_change)
            if is_number(long_change)
            else ""
        )

        ratio_value = (
            float(ratio)
            if is_number(ratio)
            else ""
        )

        result = {
            "CapturedAt":
                captured_at.isoformat(
                    timespec="seconds"
                ),

            **item,

            "Name":
                rss_name
                if rss_name
                else item["Name"],

            "ShortBalance":
                short_balance_value,

            "ShortChange1D":
                short_change_value,

            "LongBalance":
                long_balance_value,

            "LongChange1D":
                long_change_value,

            "CreditRatio":
                ratio_value,
        }

        results.append(result)

    print()
    print(
        "取得成功 :",
        len(results),
    )

    print(
        "取得失敗 :",
        len(errors),
    )

    if errors:
        print(
            "失敗銘柄 :",
            ", ".join(errors),
        )

    if len(results) != count:
        print()
        print(
            "全銘柄が揃っていないため保存を中止"
        )
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    captured_stamp = captured_at.strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        OUTPUT_DIR
        / (
            f"{selection_date}_"
            f"{captured_stamp}_"
            "credit_daily.csv"
        )
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=HEADERS,
        )

        writer.writeheader()
        writer.writerows(
            results
        )

    print()
    print(
        "CSV保存 :",
        output_path,
    )

    print(
        "保存件数 :",
        len(results),
    )

    print("==============================")


if __name__ == "__main__":
    main()
