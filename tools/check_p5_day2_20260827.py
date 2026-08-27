import sys
from pathlib import Path

import pandas as pd

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "src"))

from services.yahoo_service import _download_history_batch


PANEL_FILE = Path("data/tracking/buy_decision_backtest_panel.csv")
DETECTION_DATE = pd.Timestamp("2026-08-25")
DAY2_DATE = pd.Timestamp("2026-08-27")


# ============================================================
# パネル読込
# ============================================================

df = pd.read_csv(
    PANEL_FILE,
    encoding="utf-8-sig",
    low_memory=False,
)

df["検出日"] = pd.to_datetime(
    df["検出日"],
    errors="coerce",
).dt.normalize()


def num(column):
    return pd.to_numeric(
        df[column],
        errors="coerce",
    )


score = num("初動スコア")
change5 = num("5日騰落率")
vr20 = num("VolumeRatio20")
day1 = num("Day1")


# ============================================================
# 正式P5
# ============================================================

avoid = pd.Series(
    False,
    index=df.index,
)

for column in [
    "A_STALL",
    "C_SPIKE",
    "D_OVERHEAT",
    "F_DECEL",
]:
    if column in df.columns:
        avoid |= (
            df[column]
            .fillna(False)
            .astype(bool)
        )


p5 = (
    (score >= 3)
    & (score <= 4)
    & (change5 > 0)
    & (vr20 > 1)
    & (~avoid)
)


target = df[
    (df["検出日"] == DETECTION_DATE)
    & p5
    & day1.notna()
].copy()


target["コード"] = (
    target["コード"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
)

target["Day1"] = day1[target.index]


print()
print("=" * 70)
print(" 8/25 P5 -> 8/27 Day2 LIVE CHECK")
print("=" * 70)
print()
print("正式P5・Day1あり :", len(target), "件")


# ============================================================
# Yahoo取得
# ============================================================

codes = sorted(
    target["コード"]
    .dropna()
    .unique()
    .tolist()
)

print()
print("Yahooから最新OHLCを取得します...")

history_map = _download_history_batch(
    codes,
    period="10d",
    batch_size=100,
)

print()
print(
    "Yahoo取得成功 :",
    len(history_map),
    "/",
    len(codes),
)


# ============================================================
# 8/27終値からDay2計算
#
# Day1/Day2 は検出日の終値基準の累積騰落率
# ============================================================

records = []

for _, row in target.iterrows():

    code = row["コード"]

    history = history_map.get(code)

    if history is None or history.empty:
        continue

    h = history.copy()

    h["Date"] = pd.to_datetime(
        h["Date"],
        errors="coerce",
    ).dt.normalize()

    h = (
        h
        .dropna(subset=["Date", "Close"])
        .sort_values("Date")
        .drop_duplicates(
            subset=["Date"],
            keep="last",
        )
    )

    detection = h[
        h["Date"] == DETECTION_DATE
    ]

    day1_date = DETECTION_DATE + pd.Timedelta(days=1)

    day1_row = h[
        h["Date"] == day1_date
    ]

    day2_row = h[
        h["Date"] == DAY2_DATE
    ]

    if detection.empty or day2_row.empty:
        continue

    detection_close = float(
        detection.iloc[-1]["Close"]
    )

    day2_close = float(
        day2_row.iloc[-1]["Close"]
    )

    if day1_row.empty:
        continue

    day1_close = float(
        day1_row.iloc[-1]["Close"]
    )

    day1_volume = pd.to_numeric(
        day1_row.iloc[-1].get("Volume"),
        errors="coerce",
    )

    day2_volume = pd.to_numeric(
        day2_row.iloc[-1].get("Volume"),
        errors="coerce",
    )

    if (
        pd.notna(day1_volume)
        and day1_volume > 0
        and pd.notna(day2_volume)
    ):
        volume_change = (
            day2_volume / day1_volume
        )
    else:
        volume_change = float("nan")

    if detection_close == 0:
        continue

    day2_value = (
        day2_close
        / detection_close
        - 1
    ) * 100

    d1 = float(row["Day1"])

    drop = day2_value - d1

    change5_value = pd.to_numeric(
        row["5日騰落率"],
        errors="coerce",
    )

    vr_value = pd.to_numeric(
        row["VolumeRatio20"],
        errors="coerce",
    )

    normal = drop >= -3.5

    rescue = (
        drop >= -5.0
        and drop < -3.5
        and change5_value < 20.0
        and vr_value < 3.0
    )

    passed = normal or rescue

    if normal:
        decision = "通常通過"
    elif rescue:
        decision = "救済通過"
    elif drop < -5.0:
        decision = "見送り Drop<-5"
    elif change5_value >= 20.0:
        decision = "見送り 5日騰落率>=20"
    elif vr_value >= 3.0:
        decision = "見送り VR>=3"
    else:
        decision = "見送り"

    records.append(
        {
            "コード": code,
            "銘柄名": row["銘柄名"],
            "初動スコア": row["初動スコア"],
            "5日騰落率": change5_value,
            "VolumeRatio20": vr_value,
            "Day1": d1,
            "Day2": day2_value,
            "Drop": drop,
            "8/25終値": detection_close,
            "8/26終値": day1_close,
            "8/27終値": day2_close,
            "8/26出来高": day1_volume,
            "8/27出来高": day2_volume,
            "出来高比D2/D1": volume_change,
            "判定": decision,
            "_passed": passed,
        }
    )


result = pd.DataFrame(records)


# ============================================================
# 結果
# ============================================================

print()
print("=" * 70)
print(" DAY2 MATCH RESULT")
print("=" * 70)
print()

print(
    "Day2計算可能 :",
    len(result),
    "/",
    len(target),
)

if result.empty:
    print("8/27データを取得できませんでした。")
    raise SystemExit


buy = result[
    result["_passed"]
].copy()

reject = result[
    ~result["_passed"]
].copy()


print()
print("=" * 70)
print(" 8/27 DAY2 買い候補")
print("=" * 70)
print()

print(
    "買い候補 :",
    len(buy),
    "件",
)

display_cols = [
    "コード",
    "銘柄名",
    "初動スコア",
    "5日騰落率",
    "VolumeRatio20",
    "8/25終値",
    "8/26終値",
    "8/27終値",
    "Day1",
    "Day2",
    "Drop",
    "8/26出来高",
    "8/27出来高",
    "出来高比D2/D1",
    "判定",
]

if not buy.empty:

    print()

    print(
        buy[
            display_cols
        ]
        .sort_values(
            "Drop",
            ascending=False,
        )
        .to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}",
        )
    )

else:
    print("該当なし")


print()
print("=" * 70)
print(" 見送り")
print("=" * 70)
print()

print(
    "見送り :",
    len(reject),
    "件",
)

if not reject.empty:

    print()

    print(
        reject[
            display_cols
        ]
        .sort_values(
            "Drop",
            ascending=False,
        )
        .to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}",
        )
    )

print()
print("=" * 70)
print(" DONE")
print("=" * 70)
