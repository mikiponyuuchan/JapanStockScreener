from pathlib import Path
import sys
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))

from indicators.technical import add_indicators


CACHE_DIR = ROOT_DIR / "data" / "cache"
TRACKING_FILE = (
    ROOT_DIR
    / "data"
    / "tracking"
    / "initial_move_tracking.csv"
)

TARGET_DATES = {
    "2026-08-18",
    "2026-08-19",
}


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

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
        utc=True,
    )

    df = df.dropna(subset=["Date"]).copy()

    if df.empty:
        return None

    df["Date"] = (
        df["Date"]
        .dt.tz_convert("Asia/Tokyo")
        .dt.tz_localize(None)
    )

    return (
        df
        .sort_values("Date")
        .reset_index(drop=True)
    )


def get_latest_on_date(code, target_date):
    df = load_cache(code)

    if df is None:
        return None

    target = pd.Timestamp(target_date).normalize()

    df = df[
        df["Date"].dt.normalize() <= target
    ].copy()

    if len(df) < 30:
        return None

    try:
        df = add_indicators(df)
    except Exception as e:
        print(
            f"indicator ERROR {code} "
            f"{target_date} : {e}"
        )
        return None

    if df.empty:
        return None

    latest = df.iloc[-1]

    actual_date = pd.Timestamp(
        latest["Date"]
    ).normalize()

    if actual_date != target:
        return None

    return latest


def to_bool(value):
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() == "true"


def main():

    tracking = pd.read_csv(
        TRACKING_FILE,
        encoding="utf-8-sig",
        dtype={
            "コード": str,
        },
    )

    targets = tracking[
        tracking["検出日"].isin(TARGET_DATES)
    ].copy()

    targets["初動スコア"] = pd.to_numeric(
        targets["初動スコア"],
        errors="coerce",
    )

    targets = targets[
        targets["初動スコア"] == 3
    ].copy()

    results = []

    for _, row in targets.iterrows():

        code = str(row["コード"]).strip()
        target_date = row["検出日"]

        latest = get_latest_on_date(
            code,
            target_date,
        )

        if latest is None:
            print(
                f"SKIP {target_date} {code}"
            )
            continue

        change = pd.to_numeric(
            latest.get("ChangePercent"),
            errors="coerce",
        )

        volume_ratio = pd.to_numeric(
            latest.get("VolumeRatio"),
            errors="coerce",
        )

        breakout = to_bool(
            latest.get("BreakoutSignal")
        )

        new30 = to_bool(
            latest.get("New30High")
        )

        score_calc = 0

        if not pd.isna(change):
            if change >= 5:
                score_calc += 3

        if not pd.isna(volume_ratio):
            if volume_ratio >= 3:
                score_calc += 2

        if breakout:
            score_calc += 1

        if new30:
            score_calc += 1

        returns = []

        for day in range(1, 6):

            value = pd.to_numeric(
                row.get(
                    f"{day}日後騰落率"
                ),
                errors="coerce",
            )

            if not pd.isna(value):
                returns.append(
                    float(value)
                )

        max5 = (
            max(returns)
            if returns
            else None
        )

        results.append(
            {
                "検出日": target_date,
                "コード": code,
                "銘柄名": row["銘柄名"],
                "記録スコア": int(
                    row["初動スコア"]
                ),
                "再計算スコア": score_calc,
                "ChangePercent": (
                    round(float(change), 2)
                    if not pd.isna(change)
                    else None
                ),
                "VolumeRatio": (
                    round(float(volume_ratio), 2)
                    if not pd.isna(volume_ratio)
                    else None
                ),
                "BreakoutSignal": breakout,
                "New30High": new30,
                "Max5": (
                    round(max5, 2)
                    if max5 is not None
                    else None
                ),
            }
        )

    result_df = pd.DataFrame(results)

    print()
    print(
        "=== 3点群 条件内訳 ==="
    )
    print()

    print(
        result_df.to_string(
            index=False
        )
    )

    print()
    print(
        "=== 条件組み合わせ別集計 ==="
    )
    print()

    if result_df.empty:
        return

    result_df["Pattern"] = (
        result_df.apply(
            lambda r:
            (
                f"C{int(r['ChangePercent'] >= 5)}"
                f"_V{int(r['VolumeRatio'] >= 3)}"
                f"_B{int(r['BreakoutSignal'])}"
                f"_H{int(r['New30High'])}"
            ),
            axis=1,
        )
    )

    summary = (
        result_df
        .groupby(
            "Pattern",
            dropna=False,
        )
        .agg(
            Count=(
                "コード",
                "count",
            ),
            AvgMax5=(
                "Max5",
                "mean",
            ),
            Hit5=(
                "Max5",
                lambda s:
                (
                    pd.to_numeric(
                        s,
                        errors="coerce",
                    )
                    .ge(5)
                    .mean()
                    * 100
                ),
            ),
            Hit10=(
                "Max5",
                lambda s:
                (
                    pd.to_numeric(
                        s,
                        errors="coerce",
                    )
                    .ge(10)
                    .mean()
                    * 100
                ),
            ),
        )
        .reset_index()
    )

    summary["AvgMax5"] = (
        summary["AvgMax5"]
        .round(2)
    )

    summary["Hit5"] = (
        summary["Hit5"]
        .round(1)
    )

    summary["Hit10"] = (
        summary["Hit10"]
        .round(1)
    )

    print(
        summary
        .sort_values(
            [
                "AvgMax5",
                "Count",
            ],
            ascending=[
                False,
                False,
            ],
        )
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()