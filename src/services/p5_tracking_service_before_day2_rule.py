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
