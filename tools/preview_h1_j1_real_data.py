from pathlib import Path
import argparse
import ast
import pandas as pd
import sys

sys.path.insert(0, str(Path.cwd() / "src"))

ROOT = Path.cwd()
PREVIEW = ROOT / "src/intraday/rss_live_board_h1_preview.py"
TRADING = ROOT / "data/trading"


def load_preview_functions():
    source = PREVIEW.read_text(encoding="utf-8")
    tree = ast.parse(source)

    names = {
        "normalize_code",
        "preview_select_j1_top5",
        "preview_h1_j1_layout",
        "preview_h1_j1_top5_layout",
    }

    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in names
    ]

    ns = {}
    exec(
        compile(
            ast.Module(body=nodes, type_ignores=[]),
            str(PREVIEW),
            "exec",
        ),
        ns,
    )
    return ns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-date", required=True)
    args = parser.parse_args()

    ns = load_preview_functions()
    normalize = ns["normalize_code"]

    csv_path = TRADING / (
        args.plan_date + "_j1_trade_plan.csv"
    )

    if not csv_path.exists():
        raise SystemExit(
            "J1 PLAN NOT FOUND: " + str(csv_path)
        )

    df = pd.read_csv(
        csv_path,
        dtype={"Code": str},
    )

    if "Code" not in df.columns:
        raise SystemExit("J1 PLAN HAS NO Code COLUMN")

    if "DetectionDate" in df.columns:
        dates = pd.to_datetime(
            df["DetectionDate"],
            errors="coerce",
        )
        target = pd.Timestamp(args.plan_date).date()
        df = df.loc[
            dates.dt.date.eq(target)
        ].copy()

    codes = [
        normalize(code)
        for code in df["Code"].tolist()
    ]
    codes = [code for code in codes if code]

    j1_top5 = ns["preview_select_j1_top5"](codes)

    import win32com.client

    excel = win32com.client.GetActiveObject(
        "Excel.Application"
    )

    workbook_path = (
        ROOT / "data/intraday/rakuten_rss_morning.xlsx"
    ).resolve()

    workbook = None
    for wb in excel.Workbooks:
        if Path(wb.FullName).resolve() == workbook_path:
            workbook = wb
            break

    if workbook is None:
        raise SystemExit(
            "TARGET WORKBOOK NOT OPEN"
        )

    sheet_name = (
        "H1\u30e9\u30a4\u30d6\u30dc\u30fc\u30c9"
    )

    sheet = workbook.Worksheets(sheet_name)

    current_rows = {}

    for row in range(2, 22):
        code = normalize(
            sheet.Cells(row, 1).Value
        )
        label = str(
            sheet.Cells(row, 8).Value or ""
        ).strip()

        current_rows[row] = (code, label)

    h1_codes = [
        current_rows[row][0]
        for row in range(2, 12)
        if current_rows[row][0]
    ]

    print("J1 PLAN:", csv_path.name)
    print("J1 TOP5:", j1_top5)
    print("H1 CODES:", h1_codes)
    print()

    if len(h1_codes) != 10:
        raise SystemExit(
            "STOP: Excel rows 2-11 do not contain 10 H1 codes"
        )

    layout = ns["preview_h1_j1_top5_layout"](
        h1_codes=h1_codes,
        j1_codes=j1_top5,
    )

    # Collect SSR labels by stock code, not by row.
    ssr_by_code = {}

    for old_code, old_label in current_rows.values():
        if not old_code:
            continue

        ssr_parts = [
            part.strip()
            for part in old_label.split("/")
            if part.strip().startswith("SSR-Ver")
        ]

        if ssr_parts:
            bucket = ssr_by_code.setdefault(
                old_code, []
            )
            for part in ssr_parts:
                if part not in bucket:
                    bucket.append(part)

    # Preserve current H1 decisions and SSR labels
    # when the code remains in the same row.
    for row in range(2, 22):
        before_code, before_label = current_rows[row]
        after_code, after_label = layout.get(row, ("", ""))

        if not before_code or before_code != after_code:
            continue

        existing_parts = [
            part.strip()
            for part in before_label.split("/")
            if part.strip()
        ]

        new_parts = [
            part.strip()
            for part in after_label.split("/")
            if part.strip()
        ]

        for part in existing_parts:
            if part.startswith("H1 #") or part.startswith("SSR-Ver"):
                if part not in new_parts:
                    new_parts.append(part)

        if after_code:
            layout[row] = (
                after_code,
                " / ".join(new_parts),
            )

    # Attach SSR labels to the destination stock code.
    for row, (code, label) in list(layout.items()):
        if not code:
            continue

        parts = [
            part.strip()
            for part in label.split("/")
            if part.strip()
        ]

        for ssr in ssr_by_code.get(code, []):
            if ssr not in parts:
                parts.append(ssr)

        layout[row] = (code, " / ".join(parts))

    # Final safety check using the transaction module.
    # This call is strictly read-only.
    from intraday.rss_board_transaction import (
        execute_board_transaction,
    )

    print("INTEGRATED BOARD DRY RUN")
    changes = execute_board_transaction(
        sheet=sheet,
        layout=layout,
        dry_run=True,
    )

    print("INTEGRATED CHANGED CELLS:", len(changes))
    print()

    changed = 0

    print("H1/J1 LAYOUT DIFF - READ ONLY")

    for row in range(2, 22):
        before = current_rows[row]
        after = layout.get(row, ("", ""))

        if before != after:
            changed += 1
            print(
                f"ROW {row:2d} "
                f"BEFORE {before!r} "
                f"AFTER {after!r}"
            )

    print()
    print("CHANGED ROWS:", changed)
    print("READ ONLY J1 INTEGRATION DIFF OK")
    print("No cells changed. No workbook saved.")


if __name__ == "__main__":
    main()
