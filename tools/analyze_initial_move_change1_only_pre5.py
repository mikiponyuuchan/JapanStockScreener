from pathlib import Path
import sys

import pandas as pd

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

from services.yahoo_service import _download_history_batch


INPUT_FILE = Path(
    "data/analysis/initial_move_change1_only_analysis.csv"
)

OUTPUT_FILE = Path(
    "data/analysis/initial_move_change1_only_pre5.csv"
)


def normalize_history(df):

    if df is None or df.empty:
        return None

    x = df.copy()

    if "Date" in x.columns:
        x["Date"] = pd.to_datetime(
            x["Date"],
            errors="coerce"
        )
        x = x.set_index("Date")

    x.index = pd.to_datetime(
        x.index,
        errors="coerce"
    )

    if getattr(x.index, "tz", None) is not None:
        x.index = x.index.tz_localize(None)

    x = x[
        ~x.index.isna()
    ].sort_index()

    return x


def pct(a, b):

    if pd.isna(a) or pd.isna(b) or b == 0:
        return None

    return (
        a / b - 1
    ) * 100


def main():

    df = pd.read_csv(
        INPUT_FILE,
        encoding="utf-8-sig"
    )

    df["DetectionDate"] = pd.to_datetime(
        df["DetectionDate"],
        errors="coerce"
    )

    df["Code"] = (
        df["Code"]
        .astype(str)
        .str.strip()
    )

    codes = sorted(
        df["Code"]
        .dropna()
        .unique()
        .tolist()
    )

    print("=" * 100)
    print("CHANGE1-ONLY PRE5 ANALYSIS")
    print("=" * 100)

    print("Target :", len(df))
    print("Codes  :", len(codes))

    print()
    print("Yahoo history downloading...")

    history_map = _download_history_batch(
        codes,
        period="3mo",
        batch_size=100
    )

    print(
        "Yahoo success :",
        len(history_map)
    )

    rows = []

    for _, row in df.iterrows():

        code = row["Code"]

        detection_date = pd.Timestamp(
            row["DetectionDate"]
        ).normalize()

        history = normalize_history(
            history_map.get(code)
        )

        out = row.to_dict()

        if history is None:

            rows.append(out)
            continue

        pre = history[
            history.index.normalize()
            < detection_date
        ].tail(5)

        detection = history[
            history.index.normalize()
            == detection_date
        ]

        if len(pre) < 5 or detection.empty:

            rows.append(out)
            continue

        det = detection.iloc[-1]

        # ======================================
        # Pre5 ～ Pre1 raw OHLCV
        # ======================================

        for i in range(5):

            bar = pre.iloc[i]

            day_num = 5 - i

            out[
                f"Pre{day_num}Date"
            ] = pre.index[i].date()

            for col in [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]:

                out[
                    f"Pre{day_num}{col}"
                ] = pd.to_numeric(
                    bar.get(col),
                    errors="coerce"
                )

        # ======================================
        # Detection raw
        # ======================================

        for col in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:

            out[
                f"Detection{col}"
            ] = pd.to_numeric(
                det.get(col),
                errors="coerce"
            )

        pre5_close = out.get(
            "Pre5Close"
        )

        pre1_close = out.get(
            "Pre1Close"
        )

        det_close = out.get(
            "DetectionClose"
        )

        det_open = out.get(
            "DetectionOpen"
        )

        # ======================================
        # 検出前5日トレンド
        # ======================================

        out["Pre5ToPre1Pct"] = pct(
            pre1_close,
            pre5_close
        )

        # ======================================
        # 検出日の寄り→終値
        # ======================================

        out["DetectionOpenToClosePct"] = pct(
            det_close,
            det_open
        )

        # ======================================
        # 出来高
        # ======================================

        pre_volumes = pd.to_numeric(
            pre["Volume"],
            errors="coerce"
        )

        pre5_vol_mean = pre_volumes.mean()

        pre1_volume = out.get(
            "Pre1Volume"
        )

        det_volume = out.get(
            "DetectionVolume"
        )

        out["Pre5VolumeMean"] = (
            pre5_vol_mean
        )

        out["DetectionVolumeVsPre5"] = (
            det_volume / pre5_vol_mean
            if (
                pd.notna(det_volume)
                and pd.notna(pre5_vol_mean)
                and pre5_vol_mean != 0
            )
            else None
        )

        out["DetectionVolumeVsPre1"] = (
            det_volume / pre1_volume
            if (
                pd.notna(det_volume)
                and pd.notna(pre1_volume)
                and pre1_volume != 0
            )
            else None
        )

        # ======================================
        # 検出前5日の高値・安値レンジ
        # ======================================

        pre_high = pd.to_numeric(
            pre["High"],
            errors="coerce"
        ).max()

        pre_low = pd.to_numeric(
            pre["Low"],
            errors="coerce"
        ).min()

        out["Pre5RangePct"] = pct(
            pre_high,
            pre_low
        )

        # 検出前5日高値から前日終値まで
        out["Pre1CloseVsPre5HighPct"] = pct(
            pre1_close,
            pre_high
        )

        rows.append(out)

    result = pd.DataFrame(rows)

    # ==========================================
    # 保存
    # ==========================================

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(
        "Saved :",
        OUTPUT_FILE
    )

    # ==========================================
    # 成功 / 中間 / 失敗 比較
    # ==========================================

    factors = [
        "Pre5ToPre1Pct",
        "Pre5RangePct",
        "Pre1CloseVsPre5HighPct",
        "DetectionOpenToClosePct",
        "DetectionVolumeVsPre1",
        "DetectionVolumeVsPre5",
    ]

    print()
    print("=" * 100)
    print("PRE-DETECTION FACTORS")
    print("=" * 100)

    for factor in factors:

        print()
        print(
            f"[{factor}]"
        )

        for group in [
            "Success",
            "Middle",
            "Failure",
        ]:

            g = result[
                result["OutcomeGroup"]
                == group
            ]

            s = pd.to_numeric(
                g[factor],
                errors="coerce"
            ).dropna()

            if s.empty:
                continue

            print(
                f"{group:8s} "
                f"N={len(s):2d}  "
                f"mean={s.mean():8.2f}  "
                f"median={s.median():8.2f}  "
                f"min={s.min():8.2f}  "
                f"max={s.max():8.2f}"
            )

    # ==========================================
    # 個別一覧
    # ==========================================

    print()
    print("=" * 100)
    print("DETAIL")
    print("=" * 100)

    cols = [
        "DetectionDate",
        "Code",
        "Name",
        "OutcomeGroup",
        "Change1",
        "Change5",
        "VolumeRatio",
        "Pre5ToPre1Pct",
        "Pre1CloseVsPre5HighPct",
        "DetectionOpenToClosePct",
        "DetectionVolumeVsPre1",
        "DetectionVolumeVsPre5",
        "MaxHigh5Pct",
        "MinLow5Pct",
    ]

    print(
        result[cols]
        .sort_values(
            [
                "OutcomeGroup",
                "MaxHigh5Pct",
            ],
            ascending=[
                True,
                False,
            ]
        )
        .to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
