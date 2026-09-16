from pathlib import Path
import pandas as pd


RESULTS_DIR = Path("results")
OUTPUT_DIR = Path("data/analysis")
OUTPUT_FILE = OUTPUT_DIR / "p5_backtest_panel.csv"

LOAD_START_DATE = "2026-08-14"
START_DATE = "2026-08-17"
END_DATE = "2026-08-27"


def normalize_code(value):
    if pd.isna(value):
        return ""
    code = str(value).strip()
    if code.endswith(".0"):
        code = code[:-2]
    return code


def to_num(value):
    return pd.to_numeric(value, errors="coerce")


def load_result_files():
    files = {}

    for path in sorted(
        RESULTS_DIR.glob("*_stock_result.csv")
    ):
        run_date = path.name[:10]

        if run_date < LOAD_START_DATE:
            continue

        try:
            df = pd.read_csv(
                path,
                encoding="utf-8-sig",
                dtype={"コード": str},
            )
        except Exception as e:
            print(
                "READ ERROR:",
                path.name,
                e,
            )
            continue

        if "コード" not in df.columns:
            continue

        df["コード"] = (
            df["コード"]
            .map(normalize_code)
        )

        files[run_date] = df

    return files


def valid_rows_for_date(
    df,
    run_date,
):
    if "_data_date" not in df.columns:
        return df.iloc[0:0].copy()

    dates = pd.to_datetime(
        df["_data_date"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    return df.loc[
        dates == run_date
    ].copy()


def build_close_map(
    files,
):
    close_maps = {}

    for run_date, df in files.items():

        valid = valid_rows_for_date(
            df,
            run_date,
        )

        mapping = {}

        for _, row in valid.iterrows():

            code = normalize_code(
                row.get("コード")
            )

            close = to_num(
                row.get("終値")
            )

            if (
                code
                and pd.notna(close)
            ):
                mapping[code] = float(close)

        close_maps[run_date] = mapping

    return close_maps


def build_chg1_map(
    df,
):
    result = {}

    if "前日比" not in df.columns:
        return result

    for _, row in df.iterrows():

        code = normalize_code(
            row.get("コード")
        )

        value = to_num(
            row.get("前日比")
        )

        if (
            code
            and pd.notna(value)
        ):
            result[code] = float(value)

    return result


def judge_day2(
    day1,
    day2,
    change5,
    volume_ratio20,
):
    values = [
        day1,
        day2,
        change5,
        volume_ratio20,
    ]

    if any(
        pd.isna(v)
        for v in values
    ):
        return "", ""

    drop = day2 - day1

    if (
        day1 >= 3.0
        and day1 < 8.0
    ):
        return (
            "見送り",
            "Day1 3-8%除外",
        )

    if drop >= -3.5:
        return (
            "買い",
            "Drop>=-3.5",
        )

    if drop >= -5.0:

        if (
            change5 < 20
            and volume_ratio20 < 3
        ):
            return (
                "買い",
                "Drop混在ゾーン救済",
            )

        return (
            "見送り",
            "Drop混在ゾーン除外",
        )

    return (
        "見送り",
        "Drop<-5.0",
    )


def pct_change(
    base,
    price,
):
    if (
        pd.isna(base)
        or pd.isna(price)
        or base == 0
    ):
        return pd.NA

    return round(
        (
            price / base - 1
        ) * 100,
        2,
    )


def main():

    files = load_result_files()

    run_dates = sorted(
        files.keys()
    )

    close_maps = build_close_map(
        files
    )

    trading_dates = [
        d
        for d in run_dates
        if len(
            valid_rows_for_date(
                files[d],
                d,
            )
        ) > 0
    ]

    print(
        "利用営業日:",
        trading_dates,
    )

    rows = []

    for pos, detection_date in enumerate(
        trading_dates
    ):

        if (
            detection_date < START_DATE
            or detection_date > END_DATE
        ):
            continue

        df = valid_rows_for_date(
            files[detection_date],
            detection_date,
        )

        if df.empty:
            continue

        # ----------------------------------------
        # 前営業日の前日比マップ
        # Alert F 用
        # ----------------------------------------

        prev_chg1_map = {}

        if pos > 0:

            prev_date = trading_dates[
                pos - 1
            ]

            prev_df = (
                valid_rows_for_date(
                    files[prev_date],
                    prev_date,
                )
            )

            prev_chg1_map = (
                build_chg1_map(
                    prev_df
                )
            )

        candidate_count = 0

        for _, row in df.iterrows():

            code = normalize_code(
                row.get("コード")
            )

            if not code:
                continue

            score = to_num(
                row.get("初動スコア")
            )

            chg1 = to_num(
                row.get("前日比")
            )

            chg5 = to_num(
                row.get("5日騰落率")
            )

            chg20 = to_num(
                row.get("20日騰落率")
            )

            rsi = to_num(
                row.get("RSI")
            )

            vol = to_num(
                row.get("VolumeRatio")
            )

            vol20 = to_num(
                row.get("VolumeRatio20")
            )

            ma25dev = to_num(
                row.get("MA25Deviation")
            )

            base_price = to_num(
                row.get("終値")
            )

            prev_chg1 = (
                prev_chg1_map.get(
                    code,
                    float("nan"),
                )
            )

            # ------------------------------------
            # 現行 A
            # ------------------------------------

            alert_a = (
                pd.notna(chg20)
                and pd.notna(chg1)
                and pd.notna(rsi)
                and pd.notna(vol)
                and chg20 >= 25
                and chg1 < 8
                and rsi >= 75
                and vol <= 2.5
            )

            # ------------------------------------
            # 現行 C
            # ------------------------------------

            alert_c = (
                pd.notna(chg1)
                and pd.notna(chg5)
                and pd.notna(rsi)
                and pd.notna(vol)
                and chg1 >= 12
                and chg5 < 15
                and rsi < 60
                and vol >= 4
            )

            # ------------------------------------
            # 現行 D
            # ------------------------------------

            alert_d = (
                (
                    pd.notna(rsi)
                    and pd.notna(chg5)
                    and rsi >= 95
                    and chg5 >= 40
                )
                or
                (
                    pd.notna(ma25dev)
                    and ma25dev >= 80
                )
            )

            # ------------------------------------
            # 現行 F
            # ------------------------------------

            alert_f = (
                pd.notna(prev_chg1)
                and pd.notna(chg1)
                and prev_chg1 >= 10
                and chg1 < 8
            )

            danger4 = (
                alert_a
                or alert_c
                or alert_d
                or alert_f
            )

            # ------------------------------------
            # 正式 P5
            # ------------------------------------

            p5 = (
                pd.notna(score)
                and pd.notna(chg5)
                and pd.notna(vol20)
                and 3 <= score <= 4
                and chg5 > 0
                and vol20 > 1
                and not danger4
            )

            if not p5:
                continue

            candidate_count += 1

            future_dates = [
                d
                for d in trading_dates
                if d > detection_date
            ]

            prices = {}

            for day_no in range(
                1,
                6,
            ):

                if len(future_dates) >= day_no:

                    d = future_dates[
                        day_no - 1
                    ]

                    prices[
                        day_no
                    ] = (
                        close_maps
                        .get(d, {})
                        .get(
                            code,
                            float("nan"),
                        )
                    )

                else:
                    prices[
                        day_no
                    ] = float("nan")

            changes = {
                n: pct_change(
                    base_price,
                    prices[n],
                )
                for n in range(
                    1,
                    6,
                )
            }

            day1 = to_num(
                changes[1]
            )

            day2 = to_num(
                changes[2]
            )

            if (
                pd.notna(day1)
                and pd.notna(day2)
            ):
                drop = round(
                    day2 - day1,
                    2,
                )
            else:
                drop = pd.NA

            decision, reason = (
                judge_day2(
                    day1,
                    day2,
                    chg5,
                    vol20,
                )
            )

            rows.append(
                {
                    "DetectionDate":
                        detection_date,

                    "Code":
                        code,

                    "Name":
                        row.get(
                            "銘柄名",
                            "",
                        ),

                    "BasePrice":
                        base_price,

                    "InitialScore":
                        score,

                    "Change1":
                        chg1,

                    "Change5":
                        chg5,

                    "Change20":
                        chg20,

                    "RSI":
                        rsi,

                    "VolumeRatio":
                        vol,

                    "VolumeRatio20":
                        vol20,

                    "MA25Deviation":
                        ma25dev,

                    "PrevChange1":
                        prev_chg1,

                    "AlertA":
                        alert_a,

                    "AlertC":
                        alert_c,

                    "AlertD":
                        alert_d,

                    "AlertF":
                        alert_f,

                    "Day1":
                        changes[1],

                    "Day2":
                        changes[2],

                    "Drop":
                        drop,

                    "Day2Decision":
                        decision,

                    "Day2Reason":
                        reason,

                    "Day3":
                        changes[3],

                    "Day4":
                        changes[4],

                    "Day5":
                        changes[5],
                }
            )

        print(
            detection_date,
            "P5候補:",
            candidate_count,
        )

    panel = pd.DataFrame(
        rows
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    panel.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        "保存:",
        OUTPUT_FILE,
    )

    print(
        "候補総数:",
        len(panel),
    )

    if not panel.empty:

        print(
            "Day1取得:",
            panel["Day1"]
            .notna()
            .sum(),
        )

        print(
            "Day2取得:",
            panel["Day2"]
            .notna()
            .sum(),
        )

        print(
            "Day3取得:",
            panel["Day3"]
            .notna()
            .sum(),
        )

        print(
            "Day5取得:",
            panel["Day5"]
            .notna()
            .sum(),
        )


if __name__ == "__main__":
    main()

