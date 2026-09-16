import io
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

import pandas as pd

from services.yahoo_service import (
    _download_history_batch,
)

from services.tracking_service import (
    add_business_days,
    _find_price,
    get_price_on_or_after,
    calculate_change,
)


P5_TRACKING_DIR = Path("data/tracking")

P5_TRACKING_FILE = (
    P5_TRACKING_DIR / "p5_tracking.csv"
)


COLUMNS = [
    "DetectionDate",
    "Code",
    "Name",
    "BasePrice",
    "InitialScore",
    "Change5",
    "VolumeRatio20",
    "Day1Price",
    "Day1",
    "Day2Price",
    "Day2",
    "Drop",
    "BuyDecision",
    "BuyReason",
]


def _empty_tracking():
    return pd.DataFrame(
        columns=COLUMNS
    )


def load_p5_tracking():

    P5_TRACKING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not P5_TRACKING_FILE.exists():
        return _empty_tracking()

    try:
        df = pd.read_csv(
            P5_TRACKING_FILE,
            encoding="utf-8-sig",
            dtype={
                "Code": str,
            },
        )

    except Exception as e:
        print(
            "P5 tracking load ERROR :",
            e,
        )
        return _empty_tracking()

    for column in COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    return df[COLUMNS].copy()


def _save_p5_tracking(df):

    P5_TRACKING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        P5_TRACKING_FILE,
        index=False,
        encoding="utf-8-sig",
    )


def _value(row, column, default=None):

    if column not in row.index:
        return default

    value = row[column]

    if pd.isna(value):
        return default

    return value


def _number(row, column):

    value = _value(
        row,
        column,
        pd.NA,
    )

    return pd.to_numeric(
        value,
        errors="coerce",
    )


def record_p5_candidates(
    p5_candidates,
):

    if p5_candidates is None:
        return load_p5_tracking()

    if p5_candidates.empty:
        return load_p5_tracking()

    tracking = load_p5_tracking()

    if "_data_date" in p5_candidates.columns:
        detection_date = str(
            p5_candidates[
                "_data_date"
            ].iloc[0]
        )
    else:
        detection_date = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )

    try:
        detection_date = (
            pd.Timestamp(
                detection_date
            )
            .strftime("%Y-%m-%d")
        )
    except Exception:
        detection_date = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )

    existing_keys = set()

    for _, old_row in tracking.iterrows():

        old_date = str(
            _value(
                old_row,
                "DetectionDate",
                "",
            )
        )

        old_code = str(
            _value(
                old_row,
                "Code",
                "",
            )
        ).replace(
            ".0",
            "",
        ).strip()

        existing_keys.add(
            (
                old_date,
                old_code,
            )
        )

    new_rows = []

    for _, row in p5_candidates.iterrows():

        code = str(
            _value(
                row,
                "\u30b3\u30fc\u30c9",
                "",
            )
        ).replace(
            ".0",
            "",
        ).strip()

        if not code:
            continue

        key = (
            detection_date,
            code,
        )

        if key in existing_keys:
            continue

        base_price = _number(
            row,
            "\u7d42\u5024",
        )

        if pd.isna(base_price):
            continue

        name = str(
            _value(
                row,
                "\u9298\u67c4\u540d",
                "",
            )
        )

        new_rows.append(
            {
                "DetectionDate":
                    detection_date,

                "Code":
                    code,

                "Name":
                    name,

                "BasePrice":
                    float(base_price),

                "InitialScore":
                    _number(
                        row,
                        "\u521d\u52d5\u30b9\u30b3\u30a2",
                    ),

                "Change5":
                    _number(
                        row,
                        "5\u65e5\u9a30\u843d\u7387",
                    ),

                "VolumeRatio20":
                    _number(
                        row,
                        "VolumeRatio20",
                    ),

                "Day1Price":
                    pd.NA,

                "Day1":
                    pd.NA,

                "Day2Price":
                    pd.NA,

                "Day2":
                    pd.NA,

                "Drop":
                    pd.NA,

                "BuyDecision":
                    "",

                "BuyReason":
                    "",
            }
        )

        existing_keys.add(key)

    if new_rows:

        tracking = pd.concat(
            [
                tracking,
                pd.DataFrame(new_rows),
            ],
            ignore_index=True,
        )

        _save_p5_tracking(
            tracking
        )

    return tracking

