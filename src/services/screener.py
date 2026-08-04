import pandas as pd
from pathlib import Path

import config
from services.yahoo_service import get_history
from indicators.technical import add_indicators


def load_stock_list(limit=10):
    """
    普通株のみ読み込む
    """

    file_path = Path(config.DATA_DIR) / "stocks.csv"

    df = pd.read_csv(file_path, dtype={"コード": str})

    # 普通株だけ残す
    normal_markets = [
        "プライム（内国株式）",
        "スタンダード（内国株式）",
        "グロース（内国株式）",
    ]

    df = df[df["市場・商品区分"].isin(normal_markets)]

    print(f"普通株数 : {len(df)}")

    return df.head(limit)


def run_screener(limit=10):
    """
    指定銘柄数を解析し、
    price_data.csv と screening_result.csv を作成する
    """

    stocks = load_stock_list(limit)

    results = []

    for _, stock in stocks.iterrows():

        code = stock["コード"]

        print(f"取得中 : {code}")

        df = get_history(code)

        if df is None:
            print("  データ取得失敗")
            continue

        df = add_indicators(df)

        latest = df.iloc[-1]

        results.append({
            "コード": code,
            "銘柄名": stock["銘柄名"],
            "市場": stock["市場・商品区分"],
            "終値": round(float(latest["Close"]), 2),
            "MA5": round(float(latest["MA5"]), 2) if pd.notna(latest["MA5"]) else None,
            "MA25": round(float(latest["MA25"]), 2) if pd.notna(latest["MA25"]) else None,
            "出来高": int(latest["Volume"]),
            "出来高倍率": round(float(latest["VolumeRatio"]), 2) if pd.notna(latest["VolumeRatio"]) else None,
            "株価上昇": bool(latest["PriceUp"]),
            "5MA上": bool(latest["AboveMA5"]),
        })

    # DataFrame化
    result_df = pd.DataFrame(results)

    # -----------------------------------
    # 全銘柄データ保存
    # -----------------------------------

    price_path = Path(config.DATA_DIR) / "price_data.csv"

    result_df.to_csv(
        price_path,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(f"保存しました : {price_path}")

    # -----------------------------------
    # スクリーニング
    # -----------------------------------

    screening_df = result_df[
        (result_df["出来高倍率"] >= 2)
        & (result_df["株価上昇"])
        & (result_df["5MA上"])
    ]

    # 出来高倍率の高い順
    screening_df = screening_df.sort_values(
        by="出来高倍率",
        ascending=False
    )

    screening_path = Path(config.DATA_DIR) / "screening_result.csv"

    screening_df.to_csv(
        screening_path,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"保存しました : {screening_path}")

    print()
    print("========== スクリーニング結果 ==========")

    if screening_df.empty:
        print("条件に一致する銘柄はありませんでした。")
    else:
        print(screening_df)

    return screening_df