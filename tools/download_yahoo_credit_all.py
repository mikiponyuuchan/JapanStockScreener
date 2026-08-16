import sys
import time
from pathlib import Path

import pandas as pd


# ==========================================
# プロジェクトの src を import 対象にする
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))


from services.yahoo_credit_service import (  # noqa: E402
    DATA_DIR,
    download_credit_batch,
)


# ==========================================
# 設定
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


TARGET_MARKETS = [
    "プライム（内国株式）",
    "スタンダード（内国株式）",
    "グロース（内国株式）",
]


# ==========================================
# JPX銘柄一覧を取得
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
# 取得済み銘柄
# ==========================================

def get_existing_codes():

    return {
        path.stem
        for path in DATA_DIR.glob("*.csv")
    }


# ==========================================
# ブラックリスト
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
            "ブラックリスト読込失敗:"
            f" {e}"
        )

        return set()


# ==========================================
# メイン
# ==========================================

def main():

    print()
    print("=" * 60)
    print(" Yahoo信用データ 夜間自動取得")
    print("=" * 60)
    print()

    # --------------------------------------
    # 対象銘柄
    # --------------------------------------

    codes = load_target_codes()

    # --------------------------------------
    # 状態確認
    # --------------------------------------

    existing = get_existing_codes()

    failed = get_failed_codes()

    remaining = [
        code
        for code in codes
        if code not in existing
        and code not in failed
    ]

    print(
        f"対象銘柄数   : {len(codes)}"
    )

    print(
        f"取得済み     : {len(existing)}"
    )

    print(
        f"ブラックリスト: {len(failed)}"
    )

    print(
        f"残り未取得   : {len(remaining)}"
    )

    print(
        f"1バッチ      : {BATCH_SIZE} 銘柄"
    )

    print()

    if not remaining:

        print(
            "未取得銘柄はありません。"
        )

        return

    # ======================================
    # 50銘柄ずつ自動取得
    # ======================================

    batch_number = 0

    while remaining:

        batch_number += 1

        # ----------------------------------
        # 最新状態を再確認
        # ----------------------------------

        existing = get_existing_codes()

        failed = get_failed_codes()

        remaining = [
            code
            for code in codes
            if code not in existing
            and code not in failed
        ]

        if not remaining:
            break

        targets = remaining[:BATCH_SIZE]

        print()
        print("=" * 60)

        print(
            f"バッチ {batch_number}"
        )

        print(
            f"今回の対象 : {len(targets)} 銘柄"
        )

        print(
            f"残り       : {len(remaining)} 銘柄"
        )

        print(
            f"先頭       : {targets[0]}"
        )

        print(
            f"末尾       : {targets[-1]}"
        )

        print("=" * 60)
        print()

        # ----------------------------------
        # 取得
        # ----------------------------------

        try:

            result = download_credit_batch(
                targets
            )

            print()
            print(
                f"バッチ {batch_number} 完了"
            )

            print(
                f"今回取得成功 : "
                f"{len(result)} 銘柄"
            )

        except KeyboardInterrupt:

            print()
            print(
                "ユーザー操作により"
                "取得を停止しました。"
            )

            break

        except Exception as e:

            print()
            print(
                "バッチ処理で予期しない"
                "エラーが発生しました。"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            print()
            print(
                "30分後に自動再開します。"
            )

            try:

                time.sleep(
                    30 * 60
                )

            except KeyboardInterrupt:

                print()
                print(
                    "ユーザー操作により"
                    "取得を停止しました。"
                )

                break

        # ----------------------------------
        # 次のバッチ前に状態更新
        # ----------------------------------

        existing = get_existing_codes()

        failed = get_failed_codes()

        remaining = [
            code
            for code in codes
            if code not in existing
            and code not in failed
        ]

        print()
        print(
            "-" * 60
        )

        print(
            "現在の進捗"
        )

        print(
            f"取得済み       : "
            f"{len(existing)}"
        )

        print(
            f"ブラックリスト : "
            f"{len(failed)}"
        )

        print(
            f"残り未取得     : "
            f"{len(remaining)}"
        )

        print(
            "-" * 60
        )

        if not remaining:

            break

        # ----------------------------------
        # 次バッチ
        # ----------------------------------

        print()
        print(
            "Yahoo負荷対策:"
        )
        print(
            "15分休憩します..."
        )

        try:

            for wait_seconds in range(
                15 * 60,
                0,
                -60,
            ):

                minutes = wait_seconds // 60

                print(
                    f"再開まで約 {minutes} 分..."
                )

                time.sleep(
                    min(60, wait_seconds)
                )

        except KeyboardInterrupt:

            print()
            print(
                "ユーザー操作により"
                "取得を中断しました。"
            )

            break

        print()
        print(
            "15分休憩が完了しました。"
        )
        print(
            "次の50銘柄へ進みます。"
        )

    # ======================================
    # 完了
    # ======================================

    existing = get_existing_codes()

    failed = get_failed_codes()

    remaining = [
        code
        for code in codes
        if code not in existing
        and code not in failed
    ]

    print()
    print("=" * 60)
    print(" Yahoo信用データ取得終了")
    print("=" * 60)

    print(
        f"対象銘柄数       : {len(codes)}"
    )

    print(
        f"取得済み         : {len(existing)}"
    )

    print(
        f"ブラックリスト   : {len(failed)}"
    )

    print(
        f"残り未取得       : {len(remaining)}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()