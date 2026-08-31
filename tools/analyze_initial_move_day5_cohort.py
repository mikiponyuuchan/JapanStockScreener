from pathlib import Path

import pandas as pd


INPUT_FILE = Path(
    "data/analysis/initial_move_highlow_panel.csv"
)

CURRENT_START_DATE = pd.Timestamp(
    "2026-08-18"
)


def stat_text(s):

    s = pd.to_numeric(
        s,
        errors="coerce"
    ).dropna()

    if s.empty:
        return "N=0"

    return (
        f"N={len(s):3d}  "
        f"mean={s.mean():7.2f}%  "
        f"median={s.median():7.2f}%"
    )


def main():

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    df["DetectionDate"] = pd.to_datetime(
        df["DetectionDate"],
        errors="coerce"
    )

    df["InitialScore"] = pd.to_numeric(
        df["InitialScore"],
        errors="coerce"
    )

    # ==========================================
    # 現行スコア期間だけ
    # ==========================================

    df = df[
        df["DetectionDate"]
        >= CURRENT_START_DATE
    ].copy()

    df = df[
        df["InitialScore"]
        .between(3, 7)
    ].copy()

    # ==========================================
    # 銘柄ごとの最初の検出だけ
    # ==========================================

    first = (
        df
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

    # ==========================================
    # Day5まで成熟している同一コホート
    # ==========================================

    mature = first[
        pd.to_numeric(
            first["Day5ClosePct"],
            errors="coerce"
        ).notna()
    ].copy()

    print("=" * 78)
    print("DAY5 MATURE - FIRST DETECTION COHORT")
    print("=" * 78)

    print(
        "Total :",
        len(mature)
    )

    print()

    print(
        "Score distribution"
    )

    print(
        mature[
            "InitialScore"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    # ==========================================
    # スコア別
    # ==========================================

    for score in range(3, 8):

        g = mature[
            mature["InitialScore"]
            == score
        ].copy()

        if g.empty:
            continue

        print()
        print("=" * 78)
        print(
            f"SCORE {score}   N={len(g)}"
        )
        print("=" * 78)

        # --------------------------------------
        # 同じ銘柄群のMaxHigh推移
        # --------------------------------------

        print()
        print("MAX HIGH")

        for horizon in [
            1, 3, 5
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
                f"Day{horizon}  "
                f"{stat_text(s)}  "
                f"+5={((s >= 5).mean()*100):5.1f}%  "
                f"+10={((s >= 10).mean()*100):5.1f}%  "
                f"+20={((s >= 20).mean()*100):5.1f}%"
            )

        # --------------------------------------
        # 5日以内最大下落
        # --------------------------------------

        print()
        print("MIN LOW")

        for horizon in [
            1, 3, 5
        ]:

            s = pd.to_numeric(
                g[
                    f"MinLow{horizon}Pct"
                ],
                errors="coerce"
            ).dropna()

            if s.empty:
                continue

            print(
                f"Day{horizon}  "
                f"{stat_text(s)}  "
                f"<=-5={((s <= -5).mean()*100):5.1f}%  "
                f"<=-10={((s <= -10).mean()*100):5.1f}%"
            )

        # --------------------------------------
        # Day5までのピーク日
        # --------------------------------------

        peak = pd.to_numeric(
            g["PeakDay5"],
            errors="coerce"
        ).dropna()

        print()
        print("PEAK DAY within 5 days")

        if not peak.empty:

            counts = (
                peak.astype(int)
                .value_counts()
                .sort_index()
            )

            for day in range(1, 6):

                n = int(
                    counts.get(day, 0)
                )

                pct = (
                    n
                    / len(peak)
                    * 100
                )

                print(
                    f"Day{day}: "
                    f"{n:3d} "
                    f"({pct:5.1f}%)"
                )

            print(
                "PeakDay median :",
                round(
                    peak.median(),
                    2
                )
            )

        # --------------------------------------
        # 5日最大上昇と最大下落を並べる
        # --------------------------------------

        high5 = pd.to_numeric(
            g["MaxHigh5Pct"],
            errors="coerce"
        )

        low5 = pd.to_numeric(
            g["MinLow5Pct"],
            errors="coerce"
        )

        valid = (
            high5.notna()
            &
            low5.notna()
        )

        if valid.any():

            print()
            print("5-DAY OPPORTUNITY / RISK")

            print(
                "MaxHigh median :",
                round(
                    high5[valid].median(),
                    2
                ),
                "%"
            )

            print(
                "MinLow median  :",
                round(
                    low5[valid].median(),
                    2
                ),
                "%"
            )

            print(
                "+5% hit        :",
                round(
                    (
                        high5[valid]
                        >= 5
                    ).mean()
                    * 100,
                    1
                ),
                "%"
            )

            print(
                "+10% hit       :",
                round(
                    (
                        high5[valid]
                        >= 10
                    ).mean()
                    * 100,
                    1
                ),
                "%"
            )

            print(
                "-5% touched    :",
                round(
                    (
                        low5[valid]
                        <= -5
                    ).mean()
                    * 100,
                    1
                ),
                "%"
            )

            print(
                "-10% touched   :",
                round(
                    (
                        low5[valid]
                        <= -10
                    ).mean()
                    * 100,
                    1
                ),
                "%"
            )


if __name__ == "__main__":
    main()
