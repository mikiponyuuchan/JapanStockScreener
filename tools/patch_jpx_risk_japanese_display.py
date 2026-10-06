from pathlib import Path

path = Path("src/services/jpx_risk_filter.py")
backup = Path(
    "src/services/jpx_risk_filter_before_japanese_display.py"
)

text = path.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(
        text,
        encoding="utf-8",
    )

old = '''            reason = str(value).strip()

            if (
                reason
                and reason not in reasons
            ):
                reasons.append(reason)
'''

new = '''            reason = str(value).strip()

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
'''

if old not in text:
    raise RuntimeError(
        "Display reason block not found."
    )

text = text.replace(
    old,
    new,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print("Patched:", path)
print("Backup :", backup)
