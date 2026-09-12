import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TRIGGER_DIR = ROOT / "data" / "jpx_short_sale_trigger"

SSR_GAP = -5.0


def normalize_code(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def read_trigger_file(path):
    raw = pd.read_excel(
        path,
        header=None,
    )

    if (
        raw.empty
        or raw.shape[0] < 12
        or raw.shape[1] < 6
    ):
        return pd.DataFrame()

    trade_date = pd.to_datetime(
        raw.iloc[7, 2],
        errors="coerce",
    )

    if pd.isna(trade_date):
        return pd.DataFrame()

    rows = []

    for _, row in raw.iloc[11:].iterrows():
        code = normalize_code(
            row.iloc[1]
        )

        if not code:
            continue

        name = (
            ""
            if pd.isna(row.iloc[2])
            else str(row.iloc[2]).strip()
        )

        trigger_time = (
            ""
            if pd.isna(row.iloc[4])
            else str(row.iloc[4]).strip()
        )

        rows.append(
            {
                "TriggerDate":
                    trade_date.strftime("%Y-%m-%d"),
                "Code":
                    code,
                "Name":
                    name,
                "TriggerTime":
                    trigger_time,
            }
        )

    return pd.DataFrame(rows)


def find_latest_trigger_file():
    files = sorted(
        list(TRIGGER_DIR.glob(
            "*_Triggered_Stocks.xls"
        ))
        + list(TRIGGER_DIR.glob(
            "*_Triggered_Stocks.xlsx"
        ))
    )

    if not files:
        return None

    return files[-1]


def download_prices(codes):
    tickers = [
        f"{code}.T"
        for code in codes
    ]

    if not tickers:
        return {}

    data = yf.download(
        tickers=tickers,
        period="5d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    result = {}

    for code in codes:
        ticker = f"{code}.T"

        try:
            if len(codes) == 1:
                df = data.copy()
            else:
                df = data[ticker].copy()

            df = df.dropna(
                subset=["Open", "Close"],
                how="all",
            )

            if df.empty:
                continue

            result[code] = df

        except Exception:
            continue

    return result


def main():
    path = find_latest_trigger_file()

    if path is None:
        print(
            "No JPX trigger file found."
        )
        return

    trigger = read_trigger_file(path)

    if trigger.empty:
        print(
            "No trigger rows found."
        )
        return

    trigger_date = trigger[
        "TriggerDate"
    ].iloc[0]

    codes = trigger[
        "Code"
    ].astype(str).tolist()

    print("=" * 72)
    print(" SHORT-SALE TRIGGER GD WATCH")
    print("=" * 72)
    print(
        "Run time     :",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )
    print(
        "Trigger date :",
        trigger_date,
    )
    print(
        "Trigger file :",
        path.name,
    )
    print(
        "Trigger count:",
        len(trigger),
    )
    print()

    price_map = download_prices(
        codes
    )

    rows = []

    for _, item in trigger.iterrows():
        code = str(item["Code"])

        df = price_map.get(code)

        if df is None or df.empty:
            continue

        df = df.copy()
        df.index = pd.to_datetime(
            df.index
        )

        after = df[
            df.index.strftime(
                "%Y-%m-%d"
            ) > trigger_date
        ]

        before = df[
            df.index.strftime(
                "%Y-%m-%d"
            ) <= trigger_date
        ]

        if before.empty:
            continue

        prev_close = float(
            before.iloc[-1]["Close"]
        )

        if after.empty:
            trade_open = None
            gap_pct = None
            status = "NOT_OPEN_OR_NO_DATA"
        else:
            trade_open = float(
                after.iloc[0]["Open"]
            )

            gap_pct = (
                trade_open
                / prev_close
                - 1.0
            ) * 100.0

            if gap_pct <= SSR_GAP:
                status = "SSR-Ver1"
            elif gap_pct < 0:
                status = "GD-WATCH"
            else:
                status = "NOT-GD"

        rows.append(
            {
                "Code": code,
                "Name": item["Name"],
                "TriggerTime":
                    item["TriggerTime"],
                "PrevClose":
                    prev_close,
                "Open":
                    trade_open,
                "GapPct":
                    gap_pct,
                "Status":
                    status,
            }
        )

    if not rows:
        print(
            "No price data available."
        )
        return

    out = pd.DataFrame(rows)

    out = out.sort_values(
        "GapPct",
        ascending=True,
        na_position="last",
    )

    # ======================================================
    # SSR-Ver1 candidates first
    # ======================================================

    candidates = out[
        out["GapPct"] <= SSR_GAP
    ].copy()

    unjudged = out[
        out["GapPct"].isna()
    ].copy()

    print()
    print("=" * 72)
    print(" *** SSR-Ver1 CANDIDATES : Gap <= -5% ***")
    print("=" * 72)

    if candidates.empty:
        if not unjudged.empty:
            print(
                " UNJUDGED - today's open is not available yet."
            )
        else:
            print(
                " NONE - no SSR-Ver1 candidate today."
            )
    else:
        candidate_display = candidates[
            [
                "Code",
                "Name",
                "PrevClose",
                "Open",
                "GapPct",
            ]
        ].copy()

        candidate_display["PrevClose"] = (
            candidate_display["PrevClose"].map(
                lambda x: f"{x:.0f}"
            )
        )

        candidate_display["Open"] = (
            candidate_display["Open"].map(
                lambda x: f"{x:.0f}"
            )
        )

        candidate_display["GapPct"] = (
            candidate_display["GapPct"].map(
                lambda x: f"{x:+.2f}%"
            )
        )

        print()
        print(
            candidate_display.to_string(
                index=False
            )
        )

    print()
    print(
        " SSR candidates :",
        len(candidates),
    )
    print(
        " Unjudged       :",
        len(unjudged),
    )
    print("=" * 72)
    print()
    print("ALL TRIGGER STOCKS")
    print("-" * 72)

    display = out.copy()

    display["PrevClose"] = display[
        "PrevClose"
    ].map(
        lambda x:
        f"{x:.0f}"
        if pd.notna(x)
        else "-"
    )

    display["Open"] = display[
        "Open"
    ].map(
        lambda x:
        f"{x:.0f}"
        if pd.notna(x)
        else "-"
    )

    display["GapPct"] = display[
        "GapPct"
    ].map(
        lambda x:
        f"{x:+.2f}%"
        if pd.notna(x)
        else "-"
    )

    print(
        display.to_string(
            index=False
        )
    )



if __name__ == "__main__":
    main()
