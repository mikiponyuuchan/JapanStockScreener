# ================================================
# 楽天 MarketSpeed II RSS 読み取り
# ================================================

import time

import win32com.client as win32


def get_excel_app():
    """
    起動中の Excel を取得する。
    """
    retry_count = 5
    retry_wait = 0.5
    last_error = None

    for attempt in range(
        1,
        retry_count + 1,
    ):
        try:
            return win32.GetActiveObject(
                "Excel.Application"
            )

        except Exception as exc:
            last_error = exc

            if attempt < retry_count:
                time.sleep(retry_wait)

    raise RuntimeError(
        "???? Excel ?????????"
        "Excel ? MarketSpeed II RSS ?"
        "????????????????"
        f" ?????: {last_error}"
    ) from last_error


def get_rss_sheet():
    """
    楽天RSS専用ブック・シートを名前で取得する。

    ActiveWorkbook / ActiveSheet は使用しない。
    """
    retry_count = 5
    retry_wait = 0.5
    last_error = None

    for attempt in range(
        1,
        retry_count + 1,
    ):
        try:
            excel = get_excel_app()

            book = excel.Workbooks.Item(
                "rakuten_rss_h1.xlsx"
            )

            # ???????????????????
            # 1???????????????
            sheet = book.Worksheets.Item(1)

            return sheet

        except Exception as exc:
            last_error = exc

            if attempt < retry_count:
                print(
                    "RSS Excel COM retry "
                    f"{attempt}/{retry_count}"
                )
                time.sleep(retry_wait)

    raise RuntimeError(
        "??RSS??Excel???????"
        "??????? : "
        "rakuten_rss_h1.xlsx / 1?????? "
        f"(5???) : {last_error}"
    ) from last_error


def is_excel_error_value(value):
    """
    Excel COMのエラー値を検出する。

    -2146826259 などの負の巨大整数は
    RSSデータとして扱わない。
    """

    if isinstance(value, (int, float)):
        return value <= -2000000000

    return False


def read_rss_rows(start_row=2, end_row=21):
    """
    楽天RSSライブボードの A:E を読み取る。

    A : コード
    B : 銘柄名
    C : 現在値
    D : 前日比率
    E : 出来高

    空行は除外する。
    """

    sheet = get_rss_sheet()

    values = sheet.Range(
        f"A{start_row}:E{end_row}"
    ).Value

    rows = []

    for row in values:

        code, name, price, change_pct, volume = row

        # コードが空なら未使用行
        if code is None:
            continue

        # RSS式がExcelエラーの場合は
        # 正常データとして返さない。
        if (
            is_excel_error_value(name)
            or is_excel_error_value(price)
            or is_excel_error_value(change_pct)
            or is_excel_error_value(volume)
        ):
            print(
                f"RSS ERROR VALUE : "
                f"{code} "
                f"name={name} "
                f"price={price} "
                f"change={change_pct} "
                f"volume={volume}"
            )
            continue

        # Excel COMではコードがfloatになる場合がある
        try:
            code = str(int(code))
        except (TypeError, ValueError):
            code = str(code)

        rows.append(
            {
                "Code": code,
                "Name": name,
                "Price": price,
                "ChangePercent": change_pct,
                "Volume": volume,
            }
        )

    return rows


def main():

    rows = read_rss_rows()

    print("==============================")
    print(" 楽天RSS Excel 読み取りテスト")
    print("==============================")

    if not rows:
        print("RSSデータがありません。")
        return

    for row in rows:
        print(
            f"{row['Code']} "
            f"{row['Name']} "
            f"現在値={row['Price']} "
            f"前日比={row['ChangePercent']}% "
            f"出来高={row['Volume']}"
        )

    print("------------------------------")
    print(f"取得銘柄数 : {len(rows)}")


if __name__ == "__main__":
    main()
