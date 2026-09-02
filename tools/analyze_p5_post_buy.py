from pathlib import Path
import pandas as pd
import yfinance as yf


TRACKING_FILE = Path("data/tracking/p5_tracking.csv")
OUTPUT_DIR = Path("data/analysis")
OUTPUT_FILE = OUTPUT_DIR / "p5_post_buy_panel.csv"

PROSPECTIVE_START = "2026-08-28"

BUY = "\u8cb7\u3044"


def normalize_code(value):
    if pd.isna(value):
        return ""

    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    return code


def to_num(value):
    return pd.to_numeric(
        value,
        errors="coerce",
    )


def pct_change(base, price):
    if (
        pd.isna(base)
        or pd.isna(price)
        or base == 0
    ):
        return pd.NA

    return round(
        (price / base - 1.0) * 100.0,
        2,
    )


def day2_band(value):
    if pd.isna(value):
        return ""

    if value < 0:
        return "<0%"

    if value < 5:
        return "0-5%"

    if value < 10:
        return "5-10%"

    return ">=10%"


def download_history(codes):
    result = {}

    codes = sorted(
        {
            normalize_code(x)
            for x in codes
            if normalize_code(x)
        }
    )

    if not codes:
        return result

    batch_size = 100

    for start in range(
        0,
        len(codes),
        batch_size,
    ):
        batch = codes[
            start:start + batch_size
        ]

        tickers = [
            f"{code}.T"
            for code in batch
        ]

        print(
            "Yahoo:",
            min(
                start + batch_size,
                len(codes),
            ),
            "/",
            len(codes),
        )

        try:
            raw = yf.download(
                tickers=tickers,
                period="3mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
        except Exception as e:
            print(
                "Yahoo batch error:",
                e,
            )
            continue

        for code in batch:
            ticker = f"{code}.T"

            try:
                if isinstance(
                    raw.columns,
                    pd.MultiIndex,
                ):
                    level0 = (
                        raw.columns
                        .get_level_values(0)
                    )

                    if ticker not in level0:
                        continue

                    df = raw[ticker].copy()

                else:
                    if len(batch) != 1:
                        continue

                    df = raw.copy()

                if "Close" not in df.columns:
                    continue

                df = df[
                    ["Open", "High", "Low", "Close", "Volume"]
                ].copy()

                df = df.dropna(
                    subset=["Close"]
                )

                if df.empty:
                    continue

                idx = pd.to_datetime(
                    df.index,
                    errors="coerce",
                )

                try:
                    idx = idx.tz_localize(None)
                except TypeError:
                    try:
                        idx = idx.tz_convert(None)
                    except Exception:
                        pass

                df.index = idx
                df = df[
                    ~df.index.isna()
                ].copy()

                df.index = (
                    pd.DatetimeIndex(df.index)
                    .normalize()
                )

                result[code] = df

            except Exception:
                continue

    return result


def summarize(
    df,
    label,
):
    if df.empty:
        print(
            label,
            ": no rows",
        )
        return

    d3 = pd.to_numeric(
        df["D2toD3"],
        errors="coerce",
    ).dropna()

    d5 = pd.to_numeric(
        df["D2toD5"],
        errors="coerce",
    ).dropna()

    print()
    print(label)
    print("-" * 68)
    print("N           :", len(df))
    print("D3 available:", len(d3))
    print("D5 available:", len(d5))

    if len(d3):
        print(
            "D2->D3 mean  :",
            round(d3.mean(), 2),
        )
        print(
            "D2->D3 median:",
            round(d3.median(), 2),
        )
        print(
            "D2->D3 plus% :",
            round(
                (d3 > 0).mean() * 100,
                1,
            ),
        )

    if len(d5):
        print(
            "D2->D5 mean  :",
            round(d5.mean(), 2),
        )
        print(
            "D2->D5 median:",
            round(d5.median(), 2),
        )
        print(
            "D2->D5 plus% :",
            round(
                (d5 > 0).mean() * 100,
                1,
            ),
        )


def main():
    if not TRACKING_FILE.exists():
        raise FileNotFoundError(
            TRACKING_FILE
        )

    tracking = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig",
        dtype={"Code": str},
    )

    tracking["Code"] = (
        tracking["Code"]
        .map(normalize_code)
    )

    tracking["DetectionDate"] = (
        pd.to_datetime(
            tracking["DetectionDate"],
            errors="coerce",
        )
    )

    tracking["Day1"] = tracking[
        "Day1"
    ].map(to_num)

    tracking["Day2"] = tracking[
        "Day2"
    ].map(to_num)

    tracking["Day2Price"] = tracking[
        "Day2Price"
    ].map(to_num)

    start_date = pd.Timestamp(
        PROSPECTIVE_START
    )

    buys = tracking[
        (tracking["DetectionDate"] >= start_date)
        & (tracking["BuyDecision"] == BUY)
        & tracking["Day2Price"].notna()
    ].copy()

    print("=" * 68)
    print("P5 POST-BUY PROSPECTIVE ANALYSIS")
    print("=" * 68)
    print(
        "Prospective start :",
        PROSPECTIVE_START,
    )
    print(
        "Buy rows          :",
        len(buys),
    )

    if buys.empty:
        return

    history_map = download_history(
        buys["Code"].tolist()
    )

    today = pd.Timestamp.today().normalize()

    rows = []

    for _, row in buys.iterrows():
        code = row["Code"]

        history = history_map.get(code)

        if history is None:
            continue

        detection_date = row[
            "DetectionDate"
        ].normalize()

        confirmed = history[
            (history.index > detection_date)
            & (history.index < today)
        ].copy()

        confirmed = confirmed.sort_index()

        if len(confirmed) < 2:
            continue

        day1_row = confirmed.iloc[0]
        day2_row = confirmed.iloc[1]

        yahoo_day2 = to_num(
            day2_row["Close"]
        )

        day3_price = pd.NA
        day5_price = pd.NA

        day3_date = pd.NaT
        day5_date = pd.NaT

        if len(confirmed) >= 3:
            day3_row = confirmed.iloc[2]
            day3_price = to_num(
                day3_row["Close"]
            )
            day3_date = confirmed.index[2]

        if len(confirmed) >= 5:
            day5_row = confirmed.iloc[4]
            day5_price = to_num(
                day5_row["Close"]
            )
            day5_date = confirmed.index[4]

        stored_day2 = to_num(
            row["Day2Price"]
        )

        stored_vs_yahoo = pct_change(
            yahoo_day2,
            stored_day2,
        )

        rows.append(
            {
                "DetectionDate":
                    detection_date.strftime(
                        "%Y-%m-%d"
                    ),
                "Code":
                    code,
                "Name":
                    row.get("Name", ""),
                "InitialScore":
                    to_num(
                        row.get(
                            "InitialScore"
                        )
                    ),
                "Change5":
                    to_num(
                        row.get("Change5")
                    ),
                "VolumeRatio20":
                    to_num(
                        row.get(
                            "VolumeRatio20"
                        )
                    ),
                "Day1":
                    to_num(row["Day1"]),
                "Day2":
                    to_num(row["Day2"]),
                "Drop":
                    to_num(
                        row.get("Drop")
                    ),
                "Day2Band":
                    day2_band(
                        to_num(row["Day2"])
                    ),
                "BuyReason":
                    row.get(
                        "BuyReason",
                        "",
                    ),
                "StoredDay2Price":
                    stored_day2,
                "YahooDay2Price":
                    yahoo_day2,
                "StoredVsYahooDay2Pct":
                    stored_vs_yahoo,
                "Day3Date":
                    (
                        day3_date.strftime(
                            "%Y-%m-%d"
                        )
                        if pd.notna(day3_date)
                        else ""
                    ),
                "Day3Price":
                    day3_price,
                "D2toD3":
                    pct_change(
                        yahoo_day2,
                        day3_price,
                    ),
                "Day5Date":
                    (
                        day5_date.strftime(
                            "%Y-%m-%d"
                        )
                        if pd.notna(day5_date)
                        else ""
                    ),
                "Day5Price":
                    day5_price,
                "D2toD5":
                    pct_change(
                        yahoo_day2,
                        day5_price,
                    ),
            }
        )

    panel = pd.DataFrame(rows)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    panel.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "Panel rows        :",
        len(panel),
    )
    print(
        "Saved             :",
        OUTPUT_FILE,
    )

    if panel.empty:
        return

    mismatch = pd.to_numeric(
        panel["StoredVsYahooDay2Pct"],
        errors="coerce",
    ).abs()

    print(
        "Day2 diff >0.10%  :",
        int((mismatch > 0.10).sum()),
    )

    summarize(
        panel,
        "ALL BUY",
    )

    print()
    print("=" * 68)
    print("BY DAY2 LEVEL")
    print("=" * 68)

    for band in [
        "<0%",
        "0-5%",
        "5-10%",
        ">=10%",
    ]:
        subset = panel[
            panel["Day2Band"] == band
        ]

        summarize(
            subset,
            band,
        )

    print()
    print("=" * 68)
    print("BY DETECTION DATE")
    print("=" * 68)

    for detection_date in sorted(
        panel["DetectionDate"].unique()
    ):
        subset = panel[
            panel["DetectionDate"]
            == detection_date
        ]

        summarize(
            subset,
            detection_date,
        )


if __name__ == "__main__":
    main()
