import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


BASELINE_FILE = (
    ROOT
    / "data"
    / "cache"
    / "morning_baseline.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "analysis"
    / "morning"
)

BATCH_SIZE = 100


def _extract_ticker_df(
    raw_df,
    ticker,
    batch_size,
):
    if raw_df is None or raw_df.empty:
        return None

    try:
        if isinstance(
            raw_df.columns,
            pd.MultiIndex,
        ):
            level0 = (
                raw_df.columns
                .get_level_values(0)
            )

            level1 = (
                raw_df.columns
                .get_level_values(1)
            )

            if ticker in level0:
                df = raw_df[
                    ticker
                ].copy()

            elif ticker in level1:
                df = raw_df.loc[
                    :,
                    ticker
                ].copy()

            else:
                return None

        else:
            if batch_size != 1:
                return None

            df = raw_df.copy()

        df = df.dropna(
            how="all"
        )

        if df.empty:
            return None

        return df

    except Exception:
        return None


def _pct(
    value,
    base,
):
    if (
        pd.isna(value)
        or pd.isna(base)
        or float(base) == 0
    ):
        return None

    return (
        float(value)
        / float(base)
        - 1.0
    ) * 100.0


def _download_morning(
    codes,
):
    rows = []

    total = len(codes)

    start_time = (
        time.perf_counter()
    )

    success = 0
    empty = 0
    error_batches = 0

    for batch_start in range(
        0,
        total,
        BATCH_SIZE,
    ):
        batch_codes = codes[
            batch_start:
            batch_start + BATCH_SIZE
        ]

        tickers = [
            f"{code}.T"
            for code in batch_codes
        ]

        try:
            raw_df = yf.download(
                tickers=tickers,
                period="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )

        except Exception as e:
            error_batches += 1

            print(
                "Yahoo batch ERROR : "
                f"{e}"
            )

            continue

        for code in batch_codes:
            ticker = f"{code}.T"

            df = _extract_ticker_df(
                raw_df,
                ticker,
                len(batch_codes),
            )

            if df is None or df.empty:
                empty += 1
                continue

            latest = df.iloc[-1]

            open_value = pd.to_numeric(
                latest.get("Open"),
                errors="coerce",
            )

            high_value = pd.to_numeric(
                latest.get("High"),
                errors="coerce",
            )

            low_value = pd.to_numeric(
                latest.get("Low"),
                errors="coerce",
            )

            close_value = pd.to_numeric(
                latest.get("Close"),
                errors="coerce",
            )

            volume_value = pd.to_numeric(
                latest.get("Volume"),
                errors="coerce",
            )

            if pd.isna(close_value):
                empty += 1
                continue

            rows.append(
                {
                    "Code": str(code),
                    "MorningOpen": open_value,
                    "MorningHigh": high_value,
                    "MorningLow": low_value,
                    "MorningPrice": close_value,
                    "MorningVolume": volume_value,
                }
            )

            success += 1

        completed = min(
            batch_start
            + len(batch_codes),
            total,
        )

        if (
            completed % 1000 == 0
            or completed == total
        ):
            elapsed = (
                time.perf_counter()
                - start_time
            )

            print(
                f"Yahoo morning : "
                f"{completed} / {total} "
                f"({elapsed:.1f}s)"
            )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    print()
    print(
        "Yahoo morning success : "
        f"{success}"
    )
    print(
        "Yahoo morning empty   : "
        f"{empty}"
    )
    print(
        "Yahoo batch errors    : "
        f"{error_batches}"
    )
    print(
        "Yahoo morning time    : "
        f"{elapsed:.1f} sec"
    )

    return pd.DataFrame(rows)


def main():
    print("=" * 60)
    print("Morning Screener - Data Build")
    print("=" * 60)

    fetch_time = datetime.now()

    print(
        "Fetch time : "
        + fetch_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    if not BASELINE_FILE.exists():
        raise RuntimeError(
            "Morning baseline not found : "
            f"{BASELINE_FILE}"
        )

    baseline = pd.read_csv(
        BASELINE_FILE,
        dtype={
            "Code": str,
        },
    )

    required = [
        "Code",
        "Name",
        "BaseDate",
        "PrevClose",
        "Prev20High",
        "Prev30High",
        "MA5",
        "MA25",
        "Prev5AvgVolume",
    ]

    missing = [
        col
        for col in required
        if col not in baseline.columns
    ]

    if missing:
        raise RuntimeError(
            "Baseline columns missing : "
            + ", ".join(missing)
        )

    baseline["Code"] = (
        baseline["Code"]
        .astype(str)
    )

    codes = (
        baseline["Code"]
        .drop_duplicates()
        .tolist()
    )

    print(
        "Baseline date   : "
        f"{baseline['BaseDate'].max()}"
    )
    print(
        "Baseline stocks : "
        f"{len(codes)}"
    )
    print()

    morning = _download_morning(
        codes
    )

    if morning.empty:
        raise RuntimeError(
            "Morning Yahoo data is empty"
        )

    merged = baseline.merge(
        morning,
        on="Code",
        how="left",
    )

    # --------------------------------
    # Morning-only derived metrics
    # --------------------------------

    merged[
        "MorningChangePct"
    ] = merged.apply(
        lambda r: _pct(
            r["MorningPrice"],
            r["PrevClose"],
        ),
        axis=1,
    )

    merged[
        "OpenGapPct"
    ] = merged.apply(
        lambda r: _pct(
            r["MorningOpen"],
            r["PrevClose"],
        ),
        axis=1,
    )

    merged[
        "OpenToPricePct"
    ] = merged.apply(
        lambda r: _pct(
            r["MorningPrice"],
            r["MorningOpen"],
        ),
        axis=1,
    )

    merged[
        "PriceVs20HighPct"
    ] = merged.apply(
        lambda r: _pct(
            r["MorningPrice"],
            r["Prev20High"],
        ),
        axis=1,
    )

    merged[
        "PriceVs30HighPct"
    ] = merged.apply(
        lambda r: _pct(
            r["MorningPrice"],
            r["Prev30High"],
        ),
        axis=1,
    )

    merged[
        "RoomTo30HighPct"
    ] = merged.apply(
        lambda r: _pct(
            r["Prev30High"],
            r["MorningPrice"],
        ),
        axis=1,
    )

    merged[
        "ResistanceGapPct"
    ] = merged.apply(
        lambda r: _pct(
            r["Prev30High"],
            r["Prev20High"],
        ),
        axis=1,
    )

    merged[
        "MorningVolumeVsPrev5"
    ] = merged.apply(
        lambda r: (
            float(r["MorningVolume"])
            / float(r["Prev5AvgVolume"])
            if (
                pd.notna(
                    r["MorningVolume"]
                )
                and pd.notna(
                    r["Prev5AvgVolume"]
                )
                and float(
                    r["Prev5AvgVolume"]
                ) > 0
            )
            else None
        ),
        axis=1,
    )

    merged[
        "MorningBullish"
    ] = (
        merged["MorningPrice"]
        > merged["MorningOpen"]
    )

    merged[
        "AbovePrev20High"
    ] = (
        merged["MorningPrice"]
        > merged["Prev20High"]
    )

    merged[
        "AbovePrev30High"
    ] = (
        merged["MorningPrice"]
        > merged["Prev30High"]
    )

    # --------------------------------
    # Save full morning panel
    # --------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        OUTPUT_DIR
        / (
            fetch_time.strftime(
                "%Y-%m-%d_%H%M"
            )
            + "_morning_panel.csv"
        )
    )

    merged.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    valid_count = int(
        merged["MorningPrice"]
        .notna()
        .sum()
    )

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)

    print(
        "Baseline stocks : "
        f"{len(baseline)}"
    )

    print(
        "Morning valid   : "
        f"{valid_count}"
    )

    print(
        "Bullish         : "
        f"{int(merged['MorningBullish'].sum())}"
    )

    print(
        "Above 20High    : "
        f"{int(merged['AbovePrev20High'].sum())}"
    )

    print(
        "Above 30High    : "
        f"{int(merged['AbovePrev30High'].sum())}"
    )

    print()
    print(
        "Saved : "
        f"{output_file}"
    )


if __name__ == "__main__":
    main()
