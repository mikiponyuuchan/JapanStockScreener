from pathlib import Path
import sys
import io
from contextlib import redirect_stdout

sys.path.insert(
    0,
    str(
        Path(__file__)
        .resolve()
        .parents[1]
        / "src"
    )
)

import pandas as pd

from services.yahoo_service import _download_history_batch


TRACKING_FILE = Path(
    "data/tracking/initial_move_tracking.csv"
)

OUTPUT_FILE = Path(
    "data/analysis/initial_move_highlow_panel.csv"
)

CURRENT_START_DATE = pd.Timestamp(
    "2026-08-18"
)


def normalize_history(df):

    if df is None or df.empty:
        return None

    x = df.copy()

    if "Date" in x.columns:

        x["Date"] = pd.to_datetime(
            x["Date"],
            errors="coerce"
        )

        x = x.dropna(
            subset=["Date"]
        )

        x = x.set_index(
            "Date"
        )

    else:

        x.index = pd.to_datetime(
            x.index,
            errors="coerce"
        )

        x = x[
            ~x.index.isna()
        ]

    if x.empty:
        return None

    if getattr(
        x.index,
        "tz",
        None
    ) is not None:

        x.index = (
            x.index
            .tz_localize(None)
        )

    x.index = x.index.normalize()

    x = (
        x
        .sort_index()
    )

    return x


def pct(price, base):

    if pd.isna(price):
        return None

    if pd.isna(base):
        return None

    if base == 0:
        return None

    return (
        float(price)
        / float(base)
        - 1
    ) * 100


