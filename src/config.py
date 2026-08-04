# =========================
# データ取得設定
# =========================

# データソース
DATA_PROVIDER = "yahoo"

# JPX上場銘柄一覧
JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"

# 保存先
DATA_DIR = "data"

# =========================
# スクリーニング条件
# =========================

VOLUME_RATIO = 2.0      # 出来高2倍以上
PRICE_UP = True         # 前日比プラス
MA_DAYS = 5             # 5日移動平均
CREDIT_RATIO = 1.0      # 信用倍率