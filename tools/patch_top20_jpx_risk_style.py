from pathlib import Path

path = Path("src/services/result_writer.py")
backup = Path(
    "src/services/result_writer_before_jpx_risk_style.py"
)

text = path.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(text, encoding="utf-8")

# ==========================================================
# 1. TOP20列幅を14列構成へ修正
# ==========================================================

old = '''        {
            "A": 6,     # code
            "B": 14,    # name
            "C": 8,     # close
            "D": 7,     # initial score
            "E": 6,     # P5　condition
            "F": 6,     # buy avoidance
            "G": 12,    # avoidance comment
            "H": 7,     # credit ratio
            "I": 7,     # short increase
            "J": 13,    # reason
            "K": 20,    # news
            "L": 11,    # news date
            "M": 30,    # chart
        }
'''

new = '''        {
            "A": 6,     # code
            "B": 14,    # name
            "C": 8,     # close
            "D": 7,     # initial score
            "E": 6,     # P5 condition
            "F": 6,     # buy avoidance
            "G": 12,    # avoidance comment
            "H": 24,    # JPX risk
            "I": 7,     # credit ratio
            "J": 7,     # short increase
            "K": 13,    # reason
            "L": 20,    # news
            "M": 11,    # news date
            "N": 30,    # chart
        }
'''

if old not in text:
    raise RuntimeError(
        "Column width block not found."
    )

text = text.replace(
    old,
    new,
    1,
)

# ==========================================================
# 2. JPX判定の色付け
# headers作成後・買い回避表示の前へ追加
# ==========================================================

marker = '''    # ======================================================
    # Buy avoidance display
'''

new_block = '''    # ======================================================
    # JPX risk display
    #
    # BLOCK = red fill + white bold font
    # WARN  = yellow fill + bold font
    # ======================================================

    if "JPX判定" in headers:

        jpx_col = headers[
            "JPX判定"
        ]

        jpx_block_fill = PatternFill(
            fill_type="solid",
            start_color="FFC00000",
            end_color="FFC00000",
        )

        jpx_warn_fill = PatternFill(
            fill_type="solid",
            start_color="FFFFC000",
            end_color="FFFFC000",
        )

        for row_number in range(
            2,
            sheet.max_row + 1
        ):

            cell = sheet.cell(
                row=row_number,
                column=jpx_col,
            )

            cell.alignment = Alignment(
                horizontal="left",
                vertical="center",
                wrap_text=True,
            )

            value = str(
                cell.value or ""
            ).strip()

            if value.startswith(
                "JPX BLOCK"
            ):

                cell.fill = jpx_block_fill

                cell.font = Font(
                    name=cell.font.name,
                    size=cell.font.sz or 11,
                    bold=True,
                    color="FFFFFFFF",
                )

            elif value.startswith(
                "JPX WARN"
            ):

                cell.fill = jpx_warn_fill

                cell.font = Font(
                    name=cell.font.name,
                    size=cell.font.sz or 11,
                    bold=True,
                    color="FF000000",
                )

    # ======================================================
    # Buy avoidance display
'''

if "# JPX risk display" not in text:
    if marker not in text:
        raise RuntimeError(
            "Style insertion position not found."
        )

    text = text.replace(
        marker,
        new_block,
        1,
    )

path.write_text(
    text,
    encoding="utf-8",
)

print("Patched:", path)
print("Backup :", backup)
