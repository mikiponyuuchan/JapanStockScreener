from pathlib import Path
from datetime import datetime

import pandas as pd


SUPERVISION_URL = (
    "https://www.jpx.co.jp/listing/"
    "market-alerts/supervision/index.html"
)

SPECIAL_ALERT_URL = (
    "https://www.jpx.co.jp/listing/"
    "measures/alert/01.html"
)

AUDIT_URL = (
    "https://www.jpx.co.jp/listing/"
    "others/adverse-opinion/index.html"
)

OUTPUT_PATH = Path(
    "data/cache/jpx_risk_stocks.csv"
)


def normalize_code(value):
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def add_rows(
    output,
    df,
    risk_type,
    action,
    reason_column=None,
):
    for _, row in df.iterrows():

        code = normalize_code(
            row.get("コード", "")
        )

        if not code:
            continue

        name = str(
            row.get("銘柄名", "")
        ).strip()

        reason = risk_type

        if (
            reason_column
            and reason_column in df.columns
        ):
            value = row.get(
                reason_column,
                "",
            )

            if not pd.isna(value):
                reason = str(value).strip()

        output.append(
            {
                "Code": code,
                "Name": name,
                "RiskType": risk_type,
                "Action": action,
                "Reason": reason,
            }
        )


def load_supervision_rows():
    tables = pd.read_html(
        SUPERVISION_URL
    )

    output = []

    labels = [
        "SUPERVISION_CONFIRMING",
        "SUPERVISION_REVIEW",
        "DELISTING",
    ]

    for index, df in enumerate(tables):

        risk_type = (
            labels[index]
            if index < len(labels)
            else f"SUPERVISION_{index}"
        )

        add_rows(
            output,
            df,
            risk_type,
            "BLOCK",
        )

    return output


def load_special_alert_rows():
    tables = pd.read_html(
        SPECIAL_ALERT_URL
    )

    output = []

    for df in tables:
        add_rows(
            output,
            df,
            "SPECIAL_ALERT",
            "BLOCK",
        )

    return output


def classify_audit_opinion(value):
    if pd.isna(value):
        return "WARN"

    text = str(value).strip()

    block_words = [
        "不適正意見",
        "意見不表明",
        "結論不表明",
        "否定的結論",
    ]

    for word in block_words:
        if word in text:
            return "BLOCK"

    return "WARN"


def load_audit_rows():
    tables = pd.read_html(
        AUDIT_URL
    )

    output = []

    for df in tables:

        if "監査意見等" not in df.columns:
            continue

        for _, row in df.iterrows():

            code = normalize_code(
                row.get("コード", "")
            )

            if not code:
                continue

            name = str(
                row.get("銘柄名", "")
            ).strip()

            opinion = row.get(
                "監査意見等",
                "",
            )

            opinion_text = (
                ""
                if pd.isna(opinion)
                else str(opinion).strip()
            )

            action = classify_audit_opinion(
                opinion_text
            )

            output.append(
                {
                    "Code": code,
                    "Name": name,
                    "RiskType":
                        "AUDIT_OPINION",
                    "Action": action,
                    "Reason": opinion_text,
                }
            )

    return output