def main():

    if not TRACKING_FILE.exists():

        print(
            "tracking file not found :",
            TRACKING_FILE
        )

        return

    tracking = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig"
    )

    # ------------------------------------------
    # 列位置から英語名へ変換
    # ------------------------------------------

    work = pd.DataFrame({
        "DetectionDate":
            pd.to_datetime(
                tracking.iloc[:, 0],
                errors="coerce"
            ),

        "Code":
            tracking.iloc[:, 1]
            .astype(str),

        "Name":
            tracking.iloc[:, 2]
            .astype(str),

        "BasePrice":
            pd.to_numeric(
                tracking.iloc[:, 3],
                errors="coerce"
            ),

        "InitialScore":
            pd.to_numeric(
                tracking.iloc[:, 4],
                errors="coerce"
            ),
    })

    # 既存ClosePctも検算用に保持
    for day in range(1, 11):

        pct_index = 4 + day * 2

        work[
            f"TrackingDay{day}ClosePct"
        ] = pd.to_numeric(
            tracking.iloc[:, pct_index],
            errors="coerce"
        )

    work = work.dropna(
        subset=[
            "DetectionDate",
            "BasePrice",
            "InitialScore",
        ]
    )

    codes = sorted(
        work["Code"]
        .dropna()
        .unique()
        .tolist()
    )

    print("=" * 70)
    print("Initial move High / Low reconstruction")
    print("=" * 70)

    print(
        "Tracking rows :",
        len(work)
    )

    print(
        "Unique codes  :",
        len(codes)
    )

    print()
    print(
        "Yahoo history downloading..."
    )

    try:

        with redirect_stdout(
            io.StringIO()
        ):

            history_map = (
                _download_history_batch(
                    codes,
                    period="3mo",
                    batch_size=100
                )
            )

    except Exception as e:

        print(
            "Yahoo ERROR :",
            e
        )

        return

    print(
        "Yahoo success:",
        len(history_map)
    )

    rows = []

    total = len(work)

    for pos, (_, row) in enumerate(
        work.iterrows(),
        start=1
    ):

        code = row["Code"]

        detection_date = (
            pd.Timestamp(
                row["DetectionDate"]
            )
            .normalize()
        )

        base = float(
            row["BasePrice"]
        )

        history = normalize_history(
            history_map.get(code)
        )

        out = {
            "DetectionDate":
                detection_date.strftime(
                    "%Y-%m-%d"
                ),

            "Code":
                code,

            "Name":
                row["Name"],

            "BasePrice":
                base,

            "InitialScore":
                row["InitialScore"],
        }

        if history is not None:

            future = history[
                history.index
                > detection_date
            ].copy()

        else:

            future = pd.DataFrame()

        # --------------------------------------
        # Day1-Day10 actual trading sessions
        # --------------------------------------

        for day in range(1, 11):

            # --------------------------------------
            # ??tracking????????????????
            # ??????????????
            # --------------------------------------

            tracking_mature = pd.notna(
                row[f"TrackingDay{day}ClosePct"]
            )

            if not tracking_mature:

                out[f"Day{day}Date"] = None
                out[f"Day{day}HighPct"] = None
                out[f"Day{day}LowPct"] = None
                out[f"Day{day}ClosePct"] = None

                continue

            if len(future) < day:

                out[f"Day{day}Date"] = None
                out[f"Day{day}HighPct"] = None
                out[f"Day{day}LowPct"] = None
                out[f"Day{day}ClosePct"] = None

                continue

            bar = future.iloc[
                day - 1
            ]

            day_date = future.index[
                day - 1
            ]

            out[
                f"Day{day}Date"
            ] = day_date.strftime(
                "%Y-%m-%d"
            )

            out[
                f"Day{day}HighPct"
            ] = pct(
                bar.get("High"),
                base
            )

            out[
                f"Day{day}LowPct"
            ] = pct(
                bar.get("Low"),
                base
            )

            out[
                f"Day{day}ClosePct"
            ] = pct(
                bar.get("Close"),
                base
            )

        # --------------------------------------
        # cumulative maximum opportunity
        # --------------------------------------

        for horizon in [
            1, 3, 5, 7, 10
        ]:

            # --------------------------------------
            # ?????????????????
            # ??horizon?????????
            # --------------------------------------

            if out.get(
                f"Day{horizon}HighPct"
            ) is None:

                out[
                    f"MaxHigh{horizon}Pct"
                ] = None

                out[
                    f"PeakDay{horizon}"
                ] = None

                out[
                    f"MinLow{horizon}Pct"
                ] = None

                out[
                    f"TroughDay{horizon}"
                ] = None

                continue

            highs = []

            lows = []

            for day in range(
                1,
                horizon + 1
            ):

                h = out.get(
                    f"Day{day}HighPct"
                )

                l = out.get(
                    f"Day{day}LowPct"
                )

                if h is not None:
                    highs.append(
                        (day, h)
                    )

                if l is not None:
                    lows.append(
                        (day, l)
                    )

            if highs:

                peak_day, peak_value = max(
                    highs,
                    key=lambda x: x[1]
                )

                out[
                    f"MaxHigh{horizon}Pct"
                ] = peak_value

                out[
                    f"PeakDay{horizon}"
                ] = peak_day

            else:

                out[
                    f"MaxHigh{horizon}Pct"
                ] = None

                out[
                    f"PeakDay{horizon}"
                ] = None

            if lows:

                trough_day, trough_value = min(
                    lows,
                    key=lambda x: x[1]
                )

                out[
                    f"MinLow{horizon}Pct"
                ] = trough_value

                out[
                    f"TroughDay{horizon}"
                ] = trough_day

            else:

                out[
                    f"MinLow{horizon}Pct"
                ] = None

                out[
                    f"TroughDay{horizon}"
                ] = None

        # --------------------------------------
        # existing tracking Close comparison
        # --------------------------------------

        for day in range(1, 11):

            tracking_pct = row[
                f"TrackingDay{day}ClosePct"
            ]

            rebuilt_pct = out[
                f"Day{day}ClosePct"
            ]

            out[
                f"TrackingDay{day}ClosePct"
            ] = tracking_pct

            if (
                pd.notna(tracking_pct)
                and rebuilt_pct is not None
            ):

                out[
                    f"Day{day}CloseDiff"
                ] = (
                    rebuilt_pct
                    - tracking_pct
                )

            else:

                out[
                    f"Day{day}CloseDiff"
                ] = None

        rows.append(
            out
        )

        if (
            pos % 100 == 0
            or pos == total
        ):

            print(
                f"{pos} / {total}"
            )

    panel = pd.DataFrame(
        rows
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    panel.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(
        "Saved :",
        OUTPUT_FILE
    )

    # ==========================================
    # Close reconstruction validation
    # ==========================================

    diffs = []

    for day in range(1, 11):

        col = f"Day{day}CloseDiff"

        if col not in panel.columns:
            continue

        s = pd.to_numeric(
            panel[col],
            errors="coerce"
        ).dropna()

        if len(s):

            diffs.extend(
                s.abs().tolist()
            )

    print()
    print("=" * 70)
    print("CLOSE VALIDATION")
    print("=" * 70)

    if diffs:

        d = pd.Series(
            diffs
        )

        print(
            "Compared :",
            len(d)
        )

        print(
            "Median absolute diff :",
            round(
                d.median(),
                4
            ),
            "%"
        )

        print(
            "Max absolute diff    :",
            round(
                d.max(),
                4
            ),
            "%"
        )

        print(
            "Diff > 0.10%         :",
            int(
                (d > 0.10).sum()
            )
        )

    # ==========================================
    # Current specification
    # ==========================================

    current = panel[
        pd.to_datetime(
            panel["DetectionDate"]
        )
        >= CURRENT_START_DATE
    ].copy()

    current = current[
        pd.to_numeric(
            current["InitialScore"],
            errors="coerce"
        )
        <= 7
    ].copy()

    # first detection per code
    first = (
        current
        .sort_values(
            [
                "DetectionDate",
                "Code",
            ]
        )
        .drop_duplicates(
            subset=["Code"],
            keep="first"
        )
        .copy()
    )

    print()
    print("=" * 70)
    print(
        "FIRST DETECTION - MAXIMUM HIGH OPPORTUNITY"
    )
    print("=" * 70)

    for score in [
        3, 4, 5, 6, 7
    ]:

        g = first[
            first["InitialScore"]
            == score
        ]

        if g.empty:
            continue

        print()
        print(
            f"SCORE {score}"
        )

        for horizon in [
            1, 3, 5, 7, 10
        ]:

            s = pd.to_numeric(
                g[
                    f"MaxHigh{horizon}Pct"
                ],
                errors="coerce"
            ).dropna()

            if s.empty:
                continue

            print(
                f"  {horizon:2d}d "
                f"N={len(s):3d}  "
                f"mean={s.mean():6.2f}%  "
                f"median={s.median():6.2f}%  "
                f"+5={((s >= 5).mean()*100):5.1f}%  "
                f"+10={((s >= 10).mean()*100):5.1f}%  "
                f"+20={((s >= 20).mean()*100):5.1f}%"
            )


if __name__ == "__main__":
    main()
