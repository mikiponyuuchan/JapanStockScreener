# ================================================
# H1 09:30 TOP3 -> 楽天RSSライブボード
# ================================================

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "src" / "intraday"),
)

from rss_live_board import (
    add_candidate,
    clear_h1_labels,
    get_current_price,
    print_board,
)


TRACKING_FILE = (
    ROOT
    / "data"
    / "tracking"
    / "intraday_strategy_h1.csv"
)


FILTER_LOG_FILE = (
    ROOT
    / "data"
    / "tracking"
    / "intraday_strategy_h1_0931_live.csv"
)

FILTER_HOUR = 9
FILTER_MINUTE = 32
FILTER_SECOND = 2

LOWER_LIMIT = -3.0
UPPER_LIMIT = 1.0


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
        "SnapshotPrice",
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

        snapshot_price = pd.to_numeric(
            row["SnapshotPrice"],
            errors="coerce",
        )

        candidates.append(
            (
                code,
                f"H1 #{rank}",
                snapshot_price,
            )
        )

    print(
        "Snapshot :",
        target_time.strftime(
            "%H:%M:%S"
        ),
    )

    # ============================================
    # H1 TOP3?????RSS?????????
    # ============================================

    clear_h1_labels()

    # First register only the H1 rank labels.
    # PASS / SKIP is not known until the 09:32 filter runs.
    for code, label, snapshot_price in candidates:
        add_candidate(
            code,
            label,
        )

    # ============================================
    # 09:32:02????
    # ============================================

    now = datetime.now()

    filter_target = now.replace(
        hour=FILTER_HOUR,
        minute=FILTER_MINUTE,
        second=FILTER_SECOND,
        microsecond=0,
    )

    if now < filter_target:
        wait_seconds = (
            filter_target - now
        ).total_seconds()

        print()
        print(
            "Waiting for H1 filter :",
            filter_target.strftime(
                "%H:%M:%S"
            ),
        )

        time.sleep(
            max(
                0,
                wait_seconds,
            )
        )

        timing_status = "ON_TIME"

    else:
        timing_status = "LATE_TEST"

        print()
        print(
            "09:32 filter time already passed."
        )
        print(
            "Running as LATE_TEST."
        )

    # Excel/RSS?????????
    time.sleep(0.3)

    # ============================================
    # H1 09:31?????
    # ============================================

    print()
    print("=" * 60)
    print(" H1 09:31 FILTER CHECK")
    print("=" * 60)

    filter_rows = []

    for code, label, snapshot_price in candidates:

        current_price = get_current_price(
            code
        )

        filter_now = datetime.now()

        if (
            pd.isna(snapshot_price)
            or snapshot_price <= 0
            or current_price is None
        ):
            move_pct = None
            result = "NO DATA"

        else:
            move_pct = (
                current_price
                / float(snapshot_price)
                - 1
            ) * 100

            result = (
                "PASS"
                if (
                    LOWER_LIMIT
                    <= move_pct
                    < UPPER_LIMIT
                )
                else "SKIP"
            )

        rank = int(
            label.replace(
                "H1 #",
                "",
            )
        )

        print()
        print(
            f"{label} : {code}"
        )
        print(
            f"  H1 price    : {snapshot_price}"
        )
        print(
            f"  Filter price: {current_price}"
        )

        if move_pct is None:
            print(
                "  H1 move     : N/A"
            )
        else:
            print(
                f"  H1 move     : {move_pct:+.2f}%"
            )

        print(
            f"  Filter      : {result}"
        )

        # 09:31 filter result ?????????
        for i, item in enumerate(candidates):
            if item[0] == code:
                candidates[i] = (
                    item[0],
                    item[1],
                    item[2],
                    result,
                )
                break
        print(
            f"  Timing      : {timing_status}"
        )

        filter_rows.append(
            {
                "DetectionDate":
                    today,
                "SnapshotTime":
                    target_time.strftime(
                        "%H:%M:%S"
                    ),
                "Code":
                    code,
                "Rank":
                    rank,
                "SnapshotPrice":
                    snapshot_price,
                "FilterTime":
                    filter_now.strftime(
                        "%H:%M:%S.%f"
                    )[:-3],
                "FilterPrice":
                    current_price,
                "H1MovePct":
                    move_pct,
                "LowerLimit":
                    LOWER_LIMIT,
                "UpperLimit":
                    UPPER_LIMIT,
                "FilterResult":
                    result,
                "TimingStatus":
                    timing_status,
            }
        )

    # ============================================
    # Reflect final PASS / SKIP result to Excel
    # ============================================

    clear_h1_labels()

    for item in candidates:
        code = item[0]
        label = item[1]

        result = (
            item[3]
            if len(item) >= 4
            else "NO DATA"
        )

        final_label = (
            f"{label} {result}"
        )

        add_candidate(
            code,
            final_label,
        )

    print_board()

    # ============================================
    # ????????CSV??
    # ============================================

    if filter_rows:

        log_df = pd.DataFrame(
            filter_rows
        )

        FILTER_LOG_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if FILTER_LOG_FILE.exists():

            old_df = pd.read_csv(
                FILTER_LOG_FILE,
                dtype={
                    "Code": str,
                },
                low_memory=False,
            )

            log_df = pd.concat(
                [
                    old_df,
                    log_df,
                ],
                ignore_index=True,
            )

            log_df = (
                log_df
                .drop_duplicates(
                    subset=[
                        "DetectionDate",
                        "SnapshotTime",
                        "Code",
                    ],
                    keep="last",
                )
            )

        log_df.to_csv(
            FILTER_LOG_FILE,
            index=False,
            encoding="utf-8-sig",
        )

        print()
        print(
            f"H1 filter log : {FILTER_LOG_FILE}"
        )

    print()
    print(
        "H1 TOP3 live board update : OK"
    )


if __name__ == "__main__":
    main()
