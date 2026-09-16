from pathlib import Path

targets = [
    Path("tools/update_intraday_strategy_h1.py"),
    Path("tools/update_intraday_strategy_h1_early20.py"),
]

needle = '''    for idx, row in df.iterrows():
        date_text = str(
            row["DetectionDate"]
        ).strip()
'''

replacement = '''    for idx, row in df.iterrows():

        exit_type = str(
            row.get(
                "ExitType",
                "",
            )
        ).strip()

        if (
            exit_type
            and exit_type.lower()
            != "nan"
        ):
            skipped += 1
            continue

        date_text = str(
            row["DetectionDate"]
        ).strip()
'''

for path in targets:

    text = path.read_text(
        encoding="utf-8"
    )

    if needle not in text:
        raise SystemExit(
            f"ERROR: marker not found: {path}"
        )

    backup = path.with_name(
        path.stem
        + "_before_skip_completed.py"
    )

    backup.write_text(
        text,
        encoding="utf-8",
    )

    text = text.replace(
        needle,
        replacement,
        1,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print("PATCHED :", path)
    print("BACKUP  :", backup)