def build_jpx_risk_list():
    rows = []

    rows.extend(
        load_supervision_rows()
    )

    rows.extend(
        load_special_alert_rows()
    )

    rows.extend(
        load_audit_rows()
    )

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "JPX risk list is empty."
        )

    df["UpdatedAt"] = (
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    df = df.drop_duplicates(
        subset=[
            "Code",
            "RiskType",
            "Action",
            "Reason",
        ]
    )

    df = df.sort_values(
        [
            "Action",
            "RiskType",
            "Code",
        ]
    ).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ======================================================
    # Safe cache replacement
    #
    # Never write directly to the current valid cache.
    # Write and validate a temporary file first, then replace.
    # ======================================================

    temp_path = OUTPUT_PATH.with_suffix(
        ".tmp.csv"
    )

    try:
        df.to_csv(
            temp_path,
            index=False,
            encoding="utf-8-sig",
        )

        check_df = pd.read_csv(
            temp_path,
            dtype={"Code": str},
            encoding="utf-8-sig",
        )

        required_columns = {
            "Code",
            "RiskType",
            "Action",
            "Reason",
            "UpdatedAt",
        }

        missing_columns = (
            required_columns
            - set(check_df.columns)
        )

        if missing_columns:
            raise RuntimeError(
                "Temporary JPX risk cache "
                "missing columns: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        if check_df.empty:
            raise RuntimeError(
                "Temporary JPX risk cache is empty."
            )

        if len(check_df) != len(df):
            raise RuntimeError(
                "Temporary JPX risk cache "
                "row count mismatch: "
                f"{len(check_df)} != {len(df)}"
            )

        # Atomic replacement on the same filesystem.
        temp_path.replace(
            OUTPUT_PATH
        )

    finally:
        if temp_path.exists():
            temp_path.unlink()

    return df


def load_blocked_codes():
    if not OUTPUT_PATH.exists():
        raise RuntimeError(
            "JPX risk cache not found: "
            f"{OUTPUT_PATH}"
        )

    df = pd.read_csv(
        OUTPUT_PATH,
        dtype={"Code": str},
    )

    required_columns = {
        "Code",
        "Action",
        "UpdatedAt",
    }

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "JPX risk cache is invalid. "
            "Missing columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    updated_values = pd.to_datetime(
        df["UpdatedAt"],
        errors="coerce",
    ).dropna()

    if updated_values.empty:
        raise RuntimeError(
            "JPX risk cache has no valid "
            "UpdatedAt value."
        )

    updated_at = updated_values.max()
    now = pd.Timestamp.now()

    age_days = (
        now - updated_at
    ).total_seconds() / 86400.0

    if age_days >= 3.0:
        print()
        print(
            "WARNING : JPX RISK CACHE "
            "IS STALE"
        )
        print(
            "UpdatedAt :",
            updated_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )
        print(
            "Age       : "
            f"{age_days:.1f} days"
        )
        print(
            "Using last valid cache."
        )
        print()

    blocked = df[
        df["Action"] == "BLOCK"
    ]

    return set(
        blocked["Code"]
        .astype(str)
        .str.strip()
    )


def load_risk_display_map():
    """
    JPX risk cacheから表示用マップを作る。

    Returns
    -------
    dict
        {
            "3133": "JPX BLOCK / 結論不表明・意見不表明",
            "xxxx": "JPX WARN / 限定付適正意見",
        }

    BLOCKとWARNが同一コードに存在する場合は
    BLOCKを優先する。
    """

    if not OUTPUT_PATH.exists():
        raise RuntimeError(
            "JPX risk cache not found: "
            f"{OUTPUT_PATH}"
        )

    df = pd.read_csv(
        OUTPUT_PATH,
        dtype={"Code": str},
        encoding="utf-8-sig",
    )

    required_columns = {
        "Code",
        "Action",
        "Reason",
        "UpdatedAt",
    }

    missing_columns = (
        required_columns - set(df.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "JPX risk cache missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    df["Code"] = df["Code"].map(
        normalize_code
    )

    result = {}

    for code, group in df.groupby("Code"):
        if not code:
            continue

        actions = set(
            group["Action"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        if "BLOCK" in actions:
            action = "BLOCK"
            selected = group[
                group["Action"].astype(str).str.strip()
                == "BLOCK"
            ]
        elif "WARN" in actions:
            action = "WARN"
            selected = group[
                group["Action"].astype(str).str.strip()
                == "WARN"
            ]
        else:
            continue

        reasons = []

        for value in selected["Reason"]:
            if pd.isna(value):
                continue

            reason = str(value).strip()

            display_reason_map = {
                "DELISTING":
                    "整理銘柄",
                "SPECIAL_ALERT":
                    "特別注意銘柄",
                "SUPERVISION_CONFIRMING":
                    "監理銘柄（確認中）",
                "SUPERVISION_REVIEW":
                    "監理銘柄（審査中）",
            }

            reason = display_reason_map.get(
                reason,
                reason,
            )

            if (
                reason
                and reason not in reasons
            ):
                reasons.append(reason)

        display = f"JPX {action}"

        if reasons:
            display += " / " + "・".join(reasons)

        result[code] = display

    return result


def filter_blocked_stocks(
    df,
    code_column="Code",
    verbose=True,
):
    """
    Remove JPX BLOCK stocks from a DataFrame.

    WARN stocks remain tradable.
    The original DataFrame is not modified.
    """

    if df is None:
        return df

    if df.empty:
        return df.copy()

    if code_column not in df.columns:
        raise KeyError(
            f"Code column not found: "
            f"{code_column}"
        )

    blocked_codes = load_blocked_codes()

    if not blocked_codes:
        if verbose:
            print(
                "JPX RISK FILTER : "
                "no BLOCK codes loaded"
            )

        return df.copy()

    work = df.copy()

    normalized_codes = (
        work[code_column]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\\.0$",
            "",
            regex=True,
        )
    )

    blocked_mask = (
        normalized_codes.isin(
            blocked_codes
        )
    )

    removed = work[
        blocked_mask
    ].copy()

    filtered = work[
        ~blocked_mask
    ].copy()

    filtered = filtered.reset_index(
        drop=True
    )

    if verbose:
        print()
        print("=" * 60)
        print(" JPX RISK FILTER")
        print("=" * 60)

        print(
            "Input  :",
            len(work),
        )

        print(
            "Blocked:",
            len(removed),
        )

        print(
            "Output :",
            len(filtered),
        )

        if not removed.empty:
            print()
            print("Excluded codes:")

            for code in (
                normalized_codes[
                    blocked_mask
                ].tolist()
            ):
                print(
                    f"  {code}"
                )

        print("=" * 60)

    return filtered


if __name__ == "__main__":

    df = build_jpx_risk_list()

    print("=" * 60)
    print(" JPX RISK FILTER")
    print("=" * 60)

    print(
        "Total rows :",
        len(df),
    )

    print(
        "BLOCK      :",
        int(
            (df["Action"] == "BLOCK").sum()
        ),
    )

    print(
        "WARN       :",
        int(
            (df["Action"] == "WARN").sum()
        ),
    )

    print()

    print(
        df[
            [
                "Code",
                "Name",
                "RiskType",
                "Action",
                "Reason",
            ]
        ].to_string(index=False)
    )

    print()
    print(
        "Saved :",
        OUTPUT_PATH,
    )
