from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

RESULTS_DIR = ROOT_DIR / "results"

TRACKING_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "initial_move_tracking_rebuilt.csv"
)

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "buy_avoid_alert_analysis.csv"
)


def normalize_code(value):
    return (
        str(value)
        .replace(".0", "")
        .strip()
    )


def get_prev_change(code, date_text):

    cache_file = (
        ROOT_DIR
        / "data"
        / "cache"
        / f"{code}.csv"
    )

    if not cache_file.exists():
        return pd.NA

    try:
        df = pd.read_csv(cache_file)
    except Exception:
        return pd.NA

    if (
        "Date" not in df.columns
        or "Close" not in df.columns
    ):
        return pd.NA

    df = df.copy()

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
        utc=True,
    )

    df["DateKey"] = (
        df["Date"]
        .dt
        .tz_convert("Asia/Tokyo")
        .dt
        .strftime("%Y-%m-%d")
    )

    df["Close"] = pd.to_numeric(
        df["Close"],
        errors="coerce",
    )

    df = (
        df
        .dropna(
            subset=[
                "DateKey",
                "Close",
            ]
        )
        .sort_values("Date")
        .reset_index(drop=True)
    )

    matches = df.index[
        df["DateKey"] == date_text
    ].tolist()

    if not matches:
        return pd.NA

    current_index = matches[-1]

    # 当日より2営業日前の終値が必要
    # PREV_CHG1 =
    # 前営業日の終値 / その前営業日の終値 - 1
    if current_index < 2:
        return pd.NA

    prev_close = df.loc[
        current_index - 1,
        "Close",
    ]

    prev_prev_close = df.loc[
        current_index - 2,
        "Close",
    ]

    if (
        pd.isna(prev_close)
        or pd.isna(prev_prev_close)
        or prev_prev_close == 0
    ):
        return pd.NA

    return round(
        (
            prev_close
            / prev_prev_close
            - 1
        )
        * 100,
        2,
    )


def to_number(value):

    return pd.to_numeric(
        value,
        errors="coerce",
    )


