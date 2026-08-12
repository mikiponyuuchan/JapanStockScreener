import time
import pandas as pd

from services.yahoo_service import get_history


PARQUET_FILE = "data/cache/_all_cache.parquet"

TEST_COUNT = 100


def measure(name, func, df):
    start = time.perf_counter()

    result = func(df)

    elapsed = time.perf_counter() - start

    print(
        f"{name:<24} : {elapsed:.6f} 秒"
    )

    return result, elapsed


def add_indicators_profile(df):

    df = df.copy()

    timings = {}

    # ==========================
    # 移動平均
    # ==========================

    start = time.perf_counter()

    df["MA5"] = (
        df["Close"]
        .rolling(5)
        .mean()
        .round(2)
    )

    df["MA25"] = (
        df["Close"]
        .rolling(25)
        .mean()
        .round(2)
    )

    df["MA75"] = (
        df["Close"]
        .rolling(75)
        .mean()
        .round(2)
    )

    timings["移動平均"] = (
        time.perf_counter() - start
    )

    # ==========================
    # 出来高
    # ==========================

    start = time.perf_counter()

    df["VolumeMA5"] = (
        df["Volume"]
        .rolling(5)
        .mean()
        .round()
    )

    df["VolumeMA20"] = (
        df["Volume"]
        .rolling(20)
        .mean()
        .round()
    )

    df["VolumeRatio"] = (
        df["Volume"]
        / df["VolumeMA5"]
    ).round(2)

    df["VolumeRatio20"] = (
        df["Volume"]
        / df["VolumeMA20"]
    ).round(2)

    timings["出来高"] = (
        time.perf_counter() - start
    )

    # ==========================
    # 前日比・騰落率
    # ==========================

    start = time.perf_counter()

    previous_close = (
        df["Close"].shift(1)
    )

    df["PreviousClose"] = previous_close

    df["Change"] = (
        df["Close"]
        - previous_close
    ).round(2)

    df["ChangePercent"] = (
        df["Change"]
        / previous_close
        * 100
    ).round(2)

    close_5 = df["Close"].shift(5)
    close_20 = df["Close"].shift(20)

    df["Change5Days"] = (
        (
            df["Close"]
            - close_5
        )
        / close_5
        * 100
    ).round(2)

    df["Change20Days"] = (
        (
            df["Close"]
            - close_20
        )
        / close_20
        * 100
    ).round(2)

    timings["前日比・騰落率"] = (
        time.perf_counter() - start
    )

    # ==========================
    # 株価位置
    # ==========================

    start = time.perf_counter()

    df["PriceUp"] = (
        df["Close"] > previous_close
    )

    df["AboveMA5"] = (
        df["Close"] > df["MA5"]
    )

    df["AboveMA25"] = (
        df["Close"] > df["MA25"]
    )

    df["AboveMA75"] = (
        df["Close"] > df["MA75"]
    )

    timings["株価位置"] = (
        time.perf_counter() - start
    )

    # ==========================
    # 連続上昇日数
    # ==========================

    start = time.perf_counter()

    up_flag = (
        df["Close"] > previous_close
    )

    up_group = (
        (~up_flag)
        .cumsum()
    )

    df["ConsecutiveUpDays"] = (
        up_flag
        .groupby(up_group)
        .cumsum()
        .astype(int)
    )

    timings["連続上昇日数"] = (
        time.perf_counter() - start
    )

    # ==========================
    # 出来高増加日数
    # ==========================

    start = time.perf_counter()

    volume_flag = (
        df["Volume"] > df["VolumeMA5"]
    )

    volume_group = (
        (~volume_flag)
        .cumsum()
    )

    df["VolumeIncreaseDays"] = (
        volume_flag
        .groupby(volume_group)
        .cumsum()
        .astype(int)
    )

    timings["出来高増加日数"] = (
        time.perf_counter() - start
    )

    # ==========================
    # MACD
    # ==========================

    start = time.perf_counter()

    ema12 = (
        df["Close"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["Close"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = (
        ema12 - ema26
    )

    df["Signal"] = (
        df["MACD"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD_GC"] = (
        (df["MACD"] > df["Signal"])
        &
        (
            df["MACD"].shift(1)
            <=
            df["Signal"].shift(1)
        )
    )

    timings["MACD"] = (
        time.perf_counter() - start
    )

    # ==========================
    # 30日高値
    # ==========================

    start = time.perf_counter()

    df["High30"] = (
        df["High"]
        .rolling(30)
        .max()
        .round(2)
    )

    prev30high = (
        df["High"]
        .shift(1)
        .rolling(30)
        .max()
    )

    df["New30High"] = (
        df["High"] > prev30high
    )

    df["High30Distance"] = (
        (
            df["High30"]
            - df["Close"]
        )
        / df["Close"]
        * 100
    ).round(2)

    timings["30日高値"] = (
        time.perf_counter() - start
    )

    # ==========================
    # 年初来高値
    # ==========================

    start = time.perf_counter()

    df["YearHigh"] = (
        df["High"]
        .rolling(250)
        .max()
        .round(2)
    )

    df["NewYearHigh"] = (
        df["High"] >= df["YearHigh"]
    )

    timings["年初来高値"] = (
        time.perf_counter() - start
    )

    # ==========================
    # RSI
    # ==========================

    start = time.perf_counter()

    delta = (
        df["Close"].diff()
    )

    gain = (
        delta.clip(lower=0)
    )

    loss = (
        -delta.clip(upper=0)
    )

    avg_gain = (
        gain
        .rolling(14)
        .mean()
    )

    avg_loss = (
        loss
        .rolling(14)
        .mean()
    )

    rs = (
        avg_gain
        /
        avg_loss
    )

    df["RSI"] = (
        100
        -
        (
            100
            /
            (1 + rs)
        )
    ).round(2)

    timings["RSI"] = (
        time.perf_counter() - start
    )

    # ==========================
    # ATR
    # ==========================

    start = time.perf_counter()

    high_low = (
        df["High"]
        - df["Low"]
    )

    high_close = (
        df["High"]
        -
        df["Close"].shift(1)
    ).abs()

    low_close = (
        df["Low"]
        -
        df["Close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    df["ATR"] = (
        true_range
        .rolling(14)
        .mean()
        .round(2)
    )

    timings["ATR"] = (
        time.perf_counter() - start
    )

    # ==========================
    # ブレイクアウト
    # ==========================

    start = time.perf_counter()

    previous_high20 = (
        df["High"]
        .shift(1)
        .rolling(20)
        .max()
    )

    df["BreakoutSignal"] = (
        df["Close"] > previous_high20
    )

    previous_signal = (
        df["BreakoutSignal"]
        .shift(1)
        .fillna(False)
        .astype(bool)
    )

    df["BreakoutFirstDay"] = (
        df["BreakoutSignal"]
        &
        (~previous_signal)
    )

    timings["ブレイクアウト"] = (
        time.perf_counter() - start
    )

    return df, timings


def main():

    print("==============================")
    print(" Ver6.15 add_indicators内部速度計測")
    print("==============================")
    print()

    codes = (
        pd.read_parquet(
            PARQUET_FILE,
            columns=["code"]
        )["code"]
        .astype(str)
        .drop_duplicates()
        .head(TEST_COUNT)
        .tolist()
    )

    print(
        f"対象銘柄数 : {len(codes)}"
    )
    print()

    total_times = {}

    success = 0

    for code in codes:

        try:

            df = get_history(
                code,
                period="6mo"
            )

            if df is None or df.empty:
                continue

            _, timings = (
                add_indicators_profile(df)
            )

            for name, value in timings.items():

                total_times[name] = (
                    total_times.get(name, 0.0)
                    + value
                )

            success += 1

        except Exception as e:

            print(
                f"ERROR: {code} / {e}"
            )

    print()
    print("==============================")
    print("計測結果")
    print("==============================")
    print(
        f"成功銘柄数 : {success}"
    )
    print()

    sorted_times = sorted(
        total_times.items(),
        key=lambda x: x[1],
        reverse=True
    )

    for name, total in sorted_times:

        average = (
            total / success
            if success > 0
            else 0
        )

        print(
            f"{name:<24} : "
            f"{total:8.4f} 秒 "
            f"({average:.6f} 秒/銘柄)"
        )

    print()
    print("==============================")
    print("上位から高速化候補を確認します")
    print("==============================")


if __name__ == "__main__":
    main()