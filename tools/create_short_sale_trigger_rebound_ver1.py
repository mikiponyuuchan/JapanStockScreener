from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


TRIGGER_DIR = Path(
    "data/jpx_short_sale_trigger"
)

TRACKING_PATH = Path(
    "data/tracking/"
    "short_sale_trigger_rebound_ver1.csv"
)

FORWARD_START = "2026-09-14"

GAP_MAX_PCT = -5.0
ENTRY_TIME = "09:30"
TAKE_PCT = 5.0
STOP_PCT = -3.0


OUTPUT_COLUMNS = [
    "StrategyVersion",
    "DataType",
    "TriggerDate",
    "TriggerTime",
    "TradeDate",
    "Code",
    "Name",
    "PrevClose",
    "TradeOpen",
    "GapPct",
    "EntryTime",
    "EntryPrice",
    "TakeProfitPct",
    "StopLossPct",
    "TakePrice",
    "StopPrice",
    "HitTakeTime",
    "HitStopTime",
    "ExitType",
    "ReturnPct",
    "MaxHighPct",
    "MinLowPct",
    "ClosePct",
    "Last5mTime",
    "DataStatus",
]


def normalize_code(value):
    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def normalize_date(value):
    dt = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(dt):
        return None

    return dt.strftime("%Y-%m-%d")


def load_trigger_files():
    files = []

    for pattern in [
        "*.xls",
        "*.xlsx",
    ]:
        files.extend(
            TRIGGER_DIR.rglob(pattern)
        )

    rows = []

    for path in sorted(set(files)):
        try:
            raw = pd.read_excel(
                path,
                header=None,
            )
        except Exception as exc:
            print(
                f"READ ERROR : "
                f"{path} : {exc}"
            )
            continue

        if (
            raw is None
            or raw.empty
            or raw.shape[0] < 12
            or raw.shape[1] < 6
        ):
            continue

        # JPX workbook layout:
        # row 7, col 2  : trading date
        # row 11 onward : stock rows
        # col 1         : code
        # col 2         : Japanese name
        # col 4         : triggered time
        # col 5         : primary market
        trigger_date = normalize_date(
            raw.iloc[7, 2]
        )

        if trigger_date is None:
            # Fallback to YYYYMMDD in filename.
            digits = "".join(
                ch
                for ch in path.stem[:8]
                if ch.isdigit()
            )

            if len(digits) == 8:
                trigger_date = normalize_date(
                    digits
                )

        if trigger_date is None:
            continue

        data = raw.iloc[
            11:,
            :
        ].copy()

        for _, row in data.iterrows():
            code_value = row.iloc[1]

            if pd.isna(code_value):
                continue

            code = normalize_code(
                code_value
            )

            if (
                not code
                or code.lower() == "nan"
            ):
                continue

            name_value = row.iloc[2]
            time_value = row.iloc[4]
            market_value = row.iloc[5]

            name = (
                ""
                if pd.isna(name_value)
                else str(name_value).strip()
            )

            trigger_time = (
                ""
                if pd.isna(time_value)
                else str(time_value).strip()
            )

            market = (
                ""
                if pd.isna(market_value)
                else str(market_value).strip()
            )

            rows.append(
                {
                    "TriggerDate":
                        trigger_date,
                    "TriggerTime":
                        trigger_time,
                    "Code":
                        code,
                    "Name":
                        name,
                    "Market":
                        market,
                }
            )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)

    out = out.drop_duplicates(
        subset=[
            "TriggerDate",
            "Code",
        ],
        keep="last",
    )

    return out


