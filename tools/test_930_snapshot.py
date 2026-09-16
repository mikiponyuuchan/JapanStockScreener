import pandas as pd
import yfinance as yf

CODE = "7203"
TARGET_DATE = pd.Timestamp("2026-08-28").date()

ticker = f"{CODE}.T"

# ==========================
# 日足
# ==========================
daily = yf.download(
    ticker,
    period="3mo",
    interval="1d",
    auto_adjust=False,
    progress=False,
)

if isinstance(daily.columns, pd.MultiIndex):
    daily.columns = daily.columns.get_level_values(0)

daily.index = pd.to_datetime(daily.index)

# 対象日の前日まで
past = daily[daily.index.date < TARGET_DATE].copy()

if len(past) < 30:
    raise RuntimeError("30営業日分の日足がありません")

prev20_high = float(past["High"].tail(20).max())
prev30_high = float(past["High"].tail(30).max())

# 当日終値
today_daily = daily[daily.index.date == TARGET_DATE]

if today_daily.empty:
    raise RuntimeError("対象日の日足がありません")

day_close = float(today_daily.iloc[-1]["Close"])

# ==========================
# 1分足
# ==========================
minute = yf.download(
    ticker,
    period="7d",
    interval="1m",
    auto_adjust=False,
    progress=False,
)

if isinstance(minute.columns, pd.MultiIndex):
    minute.columns = minute.columns.get_level_values(0)

idx = pd.to_datetime(minute.index)

if idx.tz is None:
    idx = idx.tz_localize("UTC").tz_convert("Asia/Tokyo")
else:
    idx = idx.tz_convert("Asia/Tokyo")

minute.index = idx

today = minute[minute.index.date == TARGET_DATE].copy()

if today.empty:
    raise RuntimeError("対象日の1分足がありません")

# ==========================
# 9:30時点
# 9:00～9:29だけを使用
# ==========================
morning = today[
    (today.index.time >= pd.Timestamp("09:00").time())
    & (today.index.time < pd.Timestamp("09:30").time())
]

if morning.empty:
    raise RuntimeError("9:00～9:29のデータがありません")

open_900 = float(morning.iloc[0]["Open"])
high_930 = float(morning["High"].max())
low_930 = float(morning["Low"].min())
close_929 = float(morning.iloc[-1]["Close"])
volume_930 = int(morning["Volume"].sum())

# 9:30で買ったと仮定
entry_bar = today[today.index.time >= pd.Timestamp("09:30").time()].iloc[0]
entry_time = entry_bar.name
entry_930 = float(entry_bar["Open"])

# ==========================
# 指標
# ==========================
gap_pct = (prev30_high / prev20_high - 1) * 100
morning_candle_pct = (close_929 / open_900 - 1) * 100
entry_vs_20 = (entry_930 / prev20_high - 1) * 100
entry_vs_30 = (entry_930 / prev30_high - 1) * 100
close_return = (day_close / entry_930 - 1) * 100

print()
print("==============================")
print(" 9:30スナップショット確認")
print("==============================")
print(f"コード               : {CODE}")
print(f"対象日               : {TARGET_DATE}")
print()
print(f"紫 20日高値          : {prev20_high:.2f}")
print(f"緑 30日高値          : {prev30_high:.2f}")
print(f"ライン乖離率         : {gap_pct:+.2f}%")
print()
print(f"9:00始値             : {open_900:.2f}")
print(f"9:00-9:29高値        : {high_930:.2f}")
print(f"9:00-9:29安値        : {low_930:.2f}")
print(f"9:29終値             : {close_929:.2f}")
print(f"9:30まで出来高       : {volume_930:,}")
print(f"9:30時点ローソク率   : {morning_candle_pct:+.2f}%")
print()
print(f"仮想買付時刻         : {entry_time}")
print(f"9:30仮想買値         : {entry_930:.2f}")
print(f"紫20日線から         : {entry_vs_20:+.2f}%")
print(f"緑30日線から         : {entry_vs_30:+.2f}%")
print()
print(f"当日終値             : {day_close:.2f}")
print(f"9:30→引け           : {close_return:+.2f}%")
print()

print("==============================")
print(" 仮説分類")
print("==============================")

if close_929 < open_900:
    print("① 陰線              : YES")
else:
    print("① 陰線              : NO")

if open_900 < prev20_high and high_930 >= prev30_high:
    print("② 紫→緑一気またぎ   : YES")
else:
    print("② 紫→緑一気またぎ   : NO")

if entry_930 < prev20_high:
    print("③ 9:30でも紫の下    : YES")
else:
    print("③ 9:30でも紫の下    : NO")

main_shape = (
    prev30_high > prev20_high
    and close_929 > open_900
    and entry_930 >= prev20_high
    and high_930 < prev30_high
)

print(
    "④ 本命形            : "
    + ("YES" if main_shape else "NO")
)
