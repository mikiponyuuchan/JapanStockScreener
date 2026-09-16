import math
from pathlib import Path

import pandas as pd
import yfinance as yf


SNAPSHOT_DIR = Path(
    "data/tracking/morning_snapshots"
)

OUTPUT_PATH = Path(
    "data/analysis/intraday_top20_panel.csv"
)


def num(value):
    return pd.to_numeric(
        value,
        errors="coerce"
    )


def first_hit(df, entry, pct):
    if df.empty or pd.isna(entry) or entry <= 0:
        return ""

    target = entry * (1 + pct / 100)

    if pct > 0:
        hit = df[df["High"] >= target]
    else:
        hit = df[df["Low"] <= target]

    if hit.empty:
        return ""

    return hit.index[0].strftime("%H:%M")


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


def next_5m_bar(snapshot_time):
    ts = pd.Timestamp(
        "2000-01-01 " + snapshot_time
    )

    minute = ts.minute

    next_minute = (
        (minute // 5) * 5 + 5
    )

    base = ts.replace(
        second=0,
        microsecond=0
    )

    if next_minute >= 60:
        base = (
            base
            + pd.Timedelta(hours=1)
        ).replace(minute=0)
    else:
        base = base.replace(
            minute=next_minute
        )

    return base.strftime("%H:%M")


def normalize_intraday(df):
    if df is None or df.empty:
        return pd.DataFrame()

    x = df.copy()

    if isinstance(
        x.columns,
        pd.MultiIndex
    ):
        x.columns = (
            x.columns
            .get_level_values(0)
        )

    x = x.dropna(
        subset=["High", "Low"]
    )

    return x


def main():
    files = sorted(
        SNAPSHOT_DIR.glob(
            "*_top20.csv"
        )
    )

    if not files:
        print("No snapshot files.")
        return

    print("=" * 76)
    print("INTRADAY TOP20 MOMENTUM ANALYSIS")
    print("=" * 76)
    print(
        f"Snapshot files : {len(files)}"
    )

    snapshots = []

    for file in files:
        df = pd.read_csv(
            file,
        )

        if df.empty:
            continue

        df["_source_file"] = file.name

        snapshots.append(df)

    if not snapshots:
        print("No snapshot rows.")
        return

    src = pd.concat(
        snapshots,
        ignore_index=True
    )

    print(
        f"Snapshot rows  : {len(src)}"
    )

    rows = []

    grouped = src.groupby(
        ["SnapshotDate", "SnapshotTime"],
        dropna=False
    )

    for (
        snapshot_date,
        snapshot_time
    ), group in grouped:

        date_text = str(snapshot_date)

        time_text = str(snapshot_time)

        start_eval = next_5m_bar(
            time_text
        )

        codes = (
            group.iloc[:, 2]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        print()
        print(
            f"{date_text} {time_text}"
        )
        print(
            f"Rows       : {len(group)}"
        )
        print(
            f"Eval start : {start_eval}"
        )

        start_date = date_text

        end_date = (
            pd.Timestamp(date_text)
            + pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")

        for _, source in group.iterrows():

            code = str(
                source.iloc[2]
            )

            entry = num(
                source.iloc[5]
            )

            out = source.to_dict()

            out["SnapshotPrice"] = entry
            out["EvaluationStart"] = (
                start_eval
            )

            try:
                intraday = yf.download(
                    f"{code}.T",
                    start=start_date,
                    end=end_date,
                    interval="5m",
                    auto_adjust=False,
                    progress=False,
                    threads=False
                )

            except Exception as e:
                print(
                    f"ERROR {code}: {e}"
                )
                intraday = pd.DataFrame()

            intraday = normalize_intraday(
                intraday
            )

            if not intraday.empty:
                local_index = (
                    intraday.index
                )

                if (
                    getattr(
                        local_index,
                        "tz",
                        None
                    )
                    is not None
                ):
                    local_index = (
                        local_index.tz_convert(
                            "Asia/Tokyo"
                        )
                    )

                intraday = (
                    intraday.copy()
                )

                intraday.index = (
                    local_index
                )

                intraday = intraday[
                    intraday.index.strftime(
                        "%H:%M"
                    )
                    >= start_eval
                ]

            out["Bars"] = len(
                intraday
            )

            if (
                intraday.empty
                or pd.isna(entry)
                or entry <= 0
            ):
                out["MaxHighPct"] = math.nan
                out["MinLowPct"] = math.nan
                out["ClosePct"] = math.nan

                rows.append(out)
                continue

            out["HitPlus3"] = first_hit(
                intraday,
                entry,
                3
            )

            out["HitPlus5"] = first_hit(
                intraday,
                entry,
                5
            )

            out["HitPlus10"] = first_hit(
                intraday,
                entry,
                10
            )

            out["HitMinus3"] = first_hit(
                intraday,
                entry,
                -3
            )

            out["HitMinus5"] = first_hit(
                intraday,
                entry,
                -5
            )

            out["Plus5VsMinus3"] = (
                compare_hits(
                    out["HitPlus5"],
                    out["HitMinus3"]
                )
            )

            out["Plus5VsMinus5"] = (
                compare_hits(
                    out["HitPlus5"],
                    out["HitMinus5"]
                )
            )

            high = num(
                intraday["High"].max()
            )

            low = num(
                intraday["Low"].min()
            )

            close = num(
                intraday[
                    "Close"
                ].dropna().iloc[-1]
            )

            out["MaxHighPct"] = (
                high / entry - 1
            ) * 100

            out["MinLowPct"] = (
                low / entry - 1
            ) * 100

            out["ClosePct"] = (
                close / entry - 1
            ) * 100

            rows.append(out)

    panel = pd.DataFrame(rows)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    panel.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 76)
    print("RESULT")
    print("=" * 76)
    print(
        f"Panel rows : {len(panel)}"
    )
    print(
        f"Saved      : {OUTPUT_PATH}"
    )

    valid = panel[
        pd.to_numeric(
            panel["MaxHighPct"],
            errors="coerce"
        ).notna()
    ].copy()

    if valid.empty:
        return

    valid["Score"] = pd.to_numeric(
        valid.iloc[:, 13],
        errors="coerce"
    )

    print()
    print("=" * 76)
    print("ALL")
    print("=" * 76)
    print(
        f"N            : {len(valid)}"
    )
    print(
        f"High median  : "
        f"{valid['MaxHighPct'].median():.2f}%"
    )
    print(
        f"High >= +3%  : "
        f"{(valid['MaxHighPct'] >= 3).mean()*100:.1f}%"
    )
    print(
        f"High >= +5%  : "
        f"{(valid['MaxHighPct'] >= 5).mean()*100:.1f}%"
    )
    print(
        f"High >= +10% : "
        f"{(valid['MaxHighPct'] >= 10).mean()*100:.1f}%"
    )
    print(
        f"Low median   : "
        f"{valid['MinLowPct'].median():.2f}%"
    )
    print(
        f"Close median : "
        f"{valid['ClosePct'].median():.2f}%"
    )

    print()
    print("=" * 76)
    print("BY SCORE")
    print("=" * 76)

    for score in sorted(
        valid["Score"]
        .dropna()
        .unique(),
        reverse=True
    ):
        g = valid[
            valid["Score"] == score
        ]

        print()
        print(
            f"Score {score:g}"
        )
        print("-" * 76)
        print(
            f"N            : {len(g)}"
        )
        print(
            f"High median  : "
            f"{g['MaxHighPct'].median():.2f}%"
        )
        print(
            f"High >= +3%  : "
            f"{(g['MaxHighPct'] >= 3).mean()*100:.1f}%"
        )
        print(
            f"High >= +5%  : "
            f"{(g['MaxHighPct'] >= 5).mean()*100:.1f}%"
        )
        print(
            f"High >= +10% : "
            f"{(g['MaxHighPct'] >= 10).mean()*100:.1f}%"
        )
        print(
            f"Low median   : "
            f"{g['MinLowPct'].median():.2f}%"
        )
        print(
            f"Close median : "
            f"{g['ClosePct'].median():.2f}%"
        )


if __name__ == "__main__":
    main()
