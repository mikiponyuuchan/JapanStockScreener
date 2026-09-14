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
            break

        if not unresolved:
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
