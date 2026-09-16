# ================================================
# 楽天 MarketSpeed II RSS 読み取り
# ================================================

import win32com.client as win32


def get_excel_app():
    """
    起動中の Excel を取得する。
    """
    try:
        return win32.GetActiveObject("Excel.Application")
    except Exception as e:
        raise RuntimeError(
            "起動中の Excel を取得できません。"
            "Excel と MarketSpeed II RSS が起動しているか確認してください。"
        ) from e


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

    excel = get_excel_app()
    sheet = excel.ActiveSheet

    values = sheet.Range(
        f"A{start_row}:E{end_row}"
    ).Value

    rows = []

    for row in values:

        code, name, price, change_pct, volume = row

        # コードが空なら未使用行
        if code is None:
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
