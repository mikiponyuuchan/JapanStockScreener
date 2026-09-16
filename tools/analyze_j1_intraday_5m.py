import pandas as pd
import yfinance as yf
from pathlib import Path


PANEL_PATH = Path(
    "data/analysis/j1_next_open_panel.csv"
)

OUTPUT_PATH = Path(
    "data/analysis/j1_intraday_5m_panel.csv"
)


UP_LEVELS = [3, 5, 10]
DOWN_LEVELS = [-3, -5, -10]


def first_hit_time(df, entry, level):
    if df is None or df.empty:
        return ""

    if level > 0:
        target = entry * (1 + level / 100)
        hit = df[df["High"] >= target]
    else:
        target = entry * (1 + level / 100)
        hit = df[df["Low"] <= target]

    if hit.empty:
        return ""

    ts = hit.index[0]

    try:
        return ts.strftime("%H:%M")
    except Exception:
        return str(ts)


def compare_hits(up_time, down_time):
    if not up_time and not down_time:
        return "NONE"

    if up_time and not down_time:
        return "UP_ONLY"

    if down_time and not up_time:
        return "DOWN_ONLY"

    if up_time < down_time:
        return "UP_FIRST"

    if down_time < up_time:
        return "DOWN_FIRST"

    return "SAME_BAR"


def main():
    if not PANEL_PATH.exists():
        print("Panel not found:")
        print(PANEL_PATH)
        return

    df = pd.read_csv(
        PANEL_PATH,
        dtype={"Code": str}
    )

    numeric_cols = [
        "DetectionBodyPct",
        "NextOpenGapPct",
        "Day1Open",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    target = df[
        df["Day1Open"].notna()
        & (df["NextOpenGapPct"] >= 0)
        & (df["DetectionBodyPct"] >= 5)
    ].copy()

    print("=" * 72)
    print("J1 INTRADAY 5M ANALYSIS")
    print("=" * 72)
    print(f"Target rows : {len(target)}")
    print()

    rows = []

    for _, row in target.iterrows():
        code = str(row["Code"])
        name = row.get("Name", "")
        entry = float(row["Day1Open"])

        detection_date = pd.Timestamp(
            row["DetectionDate"]
        )

        next_day = detection_date + pd.Timedelta(
            days=1
        )

        while next_day.weekday() >= 5:
            next_day += pd.Timedelta(days=1)

        start = next_day.strftime("%Y-%m-%d")
        end = (
            next_day
            + pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")

        print(
            f"{code} {name} : "
            f"{start}"
        )

        try:
            intraday = yf.download(
                f"{code}.T",
                start=start,
                end=end,
                interval="5m",
                auto_adjust=False,
                progress=False,
                threads=False
            )

        except Exception as e:
            print(f"  ERROR : {e}")
            intraday = pd.DataFrame()

        out = {
            "DetectionDate": row["DetectionDate"],
            "Code": code,
            "Name": name,
            "Entry": entry,
            "IntradayDate": start,
            "Bars": 0,
        }

        if intraday is None or intraday.empty:
            print("  NO DATA")
            rows.append(out)
            continue

        if isinstance(
            intraday.columns,
            pd.MultiIndex
        ):
            try:
                intraday.columns = (
                    intraday.columns
                    .get_level_values(0)
                )
            except Exception:
                pass

        intraday = intraday.dropna(
            subset=["High", "Low"]
        )

        out["Bars"] = len(intraday)

        for level in UP_LEVELS:
            out[f"HitPlus{level}"] = (
                first_hit_time(
                    intraday,
                    entry,
                    level
                )
            )

        for level in [3, 5, 10]:
            out[f"HitMinus{level}"] = (
                first_hit_time(
                    intraday,
                    entry,
                    -level
                )
            )

        out["Plus5VsMinus3"] = (
            compare_hits(
                out["HitPlus5"],
                out["HitMinus3"]
            )
        )

        out["Plus10VsMinus5"] = (
            compare_hits(
                out["HitPlus10"],
                out["HitMinus5"]
            )
        )

        high_pct = (
            intraday["High"].max()
            / entry - 1
        ) * 100

        low_pct = (
            intraday["Low"].min()
            / entry - 1
        ) * 100

        last_close = float(
            intraday["Close"].dropna().iloc[-1]
        )

        close_pct = (
            last_close / entry - 1
        ) * 100

        out["MaxHighPct5m"] = high_pct
        out["MinLowPct5m"] = low_pct
        out["ClosePct5m"] = close_pct

        rows.append(out)

    result = pd.DataFrame(rows)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 72)
    print("RESULT")
    print("=" * 72)
    print(f"Rows  : {len(result)}")
    print(f"Saved : {OUTPUT_PATH}")
    print()

    if not result.empty:
        print(
            result.to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
