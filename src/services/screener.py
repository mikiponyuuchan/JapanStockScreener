import pandas as pd
from pathlib import Path

import config
from services.yahoo_service import get_history
from indicators.technical import add_indicators


def load_stock_list(start=0, limit=10):
    """
    普通株のみ読み込む
    """

    file_path = Path(config.DATA_DIR) / "stocks.csv"

    df = pd.read_csv(file_path, dtype={"コード": str})

    normal_markets = [
        "プライム（内国株式）",
        "スタンダード（内国株式）",
        "グロース（内国株式）",
    ]

    df = df[df["市場・商品区分"].isin(normal_markets)]

    print(f"普通株数 : {len(df)}")
    print(f"対象 : {start + 1} ～ {start + limit} 銘柄")
    print()

    return df.iloc[start:start + limit].reset_index(drop=True)


def run_screener(start=0, limit=10):

    stocks = load_stock_list(start, limit)

    price_path = Path(config.DATA_DIR) / "price_data.csv"

    # 前回の結果を消して新規作成
    if price_path.exists():
        price_path.unlink()

    total = len(stocks)

    for i, (_, stock) in enumerate(stocks.iterrows(), start=1):

        code = stock["コード"]

        print(f"[{i}/{total}] {code}")

        df = get_history(code)

        if df is None or df.empty:
            print("   データ取得失敗")
            continue

        df = add_indicators(df)

        latest = df.iloc[-1]

        row = pd.DataFrame([{
            "コード": code,
            "銘柄名": stock["銘柄名"],
            "市場": stock["市場・商品区分"],
            "終値": round(float(latest["Close"]), 2),
            "MA5": round(float(latest["MA5"]), 2),
            "MA25": round(float(latest["MA25"]), 2),
            "出来高": int(latest["Volume"]),
            "出来高倍率": round(float(latest["VolumeRatio"]), 2),
            "株価上昇": bool(latest["PriceUp"]),
            "5MA上": bool(latest["AboveMA5"]),
        }])

        row.to_csv(
            price_path,
            mode="a",
            index=False,
            header=not price_path.exists(),
            encoding="utf-8-sig"
        )

    print()
    print("price_data.csv 作成完了")

    # =====================
    # スクリーニング
    # =====================

    result_df = pd.read_csv(price_path)

    screening_df = result_df[
        (result_df["出来高倍率"] >= 2)
        & (result_df["株価上昇"])
        & (result_df["5MA上"])
    ].sort_values(
        "出来高倍率",
        ascending=False
    )

    screening_path = Path(config.DATA_DIR) / "screening_result.csv"

    screening_df.to_csv(
        screening_path,
        index=False,
        encoding="utf-8-sig"
    )

    print("screening_result.csv 作成完了")

    if screening_df.empty:
        print()
        print("条件に一致する銘柄はありませんでした。")
    else:
        print()
        print(screening_df)

    return screening_df