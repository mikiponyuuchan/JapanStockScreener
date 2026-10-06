from pathlib import Path

path = Path("src/services/result_writer.py")
backup = Path(
    "src/services/result_writer_before_jpx_risk_display.py"
)

text = path.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(text, encoding="utf-8")

# ==========================================================
# 1. import
# ==========================================================

old = """from services.yahoo_credit_service import (
    load_latest_credit_data,
    download_credit_batch,
)
"""

new = """from services.yahoo_credit_service import (
    load_latest_credit_data,
    download_credit_batch,
)

from services.jpx_risk_filter import (
    load_risk_display_map,
)
"""

if "load_risk_display_map" not in text:
    if old not in text:
        raise RuntimeError("Import position not found.")

    text = text.replace(old, new, 1)

# ==========================================================
# 2. TOP20 columns
# ==========================================================

old = '''        "初動スコア",
        "信用倍率",
'''

new = '''        "初動スコア",
        "JPX判定",
        "信用倍率",
'''

if '"JPX判定",' not in text:
    if old not in text:
        raise RuntimeError(
            "TOP20 columns position not found."
        )

    text = text.replace(old, new, 1)

# ==========================================================
# 3. JPX display map
# ==========================================================

old = """    credit_map = {}

    # Yahoo credit disabled in main screener.
"""

new = """    credit_map = {}

    # JPX risk information is display-only.
    # TOP20 ranking is not changed.
    risk_display_map = load_risk_display_map()

    # Yahoo credit disabled in main screener.
"""

if "risk_display_map = load_risk_display_map()" not in text:
    if old not in text:
        raise RuntimeError(
            "JPX map position not found."
        )

    text = text.replace(old, new, 1)

# ==========================================================
# 4. 各銘柄のJPX表示値
# ==========================================================

old = """            # 高騰理由
"""

new = """            # JPX判定

            jpx_risk = risk_display_map.get(
                code,
                "",
            )

            # 高騰理由
"""

if "jpx_risk = risk_display_map.get(" not in text:
    if old not in text:
        raise RuntimeError(
            "JPX value position not found."
        )

    text = text.replace(old, new, 1)

# ==========================================================
# 5. TOP20出力行
# 実際の複数行 get_value() 形式を基準にする
# ==========================================================

old = '''                    "信用倍率": credit_ratio,

                    "売り残増加": sell_increase,
'''

new = '''                    "JPX判定": jpx_risk,

                    "信用倍率": credit_ratio,

                    "売り残増加": sell_increase,
'''

if '"JPX判定": jpx_risk,' not in text:
    if old not in text:
        raise RuntimeError(
            "TOP20 row position not found."
        )

    text = text.replace(old, new, 1)

path.write_text(
    text,
    encoding="utf-8",
)

print("Patched:", path)
print("Backup :", backup)
