import sys
import time
from pathlib import Path

import pandas as pd


# ==========================================
# Project paths
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))


from services.yahoo_credit_service import (  # noqa: E402
    DATA_DIR,
    download_credit_batch,
)


# ==========================================
# Settings
# ==========================================

JPX_LIST = (
    PROJECT_ROOT
    / "data"
    / "jpx_stock_list.xls"
)

FAILED_FILE = (
    PROJECT_ROOT
    / "data"
    / "yahoo_credit_failed.csv"
)

BATCH_SIZE = 50
BATCH_WAIT_SECONDS = 20 * 60


TARGET_MARKETS = [
    "プライム（内国株式）",
    "スタンダード（内国株式）",
    "グロース（内国株式）",
]


# ==========================================
# Load JPX target codes
# ==========================================

def load_target_codes():

    df = pd.read_excel(
        JPX_LIST,
        dtype={"コード": str},
    )

    df["コード"] = (
        df["コード"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["市場・商品区分"].isin(
            TARGET_MARKETS
        )
    ].copy()

    return df["コード"].tolist()


# ==========================================
# Existing CSV codes
# ==========================================

def get_existing_codes():

    return {
        path.stem
        for path in DATA_DIR.glob("*.csv")
    }


# ==========================================
# Failed codes
# ==========================================

def get_failed_codes():

    if not FAILED_FILE.exists():
        return set()

    try:

        df = pd.read_csv(
            FAILED_FILE,
            dtype=str,
            encoding="utf-8-sig",
        )

        if "code" not in df.columns:
            return set()

        return {
            str(code).strip()
            for code in df["code"]
            if pd.notna(code)
        }

    except Exception as e:

        print(
            "Failed-code list read error:"
            f" {e}"
        )

        return set()


# ==========================================
# Main
# ==========================================

def main():

    print()
    print("=" * 60)
    print(" Yahoo credit data automatic download")
    print("=" * 60)
    print()

    # --------------------------------------
    # Target codes
    # --------------------------------------

    codes = load_target_codes()

    # --------------------------------------
    # Current status
    # --------------------------------------

    existing = get_existing_codes()
    failed = get_failed_codes()

    # IMPORTANT:
    # Existing CSV files are NOT excluded.
    # Every eligible code is checked on Yahoo.
    remaining = [
        code
        for code in codes
        if code not in failed
    ]

    print(
        f"Target codes       : {len(codes)}"
    )

    print(
        f"Existing CSV       : {len(existing)}"
    )

    print(
        f"Blacklist          : {len(failed)}"
    )

    print(
        f"Yahoo check target : {len(remaining)}"
    )

    print(
        f"Batch size         : {BATCH_SIZE}"
    )

    print(
        f"Batch wait         : "
        f"{BATCH_WAIT_SECONDS // 60} minutes"
    )

    print()

    if not remaining:

        print(
            "No target codes."
        )

        return

    # ======================================
    # Process 50 codes at a time
    # ======================================

    batch_number = 0

    while remaining:

        batch_number += 1

        # ----------------------------------
        # Refresh blacklist
        # ----------------------------------

        failed = get_failed_codes()

        remaining = [
            code
            for code in codes
            if code not in failed
        ]

        if not remaining:
            break

        targets = remaining[:BATCH_SIZE]

        print()
        print("=" * 60)

        print(
            f"Batch {batch_number}"
        )

        print(
            f"Target this batch : "
            f"{len(targets)} codes"
        )

        print(
            f"Remaining         : "
            f"{len(remaining)} codes"
        )

        print(
            f"First             : "
            f"{targets[0]}"
        )

        print(
            f"Last              : "
            f"{targets[-1]}"
        )

        print("=" * 60)
        print()

        # ----------------------------------
        # Download
        # ----------------------------------

        try:

            result = download_credit_batch(
                targets
            )

            print()
            print(
                f"Batch {batch_number} completed"
            )

            print(
                f"Successful : "
                f"{len(result)} codes"
            )

        except KeyboardInterrupt:

            print()
            print(
                "Download stopped by user."
            )

            break

        except Exception as e:

            print()
            print(
                "Unexpected batch error:"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            print()
            print(
                "Waiting 30 minutes before restart."
            )

            try:

                time.sleep(
                    30 * 60
                )

            except KeyboardInterrupt:

                print()
                print(
                    "Download stopped by user."
                )

                break

        # ----------------------------------
        # Refresh status
        # ----------------------------------

        existing = get_existing_codes()
        failed = get_failed_codes()

        remaining = [
            code
            for code in codes
            if code not in failed
        ]

        print()
        print(
            "-" * 60
        )

        print(
            "Current progress"
        )

        print(
            f"Existing CSV       : "
            f"{len(existing)}"
        )

        print(
            f"Blacklist          : "
            f"{len(failed)}"
        )

        print(
            f"Yahoo check remain : "
            f"{len(remaining)}"
        )

        print(
            "-" * 60
        )

        if not remaining:

            break

        # ----------------------------------
        # Wait before next batch
        # ----------------------------------

        print()
        print(
            "Yahoo load protection:"
        )

        print(
            f"{BATCH_WAIT_SECONDS // 60} "
            "minutes waiting..."
        )

        try:

            for wait_seconds in range(
                BATCH_WAIT_SECONDS,
                0,
                -60,
            ):

                minutes = wait_seconds // 60

                print(
                    f"Restart in about "
                    f"{minutes} minutes..."
                )

                time.sleep(
                    min(60, wait_seconds)
                )

        except KeyboardInterrupt:

            print()
            print(
                "Download stopped by user."
            )

            break

        print()
        print(
            "20-minute wait completed."
        )

        print(
            "Starting next 50 codes."
        )

    # ======================================
    # Final status
    # ======================================

    existing = get_existing_codes()
    failed = get_failed_codes()

    remaining = [
        code
        for code in codes
        if code not in failed
    ]

    print()
    print("=" * 60)
    print(" Yahoo credit data download finished")
    print("=" * 60)

    print(
        f"Target codes       : {len(codes)}"
    )

    print(
        f"Existing CSV       : {len(existing)}"
    )

    print(
        f"Blacklist          : {len(failed)}"
    )

    print(
        f"Yahoo check remain : {len(remaining)}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()