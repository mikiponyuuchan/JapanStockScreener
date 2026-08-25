import sys
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))

from indicators.technical import add_indicators
from screener.analyzer import calculate_initial_score

CACHE_DIR = ROOT_DIR / "data" / "cache"
OUTPUT_DIR = ROOT_DIR / "data" / "tracking"
START_DATE = "2026-07-27"
END_DATE = "2026-08-07"
TOP_N = 20
TRACKING_DAYS = 5


def load_cache(code):
    path = CACHE_DIR / f"{code}.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "Date" not in df.columns:
        return None
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    if df.empty:
        return None
    try:
        if getattr(df["Date"].dt, "tz", None) is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
    except Exception:
        try:
            df["Date"] = (pd.to_datetime(df["Date"], errors="coerce", utc=True)
                          .dt.tz_convert("Asia/Tokyo").dt.tz_localize(None))
        except Exception:
            return None
    return df.sort_values("Date").reset_index(drop=True)


def get_business_dates(df, start_date, end_date=None):
    dates = df["Date"].dt.normalize().drop_duplicates().sort_values().tolist()
    start = pd.Timestamp(start_date)
    if end_date is None:
        return [d for d in dates if d >= start]
    end = pd.Timestamp(end_date)
    return [d for d in dates if start <= d <= end]


def get_future_prices(history, target_date):
    dates = history["Date"].dt.normalize().drop_duplicates().sort_values().tolist()
    target = pd.Timestamp(target_date).normalize()
    future_dates = [d for d in dates if d > target]
    prices = []
    for day in range(1, TRACKING_DAYS + 1):
        if len(future_dates) < day:
            prices.append(None)
            continue
        d = future_dates[day - 1]
        rows = history[history["Date"].dt.normalize() == pd.Timestamp(d).normalize()]
        if rows.empty:
            prices.append(None)
            continue
        try:
            prices.append(float(rows.iloc[0]["Close"]))
        except Exception:
            prices.append(None)
    return prices


def calculate_score_on_date(code, target_date):
    df = load_cache(code)
    if df is None:
        return None
    target_date = pd.Timestamp(target_date).normalize()
    df = df[df["Date"].dt.normalize() <= target_date].copy()
    if len(df) < 80:
        return None
    try:
        df = add_indicators(df)
    except Exception as e:
        print(f"indicator ERROR {code} {target_date.date()} : {e}")
        return None
    if df.empty:
        return None
    latest = df.iloc[-1]
    try:
        score = calculate_initial_score(latest, credit_row=None)
    except Exception as e:
        print(f"score ERROR {code} {target_date.date()} : {e}")
        return None
    try:
        close = float(latest.get("Close"))
    except Exception:
        return None
    return {"検出日": target_date.strftime("%Y-%m-%d"), "コード": str(code),
            "検出時終値": round(close, 2), "初動スコア": int(score)}


def build_all_scores_for_date(target_date, cache_files):
    results = []
    for path in cache_files:
        result = calculate_score_on_date(path.stem, target_date)
        if result is not None:
            results.append(result)
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df["初動スコア"] = pd.to_numeric(df["初動スコア"], errors="coerce")
    df = df.dropna(subset=["初動スコア"]).copy()
    df["初動スコア"] = df["初動スコア"].astype(int)
    return df


def get_previous_business_date(target_date, cache_files):
    target = pd.Timestamp(target_date).normalize()
    previous_dates = []
    for path in cache_files:
        history = load_cache(path.stem)
        if history is None:
            continue
        dates = history["Date"].dt.normalize().drop_duplicates().sort_values()
        dates = dates[dates < target]
        if not dates.empty:
            previous_dates.append(dates.iloc[-1])
    return max(previous_dates) if previous_dates else None


def add_score_change(tracking_df, target_date, cache_files):
    if tracking_df.empty:
        return tracking_df
    previous_date = get_previous_business_date(target_date, cache_files)
    if previous_date is None:
        tracking_df["前営業日"] = ""
        tracking_df["前日初動スコア"] = ""
        tracking_df["スコア変化"] = ""
        return tracking_df
    print(f"\n前営業日スコア取得: {previous_date.strftime('%Y-%m-%d')}")
    previous = build_all_scores_for_date(previous_date, cache_files)
    tracking_df = tracking_df.copy()
    tracking_df["前営業日"] = previous_date.strftime("%Y-%m-%d")
    if previous.empty:
        tracking_df["前日初動スコア"] = ""
        tracking_df["スコア変化"] = ""
        return tracking_df
    score_map = dict(zip(previous["コード"].astype(str), previous["初動スコア"]))
    tracking_df["前日初動スコア"] = tracking_df["コード"].astype(str).map(score_map)
    tracking_df["スコア変化"] = (pd.to_numeric(tracking_df["初動スコア"], errors="coerce") -
                                  pd.to_numeric(tracking_df["前日初動スコア"], errors="coerce"))
    return tracking_df