def download_daily(code, trigger_date):
    base = datetime.strptime(
        trigger_date,
        "%Y-%m-%d",
    )

    start = (
        base
        - timedelta(days=2)
    )

    end = (
        base
        + timedelta(days=10)
    )

    try:
        df = yf.download(
            f"{code}.T",
            start=start.strftime(
                "%Y-%m-%d"
            ),
            end=end.strftime(
                "%Y-%m-%d"
            ),
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:
        print(
            f"DAILY ERROR "
            f"{code} {trigger_date} : "
            f"{exc}"
        )
        return None

    if df is None or df.empty:
        return None

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        df.columns = [
            col[0]
            for col in df.columns
        ]

    idx = pd.to_datetime(
        df.index
    )

    try:
        if idx.tz is not None:
            idx = (
                idx
                .tz_convert(
                    "Asia/Tokyo"
                )
                .tz_localize(None)
            )
    except Exception:
        try:
            idx = idx.tz_localize(
                None
            )
        except Exception:
            pass

    df = df.copy()
    df.index = idx

    return df


def get_trade_info(
    daily,
    trigger_date,
):
    if daily is None or daily.empty:
        return None

    trigger_ts = pd.Timestamp(
        trigger_date
    )

    same = daily[
        daily.index.normalize()
        == trigger_ts
    ]

    future = daily[
        daily.index.normalize()
        > trigger_ts
    ]

    if same.empty or future.empty:
        return None

    trigger_row = same.iloc[-1]
    trade_row = future.iloc[0]

    prev_close = pd.to_numeric(
        trigger_row.get("Close"),
        errors="coerce",
    )

    trade_open = pd.to_numeric(
        trade_row.get("Open"),
        errors="coerce",
    )

    if (
        pd.isna(prev_close)
        or pd.isna(trade_open)
        or prev_close <= 0
    ):
        return None

    trade_date = (
        future.index[0]
        .strftime("%Y-%m-%d")
    )

    gap_pct = (
        float(trade_open)
        / float(prev_close)
        - 1.0
    ) * 100.0

    return {
        "TradeDate":
            trade_date,
        "PrevClose":
            float(prev_close),
        "TradeOpen":
            float(trade_open),
        "GapPct":
            gap_pct,
    }


def load_existing():
    if not TRACKING_PATH.exists():
        return pd.DataFrame(
            columns=OUTPUT_COLUMNS
        )

    try:
        return pd.read_csv(
            TRACKING_PATH,
            dtype={
                "Code": str,
            },
            encoding="utf-8-sig",
            low_memory=False,
        )
    except Exception:
        return pd.DataFrame(
            columns=OUTPUT_COLUMNS
        )


def main():
    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    triggers = load_trigger_files()

    if triggers.empty:
        print(
            "No JPX trigger files."
        )
        return

    existing = load_existing()

    existing_keys = set()

    if not existing.empty:
        for _, row in existing.iterrows():
            existing_keys.add(
                (
                    str(
                        row.get(
                            "TriggerDate",
                            "",
                        )
                    ),
                    normalize_code(
                        row.get(
                            "Code",
                            "",
                        )
                    ),
                )
            )

    rows = []

    for _, row in triggers.iterrows():
        trigger_date = str(
            row["TriggerDate"]
        )

        code = normalize_code(
            row["Code"]
        )

        key = (
            trigger_date,
            code,
        )

        if key in existing_keys:
            continue

        daily = download_daily(
            code,
            trigger_date,
        )

        info = get_trade_info(
            daily,
            trigger_date,
        )

        if info is None:
            continue

        trade_date = info[
            "TradeDate"
        ]

        if trade_date < FORWARD_START:
            continue

        if trade_date > today:
            continue

        gap_pct = info["GapPct"]

        if gap_pct > GAP_MAX_PCT:
            continue

        rows.append(
            {
                "StrategyVersion":
                    "SSR-Ver1",
                "DataType":
                    "FORWARD",
                "TriggerDate":
                    trigger_date,
                "TriggerTime":
                    row.get(
                        "TriggerTime",
                        "",
                    ),
                "TradeDate":
                    trade_date,
                "Code":
                    code,
                "Name":
                    row.get(
                        "Name",
                        "",
                    ),
                "PrevClose":
                    info[
                        "PrevClose"
                    ],
                "TradeOpen":
                    info[
                        "TradeOpen"
                    ],
                "GapPct":
                    gap_pct,
                "EntryTime":
                    ENTRY_TIME,
                "EntryPrice":
                    "",
                "TakeProfitPct":
                    TAKE_PCT,
                "StopLossPct":
                    STOP_PCT,
                "TakePrice":
                    "",
                "StopPrice":
                    "",
                "HitTakeTime":
                    "",
                "HitStopTime":
                    "",
                "ExitType":
                    "",
                "ReturnPct":
                    "",
                "MaxHighPct":
                    "",
                "MinLowPct":
                    "",
                "ClosePct":
                    "",
                "Last5mTime":
                    "",
                "DataStatus":
                    "PENDING",
            }
        )

        print(
            f"CANDIDATE : "
            f"{trade_date} "
            f"{code} "
            f"Gap={gap_pct:.2f}%"
        )

    if not rows:
        print(
            "No new SSR-Ver1 candidates."
        )
        return

    incoming = pd.DataFrame(
        rows,
        columns=OUTPUT_COLUMNS,
    )

    combined = pd.concat(
        [
            existing,
            incoming,
        ],
        ignore_index=True,
    )

    combined["Code"] = (
        combined["Code"]
        .map(normalize_code)
    )

    combined = combined.drop_duplicates(
        subset=[
            "StrategyVersion",
            "TriggerDate",
            "Code",
        ],
        keep="first",
    )

    combined = combined.sort_values(
        [
            "TradeDate",
            "Code",
        ]
    )

    TRACKING_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_csv(
        TRACKING_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 60)
    print("SSR VER1 CANDIDATE TRACKING")
    print("=" * 60)
    print(
        "New rows   :",
        len(incoming),
    )
    print(
        "Total rows :",
        len(combined),
    )
    print(
        "Saved      :",
        TRACKING_PATH,
    )


if __name__ == "__main__":
    main()
