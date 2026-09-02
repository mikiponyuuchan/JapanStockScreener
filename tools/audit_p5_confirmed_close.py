import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, "src")

from services.tracking_service import add_business_days
from services.p5_tracking_service import _judge_p5_day2


INPUT_FILE = Path("data/tracking/p5_tracking.csv")
OUTPUT_DIR = Path("data/analysis")
OUTPUT_FILE = OUTPUT_DIR / "p5_tracking_confirmed_audit.csv"

BUY = "\u8cb7\u3044"
SKIP = "\u898b\u9001\u308a"


def normalize_code(value):
    if pd.isna(value):
        return ""

    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    return code


def num(value):
    return pd.to_numeric(
        value,
        errors="coerce",
    )


def calc_change(base, price):
    base = num(base)
    price = num(price)

    if (
        pd.isna(base)
        or pd.isna(price)
        or base == 0
    ):
        return pd.NA

    return round(
        (price / base - 1.0) * 100.0,
        2,
    )


def download_history(codes):
    result = {}

    codes = sorted(
        {
            normalize_code(code)
            for code in codes
            if normalize_code(code)
        }
    )

    batch_size = 100

    for start in range(
        0,
        len(codes),
        batch_size,
    ):
        batch = codes[
            start:start + batch_size
        ]

        tickers = [
            f"{code}.T"
            for code in batch
        ]

        print(
            "Yahoo:",
            min(
                start + batch_size,
                len(codes),
            ),
            "/",
            len(codes),
        )

        try:
            raw = yf.download(
                tickers=tickers,
                period="3mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )

        except Exception as e:
            print(
                "Yahoo ERROR:",
                e,
            )
            continue

        for code in batch:
            ticker = f"{code}.T"

            try:
                if isinstance(
                    raw.columns,
                    pd.MultiIndex,
                ):
                    level0 = (
                        raw.columns
                        .get_level_values(0)
                    )

                    if ticker not in level0:
                        continue

                    df = raw[ticker].copy()

                else:
                    if len(batch) != 1:
                        continue

                    df = raw.copy()

                if "Close" not in df.columns:
                    continue

                df = df.dropna(
                    subset=["Close"]
                )

                if df.empty:
                    continue

                idx = pd.to_datetime(
                    df.index,
                    errors="coerce",
                )

                try:
                    idx = idx.tz_localize(None)
                except TypeError:
                    try:
                        idx = idx.tz_convert(None)
                    except Exception:
                        pass

                df.index = idx
                df = df[
                    ~df.index.isna()
                ].copy()

                df.index = (
                    pd.DatetimeIndex(
                        df.index
                    ).normalize()
                )

                result[code] = df

            except Exception:
                continue

    return result


def exact_close(
    history,
    target_date,
    today,
):
    if history is None:
        return pd.NA

    target_date = pd.Timestamp(
        target_date
    ).normalize()

    # Never use today's daily bar.
    if target_date >= today:
        return pd.NA

    exact = history.loc[
        history.index == target_date
    ]

    if exact.empty:
        return pd.NA

    close = num(
        exact.iloc[-1]["Close"]
    )

    if pd.isna(close):
        return pd.NA

    return float(close)


def different(a, b, tolerance=0.001):
    a = num(a)
    b = num(b)

    if pd.isna(a) and pd.isna(b):
        return False

    if pd.isna(a) != pd.isna(b):
        return True

    return abs(float(a) - float(b)) > tolerance


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            INPUT_FILE
        )

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig",
        dtype={"Code": str},
    )

    df["Code"] = (
        df["Code"]
        .map(normalize_code)
    )

    df["DetectionDate"] = pd.to_datetime(
        df["DetectionDate"],
        errors="coerce",
    )

    today = pd.Timestamp.today().normalize()

    history_map = download_history(
        df["Code"].dropna().tolist()
    )

    rows = []

    for _, row in df.iterrows():
        detection_date = row["DetectionDate"]

        if pd.isna(detection_date):
            continue

        detection_date = (
            detection_date.normalize()
        )

        code = normalize_code(
            row["Code"]
        )

        base_price = num(
            row.get("BasePrice")
        )

        day1_date = add_business_days(
            detection_date,
            1,
        )

        day2_date = add_business_days(
            detection_date,
            2,
        )

        history = history_map.get(
            code
        )

        correct_day1_price = exact_close(
            history,
            day1_date,
            today,
        )

        correct_day2_price = exact_close(
            history,
            day2_date,
            today,
        )

        correct_day1 = calc_change(
            base_price,
            correct_day1_price,
        )

        correct_day2 = calc_change(
            base_price,
            correct_day2_price,
        )

        correct_drop = pd.NA
        new_decision = ""
        new_reason = ""

        if (
            pd.notna(correct_day1)
            and pd.notna(correct_day2)
        ):
            correct_drop = round(
                float(correct_day2)
                - float(correct_day1),
                2,
            )

            change5 = num(
                row.get("Change5")
            )

            volume_ratio20 = num(
                row.get(
                    "VolumeRatio20"
                )
            )

            new_decision, new_reason = (
                _judge_p5_day2(
                    float(correct_day1),
                    float(correct_day2),
                    change5,
                    volume_ratio20,
                )
            )

        old_day1_price = num(
            row.get("Day1Price")
        )

        old_day2_price = num(
            row.get("Day2Price")
        )

        old_day1 = num(
            row.get("Day1")
        )

        old_day2 = num(
            row.get("Day2")
        )

        old_drop = num(
            row.get("Drop")
        )

        old_decision = str(
            row.get(
                "BuyDecision",
                "",
            )
        ).strip()

        day1_price_changed = different(
            old_day1_price,
            correct_day1_price,
        )

        day2_price_changed = different(
            old_day2_price,
            correct_day2_price,
        )

        decision_changed = (
            bool(old_decision)
            and bool(new_decision)
            and old_decision != new_decision
        )

        rows.append(
            {
                "DetectionDate":
                    detection_date.strftime(
                        "%Y-%m-%d"
                    ),
                "Code":
                    code,
                "Name":
                    row.get("Name", ""),
                "BasePrice":
                    base_price,

                "Day1Date":
                    day1_date.strftime(
                        "%Y-%m-%d"
                    ),
                "OldDay1Price":
                    old_day1_price,
                "CorrectDay1Price":
                    correct_day1_price,
                "OldDay1":
                    old_day1,
                "CorrectDay1":
                    correct_day1,
                "Day1PriceChanged":
                    day1_price_changed,

                "Day2Date":
                    day2_date.strftime(
                        "%Y-%m-%d"
                    ),
                "OldDay2Price":
                    old_day2_price,
                "CorrectDay2Price":
                    correct_day2_price,
                "OldDay2":
                    old_day2,
                "CorrectDay2":
                    correct_day2,
                "Day2PriceChanged":
                    day2_price_changed,

                "OldDrop":
                    old_drop,
                "CorrectDrop":
                    correct_drop,

                "Change5":
                    num(
                        row.get("Change5")
                    ),
                "VolumeRatio20":
                    num(
                        row.get(
                            "VolumeRatio20"
                        )
                    ),

                "OldDecision":
                    old_decision,
                "OldReason":
                    row.get(
                        "BuyReason",
                        "",
                    ),
                "CorrectDecision":
                    new_decision,
                "CorrectReason":
                    new_reason,
                "DecisionChanged":
                    decision_changed,
            }
        )

    audit = pd.DataFrame(
        rows
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 72)
    print("P5 CONFIRMED-CLOSE AUDIT")
    print("=" * 72)
    print(
        "Tracking rows        :",
        len(df),
    )
    print(
        "Audit rows           :",
        len(audit),
    )

    if audit.empty:
        return

    d1_ready = audit[
        "CorrectDay1Price"
    ].notna()

    d2_ready = audit[
        "CorrectDay2Price"
    ].notna()

    print(
        "Confirmed Day1 rows  :",
        int(d1_ready.sum()),
    )
    print(
        "Confirmed Day2 rows  :",
        int(d2_ready.sum()),
    )

    print(
        "Day1 price changed   :",
        int(
            (
                audit["Day1PriceChanged"]
                & d1_ready
            ).sum()
        ),
    )

    print(
        "Day2 price changed   :",
        int(
            (
                audit["Day2PriceChanged"]
                & d2_ready
            ).sum()
        ),
    )

    comparable = (
        audit["OldDecision"].astype(
            str
        ).str.len() > 0
    ) & (
        audit["CorrectDecision"].astype(
            str
        ).str.len() > 0
    )

    changed = (
        audit["DecisionChanged"]
        & comparable
    )

    print(
        "Decision comparable  :",
        int(comparable.sum()),
    )
    print(
        "Decision changed     :",
        int(changed.sum()),
    )

    if comparable.any():

        old_buy = (
            audit.loc[
                comparable,
                "OldDecision",
            ] == BUY
        ).sum()

        new_buy = (
            audit.loc[
                comparable,
                "CorrectDecision",
            ] == BUY
        ).sum()

        print(
            "Old BUY             :",
            int(old_buy),
        )
        print(
            "Correct BUY         :",
            int(new_buy),
        )

    print(
        "Saved                :",
        OUTPUT_FILE,
    )

    if changed.any():

        print()
        print("=" * 72)
        print("DECISION CHANGES")
        print("=" * 72)

        cols = [
            "DetectionDate",
            "Code",
            "Name",
            "OldDay1",
            "CorrectDay1",
            "OldDay2",
            "CorrectDay2",
            "OldDrop",
            "CorrectDrop",
            "OldDecision",
            "CorrectDecision",
        ]

        print(
            audit.loc[
                changed,
                cols,
            ].to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