# ============================================================
# P5 Day2 buy decision
# ============================================================

def _judge_p5_day2(
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

    if any(pd.isna(value) for value in values):
        return "", ""

    drop = (
        day2
        - day1
    )

    # --------------------------------------------------------
    # Day1 3%以上8%未満は買わない
    # --------------------------------------------------------

    if (
        day1 >= 3.0
        and day1 < 8.0
    ):
        return (
            "見送り",
            "Day1 3-8%除外",
        )

    # --------------------------------------------------------
    # 安全圏
    # Drop >= -3.5
    # --------------------------------------------------------

    if drop >= -3.5:
        return (
            "買い",
            "Drop>=-3.5",
        )

    # --------------------------------------------------------
    # 混在ゾーン
    # -5.0 <= Drop < -3.5
    #
    # Change5 < 20
    # AND VolumeRatio20 < 3
    # の場合のみ救済
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Drop < -5.0
    # --------------------------------------------------------

    return (
        "見送り",
        "Drop<-5.0",
    )


# ============================================================
# P5 tracking update
#
# Detection Day = Day0
# Day1 = 1営業日後
# Day2 = 2営業日後
#
# Day2終値が取得できた時点で
# 最終P5買い判定を行う。
# ============================================================

def update_p5_tracking(
    tracking_df=None,
    data_date=None,
):

    if tracking_df is None:
        tracking_df = load_p5_tracking()

    if tracking_df.empty:
        return tracking_df

    # --------------------------------------------------------
    # 基準日
    # --------------------------------------------------------

    if data_date is not None:

        market_date = pd.Timestamp(
            data_date
        ).normalize()

    else:

        market_date = pd.Timestamp(
            datetime.now().date()
        )

    # --------------------------------------------------------
    # Yahoo取得対象コード
    # --------------------------------------------------------

    target_codes = set()

    for _, row in tracking_df.iterrows():

        try:
            detection_date = pd.Timestamp(
                row["DetectionDate"]
            ).normalize()
        except Exception:
            continue

        code = str(
            _value(
                row,
                "Code",
                "",
            )
        ).replace(
            ".0",
            "",
        ).strip()

        if not code:
            continue

        day1_date = add_business_days(
            detection_date,
            1,
        )

        day2_date = add_business_days(
            detection_date,
            2,
        )

        day1_price = pd.to_numeric(
            row["Day1Price"],
            errors="coerce",
        )

        day2_price = pd.to_numeric(
            row["Day2Price"],
            errors="coerce",
        )

        if (
            market_date >= day1_date
            and pd.isna(day1_price)
        ):
            target_codes.add(code)

        if (
            market_date >= day2_date
            and pd.isna(day2_price)
        ):
            target_codes.add(code)

    target_codes = sorted(
        target_codes
    )

    # --------------------------------------------------------
    # Yahoo一括取得
    # --------------------------------------------------------

    yahoo_results = {}

    if target_codes:

        try:

            with redirect_stdout(
                io.StringIO()
            ):

                yahoo_results = (
                    _download_history_batch(
                        target_codes,
                        period="10d",
                        batch_size=100,
                    )
                )

        except Exception as e:

            print(
                "P5 Yahoo batch ERROR :",
                e,
            )

            yahoo_results = {}

    # --------------------------------------------------------
    # Day1 / Day2 更新
    # --------------------------------------------------------

    updated_count = 0
    judged_count = 0

    for index, row in tracking_df.iterrows():

        try:

            detection_date = pd.Timestamp(
                row["DetectionDate"]
            ).normalize()

        except Exception:
            continue

        code = str(
            _value(
                row,
                "Code",
                "",
            )
        ).replace(
            ".0",
            "",
        ).strip()

        if not code:
            continue

        base_price = pd.to_numeric(
            row["BasePrice"],
            errors="coerce",
        )

        if pd.isna(base_price):
            continue

        history = yahoo_results.get(
            code
        )

        row_updated = False

        # ----------------------------------------------------
        # Day1
        # ----------------------------------------------------

        day1_date = add_business_days(
            detection_date,
            1,
        )

        day1_price = pd.to_numeric(
            tracking_df.at[
                index,
                "Day1Price",
            ],
            errors="coerce",
        )

        if (
            market_date >= day1_date
            and pd.isna(day1_price)
        ):

            price = _find_price(
                history,
                day1_date,
            )

            if price is None:

                try:
                    price = get_price_on_or_after(
                        code,
                        day1_date,
                    )
                except Exception:
                    price = None

            if price is not None:

                tracking_df.at[
                    index,
                    "Day1Price",
                ] = round(
                    price,
                    2,
                )

                day1_change = calculate_change(
                    base_price,
                    price,
                )

                tracking_df.at[
                    index,
                    "Day1",
                ] = day1_change

                row_updated = True

        # ----------------------------------------------------
        # Day2
        # ----------------------------------------------------

        day2_date = add_business_days(
            detection_date,
            2,
        )

        day2_price = pd.to_numeric(
            tracking_df.at[
                index,
                "Day2Price",
            ],
            errors="coerce",
        )

        if (
            market_date >= day2_date
            and pd.isna(day2_price)
        ):

            price = _find_price(
                history,
                day2_date,
            )

            if price is None:

                try:
                    price = get_price_on_or_after(
                        code,
                        day2_date,
                    )
                except Exception:
                    price = None

            if price is not None:

                tracking_df.at[
                    index,
                    "Day2Price",
                ] = round(
                    price,
                    2,
                )

                day2_change = calculate_change(
                    base_price,
                    price,
                )

                tracking_df.at[
                    index,
                    "Day2",
                ] = day2_change

                row_updated = True

        # ----------------------------------------------------
        # Drop
        # ----------------------------------------------------

        day1 = pd.to_numeric(
            tracking_df.at[
                index,
                "Day1",
            ],
            errors="coerce",
        )

        day2 = pd.to_numeric(
            tracking_df.at[
                index,
                "Day2",
            ],
            errors="coerce",
        )

        if (
            pd.notna(day1)
            and pd.notna(day2)
        ):

            drop = (
                day2
                - day1
            )

            tracking_df.at[
                index,
                "Drop",
            ] = round(
                drop,
                2,
            )

            # ------------------------------------------------
            # 最終買い判定
            # ------------------------------------------------

            current_decision = str(
                _value(
                    tracking_df.loc[index],
                    "BuyDecision",
                    "",
                )
            ).strip()

            if not current_decision:

                change5 = pd.to_numeric(
                    tracking_df.at[
                        index,
                        "Change5",
                    ],
                    errors="coerce",
                )

                volume_ratio20 = pd.to_numeric(
                    tracking_df.at[
                        index,
                        "VolumeRatio20",
                    ],
                    errors="coerce",
                )

                decision, reason = (
                    _judge_p5_day2(
                        day1,
                        day2,
                        change5,
                        volume_ratio20,
                    )
                )

                if decision:

                    tracking_df.at[
                        index,
                        "BuyDecision",
                    ] = decision

                    tracking_df.at[
                        index,
                        "BuyReason",
                    ] = reason

                    judged_count += 1

        if row_updated:
            updated_count += 1

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    _save_p5_tracking(
        tracking_df
    )

    print(
        "P5追跡更新 :",
        updated_count,
        "件",
    )

    print(
        "P5買い判定 :",
        judged_count,
        "件",
    )

    return tracking_df