def main():

    tracking = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
    )

    tracking = tracking[
        tracking["検出日"]
        >= "2026-08-18"
    ].copy()

    rows = []

    total = len(tracking)

    for i, (_, track_row) in enumerate(
        tracking.iterrows(),
        1,
    ):

        date_text = str(
            track_row["検出日"]
        )[:10]

        code = normalize_code(
            track_row["コード"]
        )

        result_file = (
            RESULTS_DIR
            / f"{date_text}_stock_result.csv"
        )

        if not result_file.exists():
            continue

        try:
            result_df = pd.read_csv(
                result_file,
                encoding="utf-8-sig",
                dtype={
                    "コード": str,
                },
            )
        except Exception:
            continue

        result_df["コード"] = (
            result_df["コード"]
            .map(normalize_code)
        )

        target = result_df[
            result_df["コード"] == code
        ]

        if target.empty:
            continue

        r = target.iloc[0]

        score = to_number(
            r.get("初動スコア")
        )

        chg1 = to_number(
            r.get("前日比")
        )

        chg5 = to_number(
            r.get("5日騰落率")
        )

        chg20 = to_number(
            r.get("20日騰落率")
        )

        rsi = to_number(
            r.get("RSI")
        )

        volume_ratio = to_number(
            r.get("VolumeRatio")
        )

        volume_ratio20 = to_number(
            r.get("VolumeRatio20")
        )

        ma25_dev = to_number(
            r.get("MA25Deviation")
        )

        prev_chg1 = get_prev_change(
            code,
            date_text,
        )

        # ============================================
        # A_STALL
        # ============================================

        a_stall = (
            pd.notna(chg20)
            and pd.notna(chg1)
            and pd.notna(rsi)
            and pd.notna(volume_ratio)
            and chg20 >= 25
            and chg1 < 8
            and rsi >= 75
            and volume_ratio <= 2.5
        )

        # ============================================
        # C_SPIKE
        # ============================================

        c_spike = (
            pd.notna(chg1)
            and pd.notna(chg5)
            and pd.notna(rsi)
            and pd.notna(volume_ratio)
            and chg1 >= 12
            and chg5 < 15
            and rsi < 60
            and volume_ratio >= 4
        )

        # ============================================
        # D_OVERHEAT
        # ============================================

        d_overheat = (
            (
                pd.notna(rsi)
                and pd.notna(chg5)
                and rsi >= 95
                and chg5 >= 40
            )
            or
            (
                pd.notna(ma25_dev)
                and ma25_dev >= 80
            )
        )

        # ============================================
        # F_DECEL
        # ============================================

        f_decel = (
            pd.notna(prev_chg1)
            and pd.notna(chg1)
            and prev_chg1 >= 10
            and chg1 < 8
        )

        # ============================================
        # H2
        # ============================================

        h2 = (
            pd.notna(score)
            and pd.notna(volume_ratio20)
            and score <= 2
            and volume_ratio20 < 3
        )

        alerts = []

        if a_stall:
            alerts.append("A_STALL")

        if c_spike:
            alerts.append("C_SPIKE")

        if d_overheat:
            alerts.append("D_OVERHEAT")

        if f_decel:
            alerts.append("F_DECEL")

        if h2:
            alerts.append("H2")

        max3_values = []

        for day in range(1, 4):

            value = to_number(
                track_row.get(
                    f"{day}日後騰落率"
                )
            )

            if pd.notna(value):
                max3_values.append(
                    float(value)
                )

        max3 = (
            max(max3_values)
            if len(max3_values) == 3
            else pd.NA
        )

        rows.append({
            "検出日":
                date_text,

            "コード":
                code,

            "銘柄名":
                track_row["銘柄名"],

            "初動スコア":
                score,

            "CHG1":
                chg1,

            "CHG5":
                chg5,

            "CHG20":
                chg20,

            "PREV_CHG1":
                prev_chg1,

            "RSI":
                rsi,

            "VolumeRatio":
                volume_ratio,

            "VolumeRatio20":
                volume_ratio20,

            "MA25Deviation":
                ma25_dev,

            "A_STALL":
                a_stall,

            "C_SPIKE":
                c_spike,

            "D_OVERHEAT":
                d_overheat,

            "F_DECEL":
                f_decel,

            "H2":
                h2,

            "買い回避":
                len(alerts) > 0,

            "買い回避理由":
                " / ".join(alerts),

            "Max3":
                (
                    round(max3, 2)
                    if pd.notna(max3)
                    else ""
                ),
        })

        if (
            i % 20 == 0
            or i == total
        ):
            print(
                f"進捗 : {i} / {total}"
            )

    result = pd.DataFrame(rows)

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "保存 :",
        OUTPUT_FILE
    )

    print(
        "件数 :",
        len(result)
    )

    print()

    print("=" * 80)
    print("買い回避アラート件数")
    print("=" * 80)

    for column in [
        "A_STALL",
        "C_SPIKE",
        "D_OVERHEAT",
        "F_DECEL",
        "H2",
    ]:

        count = int(
            result[column].sum()
        )

        print(
            f"{column:12s} : {count}"
        )

    print()

    print(
        "買い回避あり :",
        int(
            result["買い回避"].sum()
        )
    )

    print(
        "買い回避なし :",
        int(
            (~result["買い回避"]).sum()
        )
    )

    # ============================================
    # Max3確定分
    # ============================================

    confirmed = result[
        pd.notna(
            pd.to_numeric(
                result["Max3"],
                errors="coerce",
            )
        )
    ].copy()

    confirmed["Max3"] = pd.to_numeric(
        confirmed["Max3"],
        errors="coerce",
    )

    print()
    print("=" * 80)
    print("Max3確定分")
    print("=" * 80)

    print(
        "件数 :",
        len(confirmed)
    )

    for avoid in [
        False,
        True,
    ]:

        part = confirmed[
            confirmed["買い回避"] == avoid
        ]

        if part.empty:
            continue

        label = (
            "買い回避あり"
            if avoid
            else "買い回避なし"
        )

        print()
        print(label)

        print(
            "件数       :",
            len(part)
        )

        print(
            "Max3平均   :",
            round(
                part["Max3"].mean(),
                2,
            )
        )

        print(
            "Max3中央値 :",
            round(
                part["Max3"].median(),
                2,
            )
        )

        print(
            "+5%到達率  :",
            round(
                (
                    part["Max3"] >= 5
                ).mean()
                * 100,
                1,
            )
        )

        print(
            "+10%到達率 :",
            round(
                (
                    part["Max3"] >= 10
                ).mean()
                * 100,
                1,
            )
        )

    print()

    print("=" * 80)
    print("買い回避該当銘柄")
    print("=" * 80)

    avoid_rows = confirmed[
        confirmed["買い回避"]
    ][[
        "検出日",
        "コード",
        "銘柄名",
        "初動スコア",
        "買い回避理由",
        "PREV_CHG1",
        "CHG1",
        "CHG5",
        "CHG20",
        "RSI",
        "VolumeRatio",
        "VolumeRatio20",
        "MA25Deviation",
        "Max3",
    ]]

    if avoid_rows.empty:

        print(
            "該当なし"
        )

    else:

        print(
            avoid_rows.to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()