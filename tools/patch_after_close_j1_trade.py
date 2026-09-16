from pathlib import Path

path = Path("tools/update_tracking_after_close.py")

text = path.read_text(
    encoding="utf-8"
)

marker1 = '''    # ======================================================
    # J1 detection
    # ======================================================
'''

insert1 = '''    # ======================================================
    # J1 Trade Ver1 result update
    # ======================================================

    print()
    print("[J1 Trade Ver1 result update]")

    try:

        subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools"
                    / "update_j1_trade_ver1.py"
                ),
            ],
            cwd=ROOT,
            check=True,
        )

        print(
            "J1 Trade Ver1 result update : complete"
        )

    except Exception as e:

        print(
            "J1 Trade Ver1 result update ERROR :",
            e,
        )

'''

if marker1 not in text:
    raise SystemExit(
        "ERROR: J1 detection marker not found"
    )

text = text.replace(
    marker1,
    insert1 + marker1,
    1,
)

marker2 = '''    # ======================================================
    # Intraday Strategy H1 result update
    # ======================================================
'''

insert2 = '''    # ======================================================
    # J1 Trade Ver1 plan creation
    # ======================================================

    print()
    print("[J1 Trade Ver1 plan]")

    if j1_detect_ok:

        try:

            subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "tools"
                        / "create_j1_trade_plan.py"
                    ),
                ],
                cwd=ROOT,
                check=True,
            )

            print(
                "J1 Trade Ver1 plan : complete"
            )

        except Exception as e:

            print(
                "J1 Trade Ver1 plan ERROR :",
                e,
            )

    else:

        print(
            "J1 Trade Ver1 plan : skipped "
            "(J1 detection failed)"
        )

'''

if marker2 not in text:
    raise SystemExit(
        "ERROR: H1 marker not found"
    )

text = text.replace(
    marker2,
    insert2 + marker2,
    1,
)

backup = path.with_name(
    "update_tracking_after_close_before_j1_trade.py"
)

backup.write_text(
    path.read_text(encoding="utf-8"),
    encoding="utf-8",
)

path.write_text(
    text,
    encoding="utf-8",
)

print("PATCHED :", path)
print("BACKUP  :", backup)
