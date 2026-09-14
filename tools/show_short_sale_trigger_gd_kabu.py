import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TRIGGER_DIR = ROOT / "data" / "jpx_short_sale_trigger"

SSR_GAP = -5.0

API_BASE = "http://localhost:18080/kabusapi"
EXCHANGE = 1


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


def request_json(
    url,
    method="GET",
    headers=None,
    body=None,
):
    data = None

    if body is not None:
        data = json.dumps(
            body,
        ).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        method=method,
        headers=headers or {},
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=10,
        ) as response:
            return json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"HTTP {exc.code}: {detail}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"API connection failed: {exc}"
        ) from exc


def get_token(api_password):
    result = request_json(
        f"{API_BASE}/token",
        method="POST",
        headers={
            "Content-Type":
                "application/json",
        },
        body={
            "APIPassword":
                api_password,
        },
    )

    token = result.get(
        "Token"
    )

    if not token:
        raise RuntimeError(
            "Token was not returned."
        )

    return token


def get_board(
    token,
    code,
):
    symbol = (
        f"{code}@{EXCHANGE}"
    )

    return request_json(
        f"{API_BASE}/board/{symbol}",
        headers={
            "X-API-KEY":
                token,
        },
    )


def safe_float(value):
    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def get_open_time(board):
    value = board.get(
        "OpeningPriceTime"
    )

    if not value:
        return ""

    try:
        dt = pd.to_datetime(
            value,
            errors="coerce",
        )

        if pd.isna(dt):
            return str(value)

        return dt.strftime(
            "%H:%M:%S"
        )

    except Exception:
        return str(value)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--password",
        default=None,
        help=argparse.SUPPRESS,
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

    print("=" * 78)
    print(
        " SHORT-SALE TRIGGER GD WATCH - kabu API"
    )
    print("=" * 78)
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

    api_password = (
        args.password
        if args.password
        else getpass.getpass(
            "kabu API password: "
        )
    )

    try:
        token = get_token(
            api_password
        )

    except Exception as exc:
        print(
            "TOKEN ERROR :",
            exc,
        )
        return

    rows = []
    api_errors = 0

    for _, item in trigger.iterrows():
        code = str(
            item["Code"]
        )

        try:
            board = get_board(
                token,
                code,
            )

        except Exception as exc:
            api_errors += 1

            rows.append(
                {
                    "Code": code,
                    "Name":
                        item["Name"],
                    "TriggerTime":
                        item["TriggerTime"],
                    "PrevClose":
                        None,
                    "Open":
                        None,
                    "OpenTime":
                        "",
                    "GapPct":
                        None,
                    "Status":
                        "API_ERROR",
                }
            )

            print(
                f"API ERROR {code}: "
                f"{exc}"
            )

            continue

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

        open_time = get_open_time(
            board
        )

        gap_pct = None

        if (
            prev_close is not None
            and prev_close > 0
            and trade_open is not None
            and trade_open > 0
        ):
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

        elif (
            prev_close is not None
            and prev_close > 0
        ):
            status = "WAITING_OPEN"

        else:
            status = "NO_PREVCLOSE"

        rows.append(
            {
                "Code":
                    code,
                "Name":
                    item["Name"],
                "TriggerTime":
                    item["TriggerTime"],
                "PrevClose":
                    prev_close,
                "Open":
                    trade_open,
                "OpenTime":
                    open_time,
                "GapPct":
                    gap_pct,
                "Status":
                    status,
            }
        )

    if not rows:
        print(
            "No API data available."
        )
        return

    out = pd.DataFrame(
        rows
    )

    status_order = {
        "SSR-Ver1": 0,
        "GD-WATCH": 1,
        "WAITING_OPEN": 2,
        "NOT-GD": 3,
        "NO_PREVCLOSE": 4,
        "API_ERROR": 5,
    }

    out["_StatusOrder"] = (
        out["Status"]
        .map(status_order)
        .fillna(99)
    )

    out = out.sort_values(
        [
            "_StatusOrder",
            "GapPct",
        ],
        ascending=[
            True,
            True,
        ],
        na_position="last",
    )

    out = out.drop(
        columns=[
            "_StatusOrder"
        ]
    )

    candidates = out[
        out["Status"]
        == "SSR-Ver1"
    ].copy()

    waiting = out[
        out["Status"]
        == "WAITING_OPEN"
    ].copy()

    print()
    print("=" * 78)
    print(
        " *** SSR-Ver1 CANDIDATES : Gap <= -5% ***"
    )
    print("=" * 78)

    if candidates.empty:
        if not waiting.empty:
            print(
                " NONE CONFIRMED - "
                "some stocks are still waiting to open."
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
                "OpenTime",
                "GapPct",
            ]
        ].copy()

        candidate_display[
            "PrevClose"
        ] = candidate_display[
            "PrevClose"
        ].map(
            lambda x:
            f"{x:.0f}"
            if pd.notna(x)
            else "-"
        )

        candidate_display[
            "Open"
        ] = candidate_display[
            "Open"
        ].map(
            lambda x:
            f"{x:.0f}"
            if pd.notna(x)
            else "-"
        )

        candidate_display[
            "GapPct"
        ] = candidate_display[
            "GapPct"
        ].map(
            lambda x:
            f"{x:+.2f}%"
            if pd.notna(x)
            else "-"
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
        " Waiting open   :",
        len(waiting),
    )
    print(
        " API errors     :",
        api_errors,
    )
    print("=" * 78)

    print()
    print(
        "ALL TRIGGER STOCKS"
    )
    print("-" * 78)

    display = out.copy()

    display[
        "PrevClose"
    ] = display[
        "PrevClose"
    ].map(
        lambda x:
        f"{x:.0f}"
        if pd.notna(x)
        else "-"
    )

    display[
        "Open"
    ] = display[
        "Open"
    ].map(
        lambda x:
        f"{x:.0f}"
        if pd.notna(x)
        else "-"
    )

    display[
        "GapPct"
    ] = display[
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
