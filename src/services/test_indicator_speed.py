import pandas as pd
import time
import importlib.util

from indicators.technical import add_indicators as new_add_indicators


# ==========================
# 旧版読み込み
# ==========================

spec = importlib.util.spec_from_file_location(
    "old_technical",
    "src/indicators/technical_v6.12_backup.py"
)

mod = importlib.util.module_from_spec(spec)

spec.loader.exec_module(mod)

old_add_indicators = mod.add_indicators


# ==========================
# データ読み込み
# ==========================

df_all = pd.read_parquet(
    "data/cache/_all_cache.parquet"
)

codes = (
    df_all["code"]
    .astype(str)
    .drop_duplicates()
    .head(100)
    .tolist()
)

print("==============================")
print(" Ver6.12 指標計算速度比較")
print("==============================")
print(f"対象銘柄数: {len(codes)}")
print()


# ==========================
# 銘柄ごとに分割
# ==========================

dfs = []

for code in codes:

    df = df_all[
        df_all["code"].astype(str) == code
    ].copy()

    if not df.empty:
        dfs.append(df)


# ==========================
# 旧版
# ==========================

start = time.perf_counter()

for df in dfs:
    old_add_indicators(df.copy())

old_time = time.perf_counter() - start


# ==========================
# 新版
# ==========================

start = time.perf_counter()

for df in dfs:
    new_add_indicators(df.copy())

new_time = time.perf_counter() - start


# ==========================
# 結果
# ==========================

print("------------------------------")
print("旧版")
print("------------------------------")
print(f"合計 : {old_time:.4f} 秒")
print(f"1銘柄 : {old_time / len(dfs):.5f} 秒")
print()

print("------------------------------")
print("新版")
print("------------------------------")
print(f"合計 : {new_time:.4f} 秒")
print(f"1銘柄 : {new_time / len(dfs):.5f} 秒")
print()

print("------------------------------")

if new_time < old_time:

    rate = (
        1
        - new_time / old_time
    ) * 100

    print(f"高速化率 : {rate:.1f}%")

else:

    rate = (
        new_time / old_time
        - 1
    ) * 100

    print(f"低速化率 : {rate:.1f}%")

print("------------------------------")
