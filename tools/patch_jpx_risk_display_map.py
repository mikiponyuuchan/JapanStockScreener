from pathlib import Path

path = Path("src/services/jpx_risk_filter.py")
backup = Path("src/services/jpx_risk_filter_before_display_map.py")

text = path.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(text, encoding="utf-8")

marker = """

def filter_blocked_stocks(
"""

new_code = r'''

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
'''

if "def load_risk_display_map():" in text:
    print("Already patched.")
else:
    if marker not in text:
        raise RuntimeError(
            "Patch position not found."
        )

    text = text.replace(
        marker,
        new_code + marker,
        1,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print("Patched:", path)
    print("Backup :", backup)
