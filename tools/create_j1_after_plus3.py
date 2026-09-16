from pathlib import Path

src = Path("tools/analyze_j1_take_compare.py")
dst = Path("tools/analyze_j1_after_plus3.py")

text = src.read_text(encoding="utf-8")

start = text.find("def main():")
if start == -1:
    raise SystemExit("main() not found")

prefix = text[:start]

new_main = r'''
def first_hit_time(work, entry, pct):
    target = entry * (1 + pct / 100)

    hits = work[
        work["High"] >= target
    ]

    if hits.empty:
        return None

    return hits.index[0]


def fmt_time(ts):
    if ts is None:
        return ""

    return pd.Timestamp(
        ts
    ).strftime("%H:%M")


def main():
    compare_path = Path(
        "data/analysis/j1_take_compare_520_549.csv"
    )

    output_path = Path(
        "data/analysis/j1_after_plus3.csv"
    )

    c = pd.read_csv(
        compare_path,
        dtype={"Code": str},
        low_memory=False,
    )

    c["TakeProfitPct"] = pd.to_numeric(
        c["TakeProfitPct"],
        errors="coerce",
    )

    targets = c[
        (c["TakeProfitPct"] == 3)
        & (c["ExitType"] == "TAKE")
    ].copy()

    targets = targets.drop_duplicates(
        subset=[
            "DetectionDate",
            "Code",
        ]
    )

    print("=" * 90)
    print("J1 AFTER +3 ANALYSIS")
    print("=" * 90)
    print("Targets :", len(targets))
    print()

    rows = []

    for _, row in targets.iterrows():

        detection_date = str(
            row["DetectionDate"]
        )

        code = normalize_code(
            row["Code"]
        )

        base = datetime.strptime(
            detection_date,
            "%Y-%m-%d",
        )

        bars = None
        trade_date = None

        for offset in range(1, 8):

            candidate = (
                base
                + timedelta(days=offset)
            )

            if candidate.weekday() >= 5:
                continue

            date_text = (
                candidate.strftime(
                    "%Y-%m-%d"
                )
            )

            candidate_bars = (
                download_5m(
                    code,
                    date_text,
                )
            )

            if (
                candidate_bars is not None
                and not candidate_bars.empty
            ):
                bars = candidate_bars
                trade_date = date_text
                break

        if bars is None:
            print(
                f"NO DATA : "
                f"{detection_date} {code}"
            )
            continue

        work = bars.copy()

        for col in [
            "Open",
            "High",
            "Low",
            "Close",
        ]:
            work[col] = pd.to_numeric(
                work[col],
                errors="coerce",
            )

        work = work.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )

        if work.empty:
            continue

        entry = float(
            work["Open"].iloc[0]
        )

        t3 = first_hit_time(
            work,
            entry,
            3,
        )

        if t3 is None:
            continue

        t4 = first_hit_time(
            work,
            entry,
            4,
        )

        t5 = first_hit_time(
            work,
            entry,
            5,
        )

        t7 = first_hit_time(
            work,
            entry,
            7,
        )

        t10 = first_hit_time(
            work,
            entry,
            10,
        )

        max_pct = (
            float(work["High"].max())
            / entry
            - 1
        ) * 100

        close_pct = (
            float(work["Close"].iloc[-1])
            / entry
            - 1
        ) * 100

        after3 = work[
            work.index >= t3
        ].copy()

        after3_min_pct = (
            float(after3["Low"].min())
            / entry
            - 1
        ) * 100

        after3_drawdown_pct = (
            after3_min_pct
            - 3.0
        )

        rows.append(
            {
                "DetectionDate":
                    detection_date,
                "TradeDate":
                    trade_date,
                "Code":
                    code,
                "Name":
                    row["Name"],
                "NextOpenGapPct":
                    row["NextOpenGapPct"],
                "EntryPrice":
                    entry,
                "Plus3Time":
                    fmt_time(t3),
                "Plus4Time":
                    fmt_time(t4),
                "Plus5Time":
                    fmt_time(t5),
                "Plus7Time":
                    fmt_time(t7),
                "Plus10Time":
                    fmt_time(t10),
                "MaxPct":
                    max_pct,
                "ClosePct":
                    close_pct,
                "After3MinPct":
                    after3_min_pct,
                "After3DrawdownPct":
                    after3_drawdown_pct,
            }
        )

    out = pd.DataFrame(rows)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 120)
    print("RESULT")
    print("=" * 120)

    if out.empty:
        print("No rows.")
        return

    cols = [
        "DetectionDate",
        "Code",
        "Name",
        "NextOpenGapPct",
        "Plus3Time",
        "Plus4Time",
        "Plus5Time",
        "Plus7Time",
        "Plus10Time",
        "MaxPct",
        "After3MinPct",
        "After3DrawdownPct",
        "ClosePct",
    ]

    print(
        out[cols]
        .round(2)
        .to_string(index=False)
    )

    print()
    print("Saved :", output_path)


if __name__ == "__main__":
    main()
'''

dst.write_text(
    prefix + new_main,
    encoding="utf-8",
)

print(f"CREATED : {dst}")
