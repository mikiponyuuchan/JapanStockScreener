import json
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

PROGRESS_FILE = (
    PROJECT_ROOT
    / "data"
    / "yahoo_credit_progress.json"
)

BATCH_SIZE = 50

BATCH_WAIT_SECONDS = 20 * 60


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
# 進捗読み込み
# ==========================================

def load_progress():

    if not PROGRESS_FILE.exists():
        return None

    try:

        with open(
            PROGRESS_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        last_completed_code = str(
            data.get(
                "last_completed_code",
                "",
            )
        ).strip()

        next_code = str(
            data.get(
                "next_code",
                "",
            )
        ).strip()

        return {
            "last_completed_code": last_completed_code,
            "next_code": next_code,
        }

    except Exception as e:

        print(
            "進捗ファイル読込失敗:"
            f" {e}"
        )

        return None

# ==========================================
# 進捗保存
# ==========================================

def save_progress(
    last_completed_code,
    next_code,
):
    data = {
        "last_completed_code": last_completed_code,
        "next_code": next_code,
    }

    try:

        with open(
            PROGRESS_FILE,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2,
            )

    except Exception as e:

        print(
            "進捗保存失敗:"
            f" {e}"
        )
    try:

        with open(
            PROGRESS_FILE,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2,
            )

    except Exception as e:

        print(
            "進捗保存失敗:"
            f" {e}"
        )


# ==========================================
# 開始位置を決定
# ==========================================

def select_start_index(codes):

    progress = load_progress()

    if progress is None:

        default_index = 0
        default_text = codes[0]

    else:

        last_code = progress[
            "last_completed_code"
        ]

        next_code = progress[
            "next_code"
        ]

        if (
            next_code
            and next_code in codes
        ):

            default_index = codes.index(
                next_code
            )

        elif (
            last_code
            and last_code in codes
        ):

            actual_index = codes.index(
                last_code
            )

            default_index = (
                actual_index + 1
            )

        else:

            default_index = 0

        if default_index < len(codes):
            default_text = codes[
                default_index
            ]
        else:
            default_text = ""

    print()
    print("=" * 60)
    print("前回の取得状況")
    print("=" * 60)

    if progress is None:

        print(
            "前回の進捗はありません。"
        )

    else:

        print(
            f"最後に完了した銘柄 : "
            f"{progress['last_completed_code']}"
        )

        if progress["next_code"]:

            print(
                f"次に開始する銘柄   : "
                f"{progress['next_code']}"
            )

    print()
    print(
        f"Enter : "
        f"{default_text} から再開"
    )

    print(
        "番号   : 指定した番号から開始"
    )

    print(
        "q      : 終了"
    )

    print()

    try:

        value = input(
            f"開始銘柄 [{default_text}]: "
        ).strip()

    except (EOFError, KeyboardInterrupt):

        print()
        print(
            "ユーザー操作により終了します。"
        )

        return None

    if value.lower() == "q":

        print()
        print(
            "取得を開始せず終了します。"
        )

        return None

    if value == "":

        return default_index

    # 銘柄コードを直接入力した場合
    if value in codes:

        return codes.index(value)

    # 従来どおり番号指定も可能
    try:

        number = int(value)

    except ValueError:

        print()
        print(
            "銘柄コードまたは番号を入力してください。"
        )

        return select_start_index(
            codes
        )

    if (
        number < 1
        or number > len(codes)
    ):

        print()
        print(
            f"1～{len(codes)}の範囲で"
            "指定してください。"
        )

        return select_start_index(
            codes
        )

    return number - 1

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

    print(
        f"対象銘柄数     : {len(codes)}"
    )

    print(
        f"既存CSV        : {len(existing)}"
    )

    print(
        f"ブラックリスト : {len(failed)}"
    )

    print()

    if not codes:

        print(
            "対象銘柄がありません。"
        )

        return

    # --------------------------------------
    # 開始位置
    # --------------------------------------

    start_index = select_start_index(
        codes
    )

    if start_index is None:
        return

    # --------------------------------------
    # ブラックリストを除外
    # --------------------------------------

    remaining = [
        (
            index,
            code,
        )
        for index, code
        in enumerate(codes)
        if (
            index >= start_index
            and code not in failed
        )
    ]

    if not remaining:

        print()
        print(
            "指定位置以降に"
            "取得対象銘柄がありません。"
        )

        return

    print()
    print("=" * 60)
    print(
        f"{start_index + 1}番目から開始します。"
    )
    print(
        f"対象 : "
        f"{len(remaining)} 銘柄"
    )
    print("=" * 60)

    # ======================================
    # 50銘柄ずつ自動取得
    # ======================================

    batch_number = 0

    position = 0

    while position < len(remaining):

        batch_number += 1

        batch = remaining[
            position:
            position + BATCH_SIZE
        ]

        targets = [
            code
            for _, code in batch
        ]

        first_index = batch[0][0]
        last_index = batch[-1][0]

        print()
        print("=" * 60)

        print(
            f"バッチ {batch_number}"
        )

        print(
            f"今回の対象 : "
            f"{len(targets)} 銘柄"
        )

        print(
            f"位置       : "
            f"{first_index + 1}"
            f"～"
            f"{last_index + 1}"
        )

        print(
            f"先頭       : "
            f"{targets[0]}"
        )

        print(
            f"末尾       : "
            f"{targets[-1]}"
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

                for wait_seconds in range(
                    30 * 60,
                    0,
                    -60,
                ):

                    minutes = (
                        wait_seconds // 60
                    )

                    print(
                        f"再開まで約 "
                        f"{minutes} 分..."
                    )

                    time.sleep(
                        min(
                            60,
                            wait_seconds,
                        )
                    )

            except KeyboardInterrupt:

                print()
                print(
                    "ユーザー操作により"
                    "取得を停止しました。"
                )

                break

            continue

        # ----------------------------------
        # 進捗保存
        # ----------------------------------

        success_codes = list(
            result.keys()
        )

        if success_codes:

            last_completed_code = (
                success_codes[-1]
            )

        else:

            last_completed_code = ""

        next_code = ""

        if success_codes:

            try:

                current_pos = codes.index(
                    last_completed_code
                )

                if (
                    current_pos + 1
                    < len(codes)
                ):

                    next_code = (
                        codes[
                            current_pos + 1
                        ]
                    )

            except ValueError:

                pass

        save_progress(
            last_completed_code,
            next_code,
        )

        print()
        print(
            "進捗保存:"
        )

        print(
            f"最後に完了した銘柄 : "
            f"{last_completed_code}"
        )

        if next_code:

            print(
                f"次回開始予定銘柄 : "
                f"{next_code}"
            )

        # ----------------------------------
        # 次へ
        # ----------------------------------

        position += len(batch)

        if position >= len(remaining):

            break

        print()
        print(
            "Yahoo負荷対策:"
        )

        print(
            "20分休憩します..."
        )

        try:

            for wait_seconds in range(
                BATCH_WAIT_SECONDS,
                0,
                -60,
            ):

                minutes = (
                    wait_seconds // 60
                )

                print(
                    f"再開まで約 "
                    f"{minutes} 分..."
                )

                time.sleep(
                    min(
                        60,
                        wait_seconds,
                    )
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
            "20分休憩が完了しました。"
        )

        print(
            "次の50銘柄へ進みます。"
        )

    # ======================================
    # 最終状態
    # ======================================

    existing = get_existing_codes()
    failed = get_failed_codes()

    print()
    print("=" * 60)
    print(" Yahoo信用データ取得終了")
    print("=" * 60)

    print(
        f"対象銘柄数     : {len(codes)}"
    )

    print(
        f"既存CSV        : {len(existing)}"
    )

    print(
        f"ブラックリスト : {len(failed)}"
    )

    progress = load_progress()

    if progress is not None:

        print(
            f"最後に完了した銘柄 : "
            f"{progress['last_completed_code']}"
        )

        print(
            f"次に開始する銘柄 : "
            f"{progress['next_code']}"
        )

        print("=" * 60)


if __name__ == "__main__":
    main()