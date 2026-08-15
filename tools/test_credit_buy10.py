import sys
import time
from pathlib import Path

import pandas as pd


# ============================================================
# プロジェクトルート
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT_DIR),
)


from src.services.yahoo_credit_service import (
    get_credit_history,
    save_credit_history,
)


# ============================================================
# 設定
# ============================================================

RESULT_FILE = Path(
    "results/2026-08-15_stock_result.csv"
)

CREDIT_DIR = Path(
    "data/yahoo_credit"
)

OUTPUT_FILE = Path(
    "results/2026-08-15_credit_buy10_test.csv"
)

TEST_COUNT = 10

THRESHOLD = -5.0


# ============================================================
# 買い候補を読み込む
# ============================================================

def load_buy_candidates():

    df = pd.read_csv(
        RESULT_FILE,
        dtype={"コード": str},
    )

    df["コード"] = (
        df["コード"]
        .astype(str)
        .str.strip()
    )

    candidates = df[
        df["総合判定"] == "買い候補"
    ].copy()

    candidates = (
        candidates
        .drop_duplicates(
            subset=["コード"]
        )
        .reset_index(drop=True)
    )

    return candidates


# ============================================================
# 既存信用CSV
# ============================================================

def load_credit_csv(code):

    path = CREDIT_DIR / f"{code}.csv"

    if not path.exists():
        return None

    try:

        df = pd.read_csv(
            path,
            encoding="utf-8-sig",
        )

    except Exception as e:

        print(
            f"[{code}] CSV読込エラー: {e}"
        )

        return None

    if df.empty:
        return None

    if "日付" not in df.columns:
        return None

    df["日付"] = pd.to_datetime(
        df["日付"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["日付"]
    )

    if df.empty:
        return None

    df = (
        df.sort_values(
            "日付",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    return df


# ============================================================
# 最新データ
# ============================================================

def get_latest(df):

    if df is None or df.empty:
        return None

    df = df.copy()

    df["日付"] = pd.to_datetime(
        df["日付"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["日付"]
    )

    if df.empty:
        return None

    df = (
        df.sort_values(
            "日付",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    return df.iloc[0]


# ============================================================
# メイン
# ============================================================

def main():

    print()
    print("=" * 70)
    print("未取得買い候補 10銘柄限定テスト")
    print("=" * 70)

    # --------------------------------------------------------
    # 買い候補
    # --------------------------------------------------------

    candidates = load_buy_candidates()

    print()
    print(
        f"買い候補銘柄数 : {len(candidates)}"
    )

    # --------------------------------------------------------
    # 既存CSVを除外
    # --------------------------------------------------------

    missing = []

    for _, row in candidates.iterrows():

        code = str(
            row["コード"]
        ).strip()

        path = CREDIT_DIR / f"{code}.csv"

        if not path.exists():

            missing.append(
                row
            )

    missing_df = pd.DataFrame(
        missing
    )

    print(
        f"信用CSVなし      : {len(missing_df)}"
    )

    # --------------------------------------------------------
    # 未取得先頭10銘柄
    # --------------------------------------------------------

    test_candidates = (
        missing_df
        .head(TEST_COUNT)
        .reset_index(drop=True)
    )

    print()
    print("=" * 70)
    print("今回の検証対象")
    print("=" * 70)

    print(
        test_candidates[
            [
                "コード",
                "銘柄名",
                "強気度",
            ]
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Yahoo取得
    # --------------------------------------------------------

    CREDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = []

    print()
    print("=" * 70)
    print("Yahoo信用データ取得")
    print("=" * 70)

    for index, row in test_candidates.iterrows():

        code = str(
            row["コード"]
        ).strip()

        name = row["銘柄名"]
        score = row["強気度"]

        print()
        print(
            f"[{index + 1}/{len(test_candidates)}] "
            f"{code} : {name}"
        )

        start = time.perf_counter()

        try:

            df = get_credit_history(
                code
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            if df is None or df.empty:

                print(
                    f"    取得失敗 "
                    f"({elapsed:.2f}s)"
                )

                continue

            save_credit_history(
                df,
                code,
            )

            latest = get_latest(
                df
            )

            if latest is None:

                print(
                    "    最新データ取得失敗"
                )

                continue

            buy = pd.to_numeric(
                latest.get("買残"),
                errors="coerce",
            )

            buy_change = pd.to_numeric(
                latest.get("買残増減"),
                errors="coerce",
            )

            if (
                pd.notna(buy)
                and buy != 0
                and pd.notna(buy_change)
            ):

                buy_rate = (
                    buy_change
                    / buy
                    * 100
                )

            else:

                buy_rate = None

            threshold_ok = (
                pd.notna(buy_rate)
                and buy_rate <= THRESHOLD
            )

            print(
                f"    成功 "
                f"{len(df)}行 "
                f"({elapsed:.2f}s)"
            )

            print(
                f"    買残        : {buy}"
            )

            print(
                f"    買残増減    : {buy_change}"
            )

            if pd.notna(buy_rate):

                print(
                    f"    買残前週比  : "
                    f"{buy_rate:.2f}%"
                )

            else:

                print(
                    "    買残前週比  : 判定不可"
                )

            print(
                f"    -5%以下    : "
                f"{'○' if threshold_ok else '×'}"
            )

            rows.append(
                {
                    "コード": code,
                    "銘柄名": name,
                    "強気度": score,
                    "信用日付": (
                        latest["日付"]
                        .strftime("%Y-%m-%d")
                    ),
                    "買残": buy,
                    "買残増減": buy_change,
                    "買残前週比": buy_rate,
                    "買残前週比-5%以下": (
                        "○"
                        if threshold_ok
                        else "×"
                    ),
                }
            )

        except Exception as e:

            elapsed = (
                time.perf_counter()
                - start
            )

            print(
                f"    ERROR: {e}"
            )

            print(
                f"    経過時間: "
                f"{elapsed:.2f}s"
            )

    # --------------------------------------------------------
    # 結果
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        rows
    )

    print()
    print("=" * 70)
    print("検証結果")
    print("=" * 70)

    print(
        f"取得対象        : "
        f"{len(test_candidates)} 銘柄"
    )

    print(
        f"取得成功        : "
        f"{len(result_df)} 銘柄"
    )

    if not result_df.empty:

        ok_count = (
            result_df[
                "買残前週比-5%以下"
            ] == "○"
        ).sum()

        print(
            f"-5%以下         : "
            f"{ok_count} 銘柄"
        )

        print()

        print(
            result_df[
                [
                    "コード",
                    "銘柄名",
                    "強気度",
                    "買残",
                    "買残増減",
                    "買残前週比",
                    "買残前週比-5%以下",
                ]
            ]
            .sort_values(
                "買残前週比"
            )
            .to_string(
                index=False
            )
        )

    else:

        print(
            "取得成功銘柄なし"
        )

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 70)
    print(
        f"結果保存 : {OUTPUT_FILE}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()