def build_top20_for_date(target_date, cache_files):
    results = []
    for path in cache_files:
        result = calculate_score_on_date(path.stem, target_date)
        if result is not None:
            results.append(result)
    if not results:
        return None
    df = pd.DataFrame(results)
    df["初動スコア"] = pd.to_numeric(df["初動スコア"], errors="coerce")
    return (df.dropna(subset=["初動スコア"])
              .sort_values(["初動スコア", "コード"], ascending=[False, True])
              .head(TOP_N).reset_index(drop=True))


def build_tracking_for_top20(top20):
    rows = []
    for _, row in top20.iterrows():
        code = str(row["コード"])
        base_price = float(row["検出時終値"])
        history = load_cache(code)
        if history is None:
            continue
        prices = get_future_prices(history, pd.Timestamp(row["検出日"]))
        result = {"検出日": row["検出日"], "コード": code,
                  "検出時終値": base_price, "初動スコア": int(row["初動スコア"])}
        for day, price in enumerate(prices, 1):
            result[f"{day}日後株価"] = round(price, 2) if price is not None else ""
            result[f"{day}日後騰落率"] = round((price / base_price - 1) * 100, 2) if price is not None else ""
        rows.append(result)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def print_summary(tracking_df, title="追跡集計"):
    if tracking_df.empty:
        return
    print(f"\n=== {title} ===")
    for day in range(1, TRACKING_DAYS + 1):
        col = f"{day}日後騰落率"
        values = pd.to_numeric(tracking_df[col], errors="coerce").dropna()
        if values.empty:
            continue
        print(f"{day}日後: 平均 {values.mean():+.2f}% / 勝率 {values.gt(0).mean()*100:.1f}% / "
              f"最大 {values.max():+.2f}% / 最小 {values.min():+.2f}% / "
              f"+5%率 {values.ge(5).mean()*100:.1f}% / +10%率 {values.ge(10).mean()*100:.1f}% / n={len(values)}")


def print_score_summary(tracking_df):
    if tracking_df.empty:
        return
    print("\n=== 初動スコア別集計 ===")
    for score in sorted(tracking_df["初動スコア"].dropna().unique(), reverse=True):
        sdf = tracking_df[tracking_df["初動スコア"] == score]
        print(f"\n【初動スコア {int(score)}点】 対象 {len(sdf)}銘柄")
        for day in range(1, TRACKING_DAYS + 1):
            v = pd.to_numeric(sdf[f"{day}日後騰落率"], errors="coerce").dropna()
            if v.empty:
                continue
            print(f"  {day}日後: 平均 {v.mean():+.2f}% / 勝率 {v.gt(0).mean()*100:.1f}% / "
                  f"+5%率 {v.ge(5).mean()*100:.1f}% / +10%率 {v.ge(10).mean()*100:.1f}% / n={len(v)}")


def print_threshold_summary(tracking_df):
    if tracking_df.empty:
        return
    print("\n=== 初動スコア閾値別集計 ===")
    for threshold in [15, 12, 10, 8, 6]:
        sdf = tracking_df[tracking_df["初動スコア"] >= threshold]
        if sdf.empty:
            continue
        print(f"\n【{threshold}点以上】 対象 {len(sdf)}銘柄")
        for day in range(1, TRACKING_DAYS + 1):
            v = pd.to_numeric(sdf[f"{day}日後騰落率"], errors="coerce").dropna()
            if v.empty:
                continue
            print(f"  {day}日後: 平均 {v.mean():+.2f}% / 勝率 {v.gt(0).mean()*100:.1f}% / "
                  f"最大 {v.max():+.2f}% / +5%率 {v.ge(5).mean()*100:.1f}% / "
                  f"+10%率 {v.ge(10).mean()*100:.1f}% / n={len(v)}")


def print_score_change_summary(tracking_df):
    if tracking_df.empty or "スコア変化" not in tracking_df.columns:
        return
    df = tracking_df.copy()
    df["スコア変化"] = pd.to_numeric(df["スコア変化"], errors="coerce")
    df = df.dropna(subset=["スコア変化"]).copy()
    if df.empty:
        return
    def group(v):
        v = float(v)
        if v >= 3: return "+3以上"
        if v == 2: return "+2"
        if v == 1: return "+1"
        if v == 0: return "0"
        if v == -1: return "-1"
        return "-2以下"
    df["スコア変化区分"] = df["スコア変化"].apply(group)
    print("\n" + "=" * 60 + "\n=== スコア変化別集計 ===\n" + "=" * 60)
    for g in ["+3以上", "+2", "+1", "0", "-1", "-2以下"]:
        sdf = df[df["スコア変化区分"] == g]
        if sdf.empty:
            continue
        print(f"\n【スコア変化 {g}】 対象 {len(sdf)}銘柄")
        for day in range(1, TRACKING_DAYS + 1):
            v = pd.to_numeric(sdf[f"{day}日後騰落率"], errors="coerce").dropna()
            if v.empty:
                continue
            print(f"  {day}日後: 平均 {v.mean():+.2f}% / 勝率 {v.gt(0).mean()*100:.1f}% / "
                  f"+5%率 {v.ge(5).mean()*100:.1f}% / +10%率 {v.ge(10).mean()*100:.1f}% / n={len(v)}")
    print("\n=== スコア変化別・5営業日以内の最高騰落率 ===")
    for g in ["+3以上", "+2", "+1", "0", "-1", "-2以下"]:
        sdf = df[df["スコア変化区分"] == g]
        maxima = []
        for _, row in sdf.iterrows():
            vals = [pd.to_numeric(row.get(f"{d}日後騰落率"), errors="coerce") for d in range(1, TRACKING_DAYS + 1)]
            vals = [float(v) for v in vals if not pd.isna(v)]
            if vals: maxima.append(max(vals))
        if maxima:
            s = pd.Series(maxima)
            print(f"{g:>6} : 対象 {len(s)} / 5%以上 {s.ge(5).mean()*100:.1f}% / 10%以上 {s.ge(10).mean()*100:.1f}%")


