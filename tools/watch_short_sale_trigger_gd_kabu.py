import argparse
import getpass
import time
from datetime import datetime

import pandas as pd

from show_short_sale_trigger_gd_kabu import (
    SSR_GAP,
    find_latest_trigger_file,
    get_board,
    get_token,
    read_trigger_file,
    safe_float,
)


DEFAULT_INTERVAL = 30
DEFAULT_CUTOFF = "09:30"

# ============================================================
# SSR-Ver2
# Development rule fixed from 2026-09-16 forward validation.
#
# Base:
#   JPX short-sale trigger
#   Opening gap <= -5%
#
# 09:30:
#   rebound from morning low < 1%
#   minutes since morning low <= 10
#
# TP/SL:
#   +5% / -3%
#
# Price0930FromOpenPct <= -5% is recorded for validation only.
# It is NOT a Ver2 entry condition.
# ============================================================

SSR_VER2_REBOUND_MAX = 1.0
SSR_VER2_LOW_AGE_MAX = 10.0
SSR_VER2_TAKE_PCT = 5.0
SSR_VER2_STOP_PCT = -3.0

SSR_VER2_TRACKING_PATH = (
    "data/tracking/"
    "short_sale_trigger_rebound_ver2.csv"
)


def parse_open_datetime(value):
    if not value:
        return None

    dt = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(dt):
        return None

    return dt


def is_today_open(open_dt):
    if open_dt is None:
        return False

    return open_dt.date() == datetime.now().date()


def format_price(value):
    if value is None:
        return "-"

    return f"{value:.0f}"


def scan_code(
    token,
    code,
    name,
):
    board = get_board(
        token,
        code,
    )

    prev_close = safe_float(
        board.get(
            "PreviousClose"
        )
    )

    trade_open = safe_float(
        board.get(
            "OpeningPrice"
        )
    )

    open_dt = parse_open_datetime(
        board.get(
            "OpeningPriceTime"
        )
    )

    if (
        prev_close is None
        or prev_close <= 0
    ):
        return {
            "Code": code,
            "Name": name,
            "Status": "NO_PREVCLOSE",
            "PrevClose": prev_close,
            "Open": trade_open,
            "OpenTime": "",
            "GapPct": None,
        }

    if (
        trade_open is None
        or trade_open <= 0
        or not is_today_open(open_dt)
    ):
        return {
            "Code": code,
            "Name": name,
            "Status": "WAITING_OPEN",
            "PrevClose": prev_close,
            "Open": None,
            "OpenTime": "",
            "GapPct": None,
        }

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

    return {
        "Code": code,
        "Name": name,
        "Status": status,
        "PrevClose": prev_close,
        "Open": trade_open,
        "OpenTime": open_dt.strftime(
            "%H:%M:%S"
        ),
        "GapPct": gap_pct,
    }


def print_candidate(row):
    print()
    print(
        "SSR-Ver1 : "
        f'{row["Code"]} '
        f'{row["Name"]}'
    )

    print(
        "  PrevClose :",
        format_price(
            row["PrevClose"]
        ),
    )

    print(
        "  Open      :",
        format_price(
            row["Open"]
        ),
    )

    print(
        "  OpenTime  :",
        row["OpenTime"],
    )

    print(
        "  Gap       :",
        f'{row["GapPct"]:+.2f}%',
    )

    print()



def parse_board_datetime(value):
    if not value:
        return None

    dt = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(dt):
        return None

    return dt


