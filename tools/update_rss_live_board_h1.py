# ================================================
# H1 09:30 TOP3 -> 楽天RSSライブボード
# ================================================

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "src" / "intraday"),
)

from rss_live_board import (
    set_candidates,
    print_board,
)


TRACKING_FILE = (
    ROOT
    / "data"
    / "tracking"
    / "intraday_strategy_h1.csv"
)


def normalize_code(value):
    if value is None:
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def main():

    print("=" * 60)
    print(" H1 TOP3 -> 楽天RSS LIVE BOARD")
    print("=" * 60)

    if not TRACKING_FILE.exists():
        raise RuntimeError(
            f"H1 tracking CSV がありません : "
            f"{TRACKING_FILE}"
        )

    df = pd.read_csv(
        TRACKING_FILE,
        dtype={"Code": str},
        low_memory=False,
    )

    required = [
        "StrategyVersion",
        "DetectionDate",
        "SnapshotTime",
        "Code",
        "Rank",
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "H1 tracking columns missing : "
            + ", ".join(missing)
        )

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    work = df[
        (df["StrategyVersion"] == "H1")
        & (
            df["DetectionDate"]
            .astype(str)
            == today
        )
    ].copy()

    # 09:30～09:35だけを対象
    snapshot_minutes = (
        pd.to_datetime(
            work["SnapshotTime"],
            format="%H:%M:%S",
            errors="coerce",
        ).dt.hour * 60
        +
        pd.to_datetime(
            work["SnapshotTime"],
            format="%H:%M:%S",
            errors="coerce",
        ).dt.minute
    )

    work = work[
        snapshot_minutes.between(
            9 * 60 + 30,
            9 * 60 + 35,
        )
    ].copy()

    if work.empty:
        raise RuntimeError(
            "本日の09:30～09:35 "
            "H1 TOP3がありません。"
        )

    # 同日に複数スナップショットがあれば
    # 最も早い09:30台を使用
    work["_time"] = pd.to_datetime(
        work["SnapshotTime"],
        format="%H:%M:%S",
        errors="coerce",
    )

    target_time = work[
        "_time"
    ].min()

    work = work[
        work["_time"] == target_time
    ].copy()

    work["RankX"] = pd.to_numeric(
        work["Rank"],
        errors="coerce",
    )

    work = (
        work
        .dropna(
            subset=[
                "RankX",
                "Code",
            ]
        )
        .sort_values("RankX")
        .head(3)
    )

    if work.empty:
        raise RuntimeError(
            "H1 TOP3候補を取得できません。"
        )

    candidates = []

    for _, row in work.iterrows():

        code = normalize_code(
            row["Code"]
        )

        rank = int(
            row["RankX"]
        )

        candidates.append(
            (
                code,
                f"H1 #{rank}",
            )
        )

    print(
        "Snapshot :",
        target_time.strftime(
            "%H:%M:%S"
        ),
    )

    for code, label in candidates:
        print(
            f"{label} : {code}"
        )

    # 09:30時点で09:20の20銘柄をクリアし、
    # H1 TOP3だけをセットする。
    set_candidates(
        candidates
    )

    print_board()

    print()
    print(
        "H1 TOP3 live board update : OK"
    )


if __name__ == "__main__":
    main()