def print_big_winners(tracking_df):
    if tracking_df.empty:
        return
    records = []
    for _, row in tracking_df.iterrows():
        vals = []
        for day in range(1, TRACKING_DAYS + 1):
            v = pd.to_numeric(row.get(f"{day}日後騰落率"), errors="coerce")
            if not pd.isna(v):
                vals.append((float(v), day))
        if vals:
            best = max(vals, key=lambda x: x[0])
            records.append({"検出日": row["検出日"], "コード": row["コード"],
                            "初動スコア": row["初動スコア"], "最大騰落率": best[0], "最大騰落日": best[1]})
    if records:
        print("\n=== 5営業日以内・最高騰落率 銘柄 ===")
        print(pd.DataFrame(records).sort_values("最大騰落率", ascending=False).head(20).to_string(index=False))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_files = list(CACHE_DIR.glob("*.csv"))
    print(f"対象キャッシュ: {len(cache_files)}")
    all_dates = set()
    for path in cache_files:
        history = load_cache(path.stem)
        if history is None:
            continue
        all_dates.update(pd.Timestamp(d).normalize() for d in get_business_dates(history, START_DATE, END_DATE))
    target_dates = sorted(all_dates)
    print(f"\n検証対象営業日 : {len(target_dates)}")
    print(" / ".join(d.strftime("%Y-%m-%d") for d in target_dates))
    all_tracking, all_top20 = [], []
    for index, target_date in enumerate(target_dates, 1):
        date_text = target_date.strftime("%Y-%m-%d")
        print("\n" + "=" * 60)
        print(f"[{index}/{len(target_dates)}] {date_text}")
        print("=" * 60)
        top20 = build_top20_for_date(target_date, cache_files)
        if top20 is None:
            print("TOP20作成: 対象なし")
            continue
        print("\n=== TOP20 ===")
        print(top20[["コード", "検出時終値", "初動スコア"]].to_string(index=True))
        top20_path = OUTPUT_DIR / f"historical_top20_{date_text.replace('-', '')}.csv"
        top20.to_csv(top20_path, index=False, encoding="utf-8-sig")
        print(f"TOP20保存: {top20_path}")
        tracking_df = build_tracking_for_top20(top20)
        if tracking_df.empty:
            continue
        tracking_df = add_score_change(tracking_df, target_date, cache_files)
        tracking_path = OUTPUT_DIR / f"historical_tracking_{date_text.replace('-', '')}.csv"
        tracking_df.to_csv(tracking_path, index=False, encoding="utf-8-sig")
        print(f"追跡保存: {tracking_path}")
        all_top20.append(top20)
        all_tracking.append(tracking_df)
        print_summary(tracking_df, title=f"{date_text} 追跡集計")
    if not all_tracking:
        print("\n追跡データがありません。")
        return
    combined_tracking = pd.concat(all_tracking, ignore_index=True)
    combined_top20 = pd.concat(all_top20, ignore_index=True)
    combined_top20_path = OUTPUT_DIR / "historical_top20_multi.csv"
    combined_tracking_path = OUTPUT_DIR / "historical_tracking_multi.csv"
    combined_top20.to_csv(combined_top20_path, index=False, encoding="utf-8-sig")
    combined_tracking.to_csv(combined_tracking_path, index=False, encoding="utf-8-sig")
    print("\n" + "=" * 60)
    print("=== 全期間検証完了 ===")
    print("=" * 60)
    print(f"検証営業日数 : {len(target_dates)}")
    print(f"TOP20延べ件数 : {len(combined_top20)}")
    print(f"追跡件数      : {len(combined_tracking)}")
    print(f"TOP20保存     : {combined_top20_path}")
    print(f"追跡保存      : {combined_tracking_path}")
    print_summary(combined_tracking, title="全期間追跡集計")
    print_score_summary(combined_tracking)
    print_threshold_summary(combined_tracking)
    print_big_winners(combined_tracking)
    print_score_change_summary(combined_tracking)


if __name__ == "__main__":
    main()
