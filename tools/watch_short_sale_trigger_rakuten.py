from datetime import datetime, date, time as dt_time
from pathlib import Path

import pandas as pd

from rss_ssr_reader import (
    normalize_code,
    row_has_valid_prices,
)


SSR_GAP = -5.0

SSR_VER2_REBOUND_MAX = 1.0
SSR_VER2_LOW_AGE_MAX = 10.0
SSR_VER2_TAKE_PCT = 5.0
SSR_VER2_STOP_PCT = -3.0

ROOT = Path(__file__).resolve().parents[1]
TRIGGER_DIR = ROOT / "data" / "jpx_short_sale_trigger"

SSR_VER2_TRACKING_PATH = (
    "data/tracking/"
    "short_sale_trigger_rebound_ver2.csv"
)


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

    result = pd.DataFrame(rows)

    stocks_path = ROOT / "data" / "stocks.csv"

    if not stocks_path.exists():
        raise RuntimeError(
            f"stocks.csv not found: {stocks_path}"
        )

    stocks = pd.read_csv(
        stocks_path,
        dtype=str,
        low_memory=False,
    )

    normal_markets = [
        "\u30d7\u30e9\u30a4\u30e0\uff08\u5185\u56fd\u682a\u5f0f\uff09",
        "\u30b9\u30bf\u30f3\u30c0\u30fc\u30c9\uff08\u5185\u56fd\u682a\u5f0f\uff09",
        "\u30b0\u30ed\u30fc\u30b9\uff08\u5185\u56fd\u682a\u5f0f\uff09",
    ]

    code_col = stocks.columns[0]
    market_col = stocks.columns[2]

    stocks = stocks[
        stocks[market_col].isin(
            normal_markets
        )
    ].copy()

    domestic_codes = set(
        stocks[code_col]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    original_count = len(result)

    result = result[
        result["Code"].astype(str).isin(
            domestic_codes
        )
    ].copy()

    result = result.reset_index(
        drop=True
    )

    print(
        "SSR trigger original :",
        original_count,
    )
    print(
        "SSR domestic common  :",
        len(result),
    )
    print(
        "SSR excluded         :",
        original_count - len(result),
    )

    return result


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


def parse_rss_time(value):
    """
    Convert Rakuten RSS HH:MM:SS values to
    today's datetime.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, dt_time):
        return datetime.combine(
            date.today(),
            value,
        )

    text = str(value).strip()

    if not text:
        return None

    for fmt in (
        "%H:%M:%S",
        "%H:%M",
    ):
        try:
            parsed = datetime.strptime(
                text,
                fmt,
            )

            return datetime.combine(
                date.today(),
                parsed.time(),
            )

        except ValueError:
            continue

    return None


def scan_row(row):
    """
    Rakuten RSS equivalent of the old
    kabu API scan_code().
    """
    code = normalize_code(
        row.get("Code")
    )

    name = str(
        row.get("Name") or ""
    ).strip()

    prev_close = row.get(
        "PreviousClose"
    )

    open_price = row.get(
        "OpeningPrice"
    )

    open_time = parse_rss_time(
        row.get("OpeningPriceTime")
    )

    if prev_close is None:
        return {
            "Code": code,
            "Name": name,
            "Status": "NO_PREVCLOSE",
            "PrevClose": None,
            "Open": open_price,
            "OpenTime": open_time,
            "GapPct": None,
        }

    try:
        prev_close = float(prev_close)

    except Exception:
        prev_close = 0.0

    try:
        open_price = float(open_price)

    except Exception:
        open_price = 0.0

    if (
        prev_close <= 0
        or open_price <= 0
        or open_time is None
    ):
        return {
            "Code": code,
            "Name": name,
            "Status": "WAITING_OPEN",
            "PrevClose": prev_close,
            "Open": (
                open_price
                if open_price > 0
                else None
            ),
            "OpenTime": open_time,
            "GapPct": None,
        }

    gap_pct = (
        open_price
        / prev_close
        - 1.0
    ) * 100.0

    if gap_pct <= SSR_GAP:
        status = "SSR-Ver1"

    elif gap_pct < 0:
        status = "GD-WATCH"

    else:
        status = "NOT-GD"

    return {
        "Code": code,
        "Name": name,
        "Status": status,
        "PrevClose": prev_close,
        "Open": open_price,
        "OpenTime": open_time,
        "GapPct": gap_pct,
    }


def evaluate_ssr_ver2(
    row,
    trigger_time="",
):
    """
    Rakuten RSS equivalent of the old
    evaluate_ssr_ver2().
    """
    if not row_has_valid_prices(row):
        return None

    code = normalize_code(
        row.get("Code")
    )

    name = str(
        row.get("Name") or ""
    ).strip()

    prev_close = float(
        row["PreviousClose"]
    )

    open_price = float(
        row["OpeningPrice"]
    )

    current_price = float(
        row["CurrentPrice"]
    )

    low_price = float(
        row["LowPrice"]
    )

    open_dt = parse_rss_time(
        row.get("OpeningPriceTime")
    )

    current_dt = parse_rss_time(
        row.get("CurrentPriceTime")
    )

    low_dt = parse_rss_time(
        row.get("LowPriceTime")
    )

    if (
        open_dt is None
        or current_dt is None
        or low_dt is None
    ):
        return None

    gap_pct = (
        open_price
        / prev_close
        - 1.0
    ) * 100.0

    price_from_open_pct = (
        current_price
        / open_price
        - 1.0
    ) * 100.0

    rebound_pct = (
        current_price
        / low_price
        - 1.0
    ) * 100.0

    minutes_since_low = (
        current_dt
        - low_dt
    ).total_seconds() / 60.0

    is_ver2 = (
        gap_pct <= SSR_GAP
        and rebound_pct
        < SSR_VER2_REBOUND_MAX
        and minutes_since_low >= 0
        and minutes_since_low
        <= SSR_VER2_LOW_AGE_MAX
    )

    entry_price = current_price

    take_price = (
        entry_price
        * (
            1.0
            + SSR_VER2_TAKE_PCT
            / 100.0
        )
    )

    stop_price = (
        entry_price
        * (
            1.0
            + SSR_VER2_STOP_PCT
            / 100.0
        )
    )

    return {
        "StrategyVersion":
            "SSR-Ver2",
        "DataType":
            "FORWARD",
        "TriggerDate":
            row.get(
                "TriggerDate",
                "",
            ),
        "TriggerTime":
            trigger_time,
        "TradeDate":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),
        "Code":
            code,
        "Name":
            name,
        "PrevClose":
            prev_close,
        "TradeOpen":
            open_price,
        "GapPct":
            gap_pct,
        "EntryTime":
            current_dt.strftime(
                "%H:%M:%S"
            ),
        "EntryPrice":
            entry_price,
        "MorningLow":
            low_price,
        "MorningLowTime":
            low_dt.strftime(
                "%H:%M:%S"
            ),
        "ReboundLowTo0930Pct":
            rebound_pct,
        "MinutesSinceLow":
            minutes_since_low,
        "Price0930FromOpenPct":
            price_from_open_pct,
        "TakeProfitPct":
            SSR_VER2_TAKE_PCT,
        "StopLossPct":
            SSR_VER2_STOP_PCT,
        "TakePrice":
            take_price,
        "StopPrice":
            stop_price,
        "Ver2Candidate":
            bool(is_ver2),
        "DataStatus":
            (
                "PENDING"
                if is_ver2
                else "FILTERED"
            ),
    }


def save_ssr_ver2_rows(rows):
    if not rows:
        return

    path = Path(
        SSR_VER2_TRACKING_PATH
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    incoming = pd.DataFrame(
        rows
    )

    if path.exists():
        try:
            existing = pd.read_csv(
                path,
                dtype={
                    "Code": str,
                },
                encoding="utf-8-sig",
                low_memory=False,
            )
        except Exception:
            existing = pd.DataFrame()
    else:
        existing = pd.DataFrame()

    combined = pd.concat(
        [
            existing,
            incoming,
        ],
        ignore_index=True,
    )

    combined["Code"] = (
        combined["Code"]
        .astype(str)
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )

    combined = combined.drop_duplicates(
        subset=[
            "StrategyVersion",
            "TriggerDate",
            "TradeDate",
            "Code",
        ],
        keep="last",
    )

    combined = combined.sort_values(
        [
            "TradeDate",
            "Code",
        ]
    )

    combined.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "SSR-Ver2 saved :",
        path,
    )


def print_ssr_ver2_candidate(row):
    print()
    print("=" * 72)
    print(
        " *** SSR-Ver2 CANDIDATE ***"
    )
    print("=" * 72)

    print(
        f'{row["Code"]} '
        f'{row["Name"]}'
    )

    print(
        f'  Open gap          : '
        f'{row["GapPct"]:+.2f}%'
    )

    print(
        f'  09:30 vs Open     : '
        f'{row["Price0930FromOpenPct"]:+.2f}%'
    )

    print(
        f'  Morning Low       : '
        f'{row["MorningLow"]:.0f}'
    )

    print(
        f'  Low Time          : '
        f'{row["MorningLowTime"]}'
    )

    print(
        f'  Rebound from Low  : '
        f'{row["ReboundLowTo0930Pct"]:+.2f}%'
    )

    print(
        f'  Minutes from Low  : '
        f'{row["MinutesSinceLow"]:.1f}'
    )

    print(
        f'  Entry             : '
        f'{row["EntryPrice"]:.0f}'
    )

    print(
        f'  Take +5%          : '
        f'{row["TakePrice"]:.1f}'
    )

    print(
        f'  Stop -3%          : '
        f'{row["StopPrice"]:.1f}'
    )

    print("=" * 72)
    print()
