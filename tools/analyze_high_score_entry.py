from pathlib import Path
import sys

import pandas as pd
import yfinance as yf


# ================================================
# パス設定
# ================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT_DIR / "results"
OUTPUT_DIR = ROOT_DIR / "data" / "analysis"

OUTPUT_FILE = OUTPUT_DIR / "high_score_entry_panel.csv"

START_DATE = "2026-08-17"
END_DATE = "2026-08-27"


# ================================================
# 保存済みスクリーナー結果から
# 初動スコア6・7の初回検出を取得
# ================================================

def load_detection_rows():

    rows = []

    for file_path in sorted(
        RESULT_DIR.glob("*_stock_result.csv")
    ):

        detection_date = file_path.name[:10]

        if not (
            START_DATE
            <= detection_date
            <= END_DATE
        ):
            continue

        try:
            df = pd.read_csv(
                file_path,
                dtype={"コード": str}
            )
        except Exception as e:
            print(
                f"CSV読込ERROR : "
                f"{file_path.name} / {e}"
            )
            continue

        if "初動スコア" not in df.columns:
            continue

        work = df[
            df["初動スコア"].isin([6, 7])
        ].copy()

        if work.empty:
            continue

        work["DetectionDate"] = pd.Timestamp(
            detection_date
        )

        rows.append(work)

    if not rows:
        return pd.DataFrame()

    all_df = pd.concat(
        rows,
        ignore_index=True
    )

    all_df["コード"] = (
        all_df["コード"]
        .astype(str)
        .str.strip()
    )

    all_df = all_df.sort_values(
        [
            "コード",
            "DetectionDate",
        ]
    )

    # 同一銘柄は最初に6・7点へ到達した日だけ採用
    first_df = all_df.drop_duplicates(
        subset=["コード"],
        keep="first"
    ).copy()

    first_df = first_df.sort_values(
        [
            "DetectionDate",
            "初動スコア",
        ],
        ascending=[True, False]
    )

    return first_df.reset_index(drop=True)


# ================================================
# Yahooから日足取得
# ================================================

