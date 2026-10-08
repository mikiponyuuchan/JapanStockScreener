from datetime import datetime, date, time as dt_time

from rss_ssr_reader import (
    normalize_code,
    row_has_valid_prices,
)


SSR_GAP = -5.0

SSR_VER2_REBOUND_MAX = 1.0
SSR_VER2_LOW_AGE_MAX = 10.0
SSR_VER2_TAKE_PCT = 5.0
SSR_VER2_STOP_PCT = -3.0


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
