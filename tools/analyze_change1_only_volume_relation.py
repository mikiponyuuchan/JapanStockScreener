from pathlib import Path

import pandas as pd


INPUT = Path(
    "data/analysis/initial_move_change1_only_pre5.csv"
)


def main():

    df = pd.read_csv(
        INPUT,
        encoding="utf-8-sig"
    )

    vol = "DetectionVolumeVsPre5"
    high = "MaxHigh5Pct"
    low = "MinLow5Pct"

    for c in [vol, high, low]:
        df[c] = pd.to_numeric(
            df[c],
            errors="coerce"
        )

    df = df.dropna(
        subset=[vol, high]
    ).copy()

    print("=" * 90)
    print("CHANGE1-ONLY : VOLUME vs NEXT 5D HIGH")
    print("=" * 90)
    print("N :", len(df))

    # ==========================================
    # 相関
    # ==========================================

    pearson = df[
        [vol, high]
    ].corr(
        method="pearson"
    ).iloc[0, 1]

    spearman = df[
        [vol, high]
    ].corr(
        method="spearman"
    ).iloc[0, 1]

    print()
    print("CORRELATION")
    print("-" * 90)
    print(
        f"Pearson  : {pearson:.3f}"
    )
    print(
        f"Spearman : {spearman:.3f}"
    )

    # ==========================================
    # 出来高帯
    # ==========================================

    df["VolumeBand"] = pd.cut(
        df[vol],
        bins=[
            float("-inf"),
            1.0,
            2.0,
            float("inf"),
        ],
        labels=[
            "<1.0",
            "1.0-2.0",
            ">=2.0",
        ],
        right=False,
    )

    print()
    print("=" * 90)
    print("VOLUME BAND PERFORMANCE")
    print("=" * 90)

    for band in [
        "<1.0",
        "1.0-2.0",
        ">=2.0",
    ]:

        g = df[
            df["VolumeBand"] == band
        ]

        if g.empty:
            continue

        print()
        print(
            f"[{band}] N={len(g)}"
        )

        print(
            f"  Volume median : "
            f"{g[vol].median():.2f}x"
        )

        print(
            f"  MaxHigh5 "
            f"mean={g[high].mean():.2f}%  "
            f"median={g[high].median():.2f}%"
        )

        print(
            f"  +5  = "
            f"{(g[high] >= 5).mean() * 100:.1f}%"
        )

        print(
            f"  +10 = "
            f"{(g[high] >= 10).mean() * 100:.1f}%"
        )

        print(
            f"  +20 = "
            f"{(g[high] >= 20).mean() * 100:.1f}%"
        )

        if g[low].notna().any():

            print(
                f"  MinLow5 median = "
                f"{g[low].median():.2f}%"
            )

            print(
                f"  -5 touch = "
                f"{(g[low] <= -5).mean() * 100:.1f}%"
            )

    # ==========================================
    # 低い順
    # ==========================================

    print()
    print("=" * 90)
    print("SORTED BY DetectionVolumeVsPre5")
    print("=" * 90)

    cols = [
        "DetectionDate",
        "Code",
        "Name",
        vol,
        "Change1",
        "Change5",
        high,
        low,
        "PeakDay5",
        "OutcomeGroup",
    ]

    cols = [
        c for c in cols
        if c in df.columns
    ]

    print(
        df[
            cols
        ]
        .sort_values(vol)
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