def download_history(code):

    ticker = f"{code}.T"

    try:
        df = yf.Ticker(ticker).history(
            start="2026-06-01",
            end="2026-09-10",
            auto_adjust=False
        )
    except Exception as e:
        print(
            f"Yahoo ERROR : {code} / {e}"
        )
        return None

    if df is None or df.empty:
        return None

    df = df.reset_index()

    if "Date" not in df.columns:
        return None

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    if df["Date"].dt.tz is not None:
        df["Date"] = (
            df["Date"]
            .dt.tz_localize(None)
        )

    df = (
        df
        .dropna(subset=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )

    return df


# ================================================
# 騰落率
# ================================================

def pct_change(price, base):

    try:
        price = float(price)
        base = float(base)

        if base == 0:
            return None

        return round(
            (price / base - 1.0) * 100.0,
            2
        )

    except Exception:
        return None


# ================================================
# 1銘柄のDay1～Day5を作成
# ================================================

def build_future_row(row, history):

    detection_date = pd.Timestamp(
        row["DetectionDate"]
    ).normalize()

    history = history.copy()

    history["DateOnly"] = (
        history["Date"].dt.normalize()
    )

    detection_rows = history[
        history["DateOnly"] == detection_date
    ]

    if detection_rows.empty:
        return None

    detection_index = (
        detection_rows.index[0]
    )

    try:
        base_price = float(row["終値"])
    except Exception:
        return None

    detection_daily = history.loc[detection_index]

    # Previous 20 / 30 trading-day highs
    # Detection day itself is excluded.
    prev_history = history.iloc[:detection_index]

    prev20_high = None
    prev30_high = None

    if len(prev_history) >= 20:
        prev20_high = (
            prev_history["High"]
            .tail(20)
            .max()
        )

    if len(prev_history) >= 30:
        prev30_high = (
            prev_history["High"]
            .tail(30)
            .max()
        )

    detection_high = detection_daily.get("High")
    detection_close = detection_daily.get("Close")

    breakout20_pct = None
    new30_high_pct = None
    close_vs30_high_pct = None

    if (
        prev20_high is not None
        and pd.notna(prev20_high)
        and pd.notna(detection_close)
        and float(prev20_high) != 0
    ):
        breakout20_pct = (
            float(detection_close)
            / float(prev20_high)
            - 1.0
        ) * 100.0

    if (
        prev30_high is not None
        and pd.notna(prev30_high)
        and float(prev30_high) != 0
    ):
        if pd.notna(detection_high):
            new30_high_pct = (
                float(detection_high)
                / float(prev30_high)
                - 1.0
            ) * 100.0

        if pd.notna(detection_close):
            close_vs30_high_pct = (
                float(detection_close)
                / float(prev30_high)
                - 1.0
            ) * 100.0

    # Derived previous-high metrics

    pre1_close = None

    if detection_index >= 1:
        pre1_close = history.iloc[
            detection_index - 1
        ].get("Close")

    room_to20_high_pct = None
    room_to30_high_pct = None
    high_to_close_fade = None
    resistance_gap_pct = None

    if (
        pre1_close is not None
        and pd.notna(pre1_close)
        and float(pre1_close) != 0
    ):
        if (
            prev20_high is not None
            and pd.notna(prev20_high)
        ):
            room_to20_high_pct = (
                float(prev20_high)
                / float(pre1_close)
                - 1.0
            ) * 100.0

        if (
            prev30_high is not None
            and pd.notna(prev30_high)
        ):
            room_to30_high_pct = (
                float(prev30_high)
                / float(pre1_close)
                - 1.0
            ) * 100.0

    if (
        new30_high_pct is not None
        and close_vs30_high_pct is not None
    ):
        high_to_close_fade = (
            close_vs30_high_pct
            - new30_high_pct
        )

    if (
        prev20_high is not None
        and prev30_high is not None
        and pd.notna(prev20_high)
        and pd.notna(prev30_high)
        and float(prev20_high) != 0
    ):
        resistance_gap_pct = (
            float(prev30_high)
            / float(prev20_high)
            - 1.0
        ) * 100.0

    result = {
        "DetectionDate": detection_date,
        "Code": row["コード"],
        "Name": row.get("銘柄名"),
        "BasePrice": base_price,
        "DetectionOpen": detection_daily.get("Open"),
        "DetectionHigh": detection_daily.get("High"),
        "DetectionLow": detection_daily.get("Low"),
        "DetectionClose": detection_daily.get("Close"),
        "Prev20High": prev20_high,
        "Prev30High": prev30_high,
        "Breakout20Pct": breakout20_pct,
        "New30HighPct": new30_high_pct,
        "CloseVs30HighPct": close_vs30_high_pct,
        "RoomTo20HighPct": room_to20_high_pct,
        "RoomTo30HighPct": room_to30_high_pct,
        "HighToCloseFade": high_to_close_fade,
        "ResistanceGapPct": resistance_gap_pct,
        "InitialScore": row.get("初動スコア"),
        "Change1": row.get("前日比"),
        "Change5": row.get("5日騰落率"),
        "Change20": row.get("20日騰落率"),
        "VolumeRatio": row.get("VolumeRatio"),
        "VolumeRatio20": row.get(
            "VolumeRatio20"
        ),
        "RSI": row.get("RSI"),
        "ATR": row.get("ATR"),
        "MA25Deviation": row.get(
            "MA25Deviation"
        ),
        "BreakoutSignal": row.get(
            "BreakoutSignal"
        ),
        "New30High": row.get(
            "New30High"
        ),
    }

    # --------------------------------------------
    # Pre5-Pre1 OHLCV
    # Pre1 = detection day previous trading day
    # --------------------------------------------

    for pre_day in range(5, 0, -1):

        target_index = detection_index - pre_day
        prefix = f"Pre{pre_day}"

        if target_index < 0:

            result[f"{prefix}Date"] = None
            result[f"{prefix}Open"] = None
            result[f"{prefix}High"] = None
            result[f"{prefix}Low"] = None
            result[f"{prefix}Close"] = None
            result[f"{prefix}Volume"] = None

            continue

        daily = history.iloc[target_index]

        result[f"{prefix}Date"] = daily["DateOnly"]

        for price_name in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:
            result[f"{prefix}{price_name}"] = daily.get(
                price_name
            )

    # --------------------------------------------
    # Day1～Day5 OHLC
    # --------------------------------------------

    for day in range(1, 6):

        target_index = detection_index + day

        prefix = f"Day{day}"

        if target_index >= len(history):

            result[f"{prefix}Date"] = None
            result[f"{prefix}Open"] = None
            result[f"{prefix}High"] = None
            result[f"{prefix}Low"] = None
            result[f"{prefix}Close"] = None

            result[f"{prefix}OpenPct"] = None
            result[f"{prefix}HighPct"] = None
            result[f"{prefix}LowPct"] = None
            result[f"{prefix}ClosePct"] = None

            continue

        daily = history.iloc[target_index]

        result[f"{prefix}Date"] = (
            daily["DateOnly"]
        )

        for price_name in [
            "Open",
            "High",
            "Low",
            "Close",
        ]:

            price = daily.get(price_name)

            result[
                f"{prefix}{price_name}"
            ] = price

            result[
                f"{prefix}{price_name}Pct"
            ] = pct_change(
                price,
                base_price
            )

    return result


# ================================================
# メイン
# ================================================

def main():

    print(
        "=============================="
    )
    print(
        " 高スコア6・7 買い位置研究 "
    )
    print(
        "=============================="
    )

    detections = load_detection_rows()

    if detections.empty:
        print(
            "対象データがありません。"
        )
        return

    print(
        f"初回検出銘柄数 : "
        f"{len(detections)}"
    )

    print(
        "Yahoo日足取得中..."
    )

    output_rows = []

    total = len(detections)

    for number, (_, row) in enumerate(
        detections.iterrows(),
        start=1
    ):

        code = row["コード"]

        history = download_history(code)

        if history is None:
            print(
                f"[{number}/{total}] "
                f"履歴なし : {code}"
            )
            continue

        future_row = build_future_row(
            row,
            history
        )

        if future_row is None:
            print(
                f"[{number}/{total}] "
                f"検出日なし : {code}"
            )
            continue

        output_rows.append(
            future_row
        )

        if (
            number % 10 == 0
            or number == total
        ):
            print(
                f"進捗 : "
                f"{number} / {total}"
            )

    if not output_rows:
        print(
            "分析データを作成できませんでした。"
        )
        return

    panel = pd.DataFrame(
        output_rows
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    panel.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    complete_day5 = (
        panel["Day5Close"]
        .notna()
        .sum()
    )

    print()
    print(
        "=============================="
    )
    print(
        " 作成結果 "
    )
    print(
        "=============================="
    )
    print(
        f"作成件数       : "
        f"{len(panel)}"
    )
    print(
        f"Day5完了件数   : "
        f"{complete_day5}"
    )
    print(
        f"未完了件数     : "
        f"{len(panel) - complete_day5}"
    )
    print(
        f"保存先         : "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()