def evaluate_ssr_ver2(
    token,
    base_row,
    trigger_time="",
):
    code = base_row["Code"]

    board = get_board(
        token,
        code,
    )

    prev_close = safe_float(
        board.get("PreviousClose")
    )

    trade_open = safe_float(
        board.get("OpeningPrice")
    )

    current_price = safe_float(
        board.get("CurrentPrice")
    )

    low_price = safe_float(
        board.get("LowPrice")
    )

    current_dt = parse_board_datetime(
        board.get("CurrentPriceTime")
    )

    low_dt = parse_board_datetime(
        board.get("LowPriceTime")
    )

    if (
        prev_close is None
        or prev_close <= 0
        or trade_open is None
        or trade_open <= 0
        or current_price is None
        or current_price <= 0
        or low_price is None
        or low_price <= 0
        or current_dt is None
        or low_dt is None
    ):
        return None

    gap_pct = (
        trade_open
        / prev_close
        - 1.0
    ) * 100.0

    price_from_open_pct = (
        current_price
        / trade_open
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
            + SSR_VER2_TAKE_PCT / 100.0
        )
    )

    stop_price = (
        entry_price
        * (
            1.0
            + SSR_VER2_STOP_PCT / 100.0
        )
    )

    return {
        "StrategyVersion":
            "SSR-Ver2",
        "DataType":
            "FORWARD",
        "TriggerDate":
            base_row.get(
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
            base_row["Name"],
        "PrevClose":
            prev_close,
        "TradeOpen":
            trade_open,
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

    from pathlib import Path

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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Run one scan only."
        ),
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=(
            "Polling interval in seconds."
        ),
    )

    parser.add_argument(
        "--cutoff",
        default=DEFAULT_CUTOFF,
        help=(
            "Stop time HH:MM."
        ),
    )

    args = parser.parse_args()

    path = find_latest_trigger_file()

    if path is None:
        print(
            "No JPX trigger file found."
        )
        return

    trigger = read_trigger_file(
        path
    )

    if trigger.empty:
        print(
            "No trigger rows found."
        )
        return

    trigger_date = trigger[
        "TriggerDate"
    ].iloc[0]

    watch = {}

    for _, row in trigger.iterrows():
        code = str(
            row["Code"]
        )

        watch[code] = {
            "Code": code,
            "Name": row["Name"],
            "TriggerDate":
                row.get(
                    "TriggerDate",
                    "",
                ),
            "TriggerTime":
                row.get(
                    "TriggerTime",
                    "",
                ),
        }

    print("=" * 72)
    print(
        " SSR-Ver1 MORNING WATCH - kabu API"
    )
    print("=" * 72)

    print(
        "Run date     :",
        datetime.now().strftime(
            "%Y-%m-%d"
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
        len(watch),
    )

    if not args.once:
        print(
            "Poll interval:",
            f"{args.interval} sec",
        )

        print(
            "Cutoff       :",
            args.cutoff,
        )

    print()

    api_password = getpass.getpass(
        "kabu API password: "
    )

    try:
        token = get_token(
            api_password
        )

    except Exception as exc:
        print(
            "TOKEN ERROR:",
            exc,
        )
        return

    unresolved = set(
        watch.keys()
    )

    results = {}

    ssr_codes = set()

    # SSR-Ver1 stocks remain under observation until 09:30
    # for the independent SSR-Ver2 forward validation.
    ver2_watch = set()

    cutoff_hour, cutoff_minute = (
        map(
            int,
            args.cutoff.split(":"),
        )
    )

    while True:
        api_errors = 0

        for code in list(
            unresolved
        ):
            item = watch[
                code
            ]

            try:
                row = scan_code(
                    token,
                    code,
                    item["Name"],
                )

                # Avoid kabu API request-rate errors.
                time.sleep(0.25)

            except Exception as exc:
                api_errors += 1

                print(
                    f"API ERROR {code}: "
                    f"{exc}"
                )

                continue

            status = row[
                "Status"
            ]

            if status == "WAITING_OPEN":
                continue

            results[
                code
            ] = row

            unresolved.discard(
                code
            )

            if (
                status == "SSR-Ver1"
                and code not in ssr_codes
            ):
                ssr_codes.add(
                    code
                )

                ver2_watch.add(
                    code
                )

                print_candidate(
                    row
                )

        now = datetime.now()

        print(
            now.strftime(
                "%H:%M:%S"
            ),
            "| Checked:",
            len(results),
            "| SSR:",
            len(ssr_codes),
            "| Waiting:",
            len(unresolved),
            "| API errors:",
            api_errors,
        )

        if args.once:
            break

        cutoff = now.replace(
            hour=cutoff_hour,
            minute=cutoff_minute,
            second=0,
            microsecond=0,
        )

        if now >= cutoff:
            ver2_rows = []

            if ver2_watch:
                print()
                print("=" * 72)
                print(
                    " SSR-Ver2 09:30 EVALUATION"
                )
                print("=" * 72)

            for code in sorted(
                ver2_watch
            ):
                item = watch[
                    code
                ]

                try:
                    ver2_row = (
                        evaluate_ssr_ver2(
                            token,
                            item,
                            item.get(
                                "TriggerTime",
                                "",
                            ),
                        )
                    )

                    time.sleep(0.25)

                except Exception as exc:
                    print(
                        f"SSR-Ver2 API ERROR "
                        f"{code}: {exc}"
                    )
                    continue

                if ver2_row is None:
                    print(
                        f"SSR-Ver2 NO DATA : "
                        f"{code}"
                    )
                    continue

                ver2_rows.append(
                    ver2_row
                )

                if ver2_row[
                    "Ver2Candidate"
                ]:
                    print_ssr_ver2_candidate(
                        ver2_row
                    )

                else:
                    print(
                        f'SSR-Ver2 FILTERED : '
                        f'{code} '
                        f'Rebound='
                        f'{ver2_row["ReboundLowTo0930Pct"]:+.2f}% '
                        f'LowAge='
                        f'{ver2_row["MinutesSinceLow"]:.1f}m'
                    )

            save_ssr_ver2_rows(
                ver2_rows
            )

            break

        if (
            not unresolved
            and not ver2_watch
        ):
            break

        time.sleep(
            max(
                args.interval,
                5,
            )
        )

    print()
    print("=" * 72)
    print(
        " FINAL SUMMARY"
    )
    print("=" * 72)

    if ssr_codes:
        rows = [
            results[code]
            for code in ssr_codes
        ]

        rows = sorted(
            rows,
            key=lambda x:
                x["GapPct"],
        )

        for row in rows:
            print(
                f'{row["Code"]} '
                f'{row["Name"]} '
                f'Open={format_price(row["Open"])} '
                f'Time={row["OpenTime"]} '
                f'Gap={row["GapPct"]:+.2f}%'
            )

    else:
        print(
            "No SSR-Ver1 candidates."
        )

    print()
    print(
        "SSR candidates :",
        len(ssr_codes),
    )

    print(
        "Waiting open   :",
        len(unresolved),
    )

    print("=" * 72)


if __name__ == "__main__":
    main()
