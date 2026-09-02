from datetime import datetime
from pathlib import Path
import shutil

import pandas as pd


TRACKING_FILE = Path(
    "data/tracking/p5_tracking.csv"
)

AUDIT_FILE = Path(
    "data/analysis/p5_tracking_confirmed_audit.csv"
)

BACKUP_DIR = Path(
    "data/tracking/backup"
)


def normalize_code(value):
    if pd.isna(value):
        return ""

    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    return code


def num(value):
    return pd.to_numeric(
        value,
        errors="coerce",
    )


def main():

    if not TRACKING_FILE.exists():
        raise FileNotFoundError(
            TRACKING_FILE
        )

    if not AUDIT_FILE.exists():
        raise FileNotFoundError(
            AUDIT_FILE
        )

    tracking = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig",
        dtype={"Code": str},
    )

    audit = pd.read_csv(
        AUDIT_FILE,
        encoding="utf-8-sig",
        dtype={"Code": str},
    )

    tracking["Code"] = (
        tracking["Code"]
        .map(normalize_code)
    )

    audit["Code"] = (
        audit["Code"]
        .map(normalize_code)
    )

    tracking["DetectionDate"] = (
        pd.to_datetime(
            tracking["DetectionDate"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")
    )

    audit["DetectionDate"] = (
        pd.to_datetime(
            audit["DetectionDate"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")
    )

    audit_map = {}

    for _, row in audit.iterrows():

        key = (
            row["DetectionDate"],
            row["Code"],
        )

        if key in audit_map:
            raise RuntimeError(
                f"Duplicate audit key: {key}"
            )

        audit_map[key] = row

    # --------------------------------------------------------
    # Backup before any modification
    # --------------------------------------------------------

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_file = (
        BACKUP_DIR
        / f"p5_tracking_before_confirmed_fix_{stamp}.csv"
    )

    shutil.copy2(
        TRACKING_FILE,
        backup_file,
    )

    day1_fixed = 0
    day2_fixed = 0
    decision_fixed = 0
    missing_audit = 0

    for index, row in tracking.iterrows():

        key = (
            row["DetectionDate"],
            row["Code"],
        )

        audit_row = audit_map.get(
            key
        )

        if audit_row is None:
            missing_audit += 1
            continue

        # ----------------------------------------------------
        # Day1:
        # update only when confirmed price exists.
        # ----------------------------------------------------

        correct_day1_price = num(
            audit_row.get(
                "CorrectDay1Price"
            )
        )

        correct_day1 = num(
            audit_row.get(
                "CorrectDay1"
            )
        )

        if (
            pd.notna(correct_day1_price)
            and pd.notna(correct_day1)
        ):

            old_price = num(
                tracking.at[
                    index,
                    "Day1Price",
                ]
            )

            old_day1 = num(
                tracking.at[
                    index,
                    "Day1",
                ]
            )

            changed = (
                pd.isna(old_price)
                or pd.isna(old_day1)
                or abs(
                    float(old_price)
                    - float(correct_day1_price)
                ) > 0.001
                or abs(
                    float(old_day1)
                    - float(correct_day1)
                ) > 0.001
            )

            tracking.at[
                index,
                "Day1Price",
            ] = round(
                float(correct_day1_price),
                2,
            )

            tracking.at[
                index,
                "Day1",
            ] = round(
                float(correct_day1),
                2,
            )

            if changed:
                day1_fixed += 1

        # ----------------------------------------------------
        # Day2:
        # update only when confirmed price exists.
        # ----------------------------------------------------

        correct_day2_price = num(
            audit_row.get(
                "CorrectDay2Price"
            )
        )

        correct_day2 = num(
            audit_row.get(
                "CorrectDay2"
            )
        )

        if (
            pd.notna(correct_day2_price)
            and pd.notna(correct_day2)
        ):

            old_price = num(
                tracking.at[
                    index,
                    "Day2Price",
                ]
            )

            old_day2 = num(
                tracking.at[
                    index,
                    "Day2",
                ]
            )

            changed = (
                pd.isna(old_price)
                or pd.isna(old_day2)
                or abs(
                    float(old_price)
                    - float(correct_day2_price)
                ) > 0.001
                or abs(
                    float(old_day2)
                    - float(correct_day2)
                ) > 0.001
            )

            tracking.at[
                index,
                "Day2Price",
            ] = round(
                float(correct_day2_price),
                2,
            )

            tracking.at[
                index,
                "Day2",
            ] = round(
                float(correct_day2),
                2,
            )

            if changed:
                day2_fixed += 1

        # ----------------------------------------------------
        # Drop / decision:
        # update ONLY if confirmed Day1 and Day2 both exist.
        # ----------------------------------------------------

        if (
            pd.notna(correct_day1)
            and pd.notna(correct_day2)
        ):

            correct_drop = num(
                audit_row.get(
                    "CorrectDrop"
                )
            )

            correct_decision = str(
                audit_row.get(
                    "CorrectDecision",
                    "",
                )
            ).strip()

            correct_reason = str(
                audit_row.get(
                    "CorrectReason",
                    "",
                )
            ).strip()

            if pd.notna(correct_drop):

                tracking.at[
                    index,
                    "Drop",
                ] = round(
                    float(correct_drop),
                    2,
                )

            if correct_decision:

                old_decision = str(
                    tracking.at[
                        index,
                        "BuyDecision",
                    ]
                ).strip()

                old_reason = str(
                    tracking.at[
                        index,
                        "BuyReason",
                    ]
                ).strip()

                if (
                    old_decision
                    != correct_decision
                    or old_reason
                    != correct_reason
                ):
                    decision_fixed += 1

                tracking.at[
                    index,
                    "BuyDecision",
                ] = correct_decision

                tracking.at[
                    index,
                    "BuyReason",
                ] = correct_reason

    tracking.to_csv(
        TRACKING_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("=" * 72)
    print("P5 CONFIRMED-CLOSE REPAIR")
    print("=" * 72)
    print(
        "Tracking rows       :",
        len(tracking),
    )
    print(
        "Day1 rows repaired  :",
        day1_fixed,
    )
    print(
        "Day2 rows repaired  :",
        day2_fixed,
    )
    print(
        "Decision rows fixed :",
        decision_fixed,
    )
    print(
        "Missing audit rows  :",
        missing_audit,
    )
    print(
        "Backup              :",
        backup_file,
    )
    print(
        "Saved               :",
        TRACKING_FILE,
    )


if __name__ == "__main__":
    main()
