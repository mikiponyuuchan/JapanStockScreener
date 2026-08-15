import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


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
    "results/2026-08-15_credit_existing15_test.csv"
)


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
# 既存信用CSVを読み込む
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

    required_columns = [
        "日付",
        "売残",
        "買残",
        "売残増減",
        "買残増減",
        "信用倍率",
    ]

    if not all(
        column in df.columns
        for column in required_columns
    ):
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

    return df.iloc[0]


# ============================================================
# 信用条件判定
# ============================================================

def judge_credit(latest):

    if latest is None:

        return {
            "信用倍率条件": "未判定",
            "売残増加条件": "未判定",
            "買残減少条件": "未判定",
            "信用3条件達成数": 0,
        }

    ratio = pd.to_numeric(
        latest["信用倍率"],
        errors="coerce",
    )

    sell_change = pd.to_numeric(
        latest["売残増減"],
        errors="coerce",
    )

    buy_change = pd.to_numeric(
        latest["買残増減"],
        errors="coerce",
    )

    # 条件① 信用倍率 < 1
    ratio_ok = (
        pd.notna(ratio)
        and ratio < 1
    )

    # 条件② 売残増加
    sell_ok = (
        pd.notna(sell_change)
        and sell_change > 0
    )

    # 条件③ 買残減少
    buy_ok = (
        pd.notna(buy_change)
        and buy_change < 0
    )

    count = sum(
        [
            ratio_ok,
            sell_ok,
            buy_ok,
        ]
    )

    return {
        "信用倍率条件": (
            "○" if ratio_ok else "×"
        ),
        "売残増加条件": (
            "○" if sell_ok else "×"
        ),
        "買残減少条件": (
            "○" if buy_ok else "×"
        ),
        "信用3条件達成数": count,
    }


# ============================================================
# メイン
# ============================================================

def main():

    print()
    print("=" * 70)
    print("既存信用CSV 15銘柄限定テスト")
    print("=" * 70)

    # --------------------------------------------------------
    # 買い候補122銘柄
    # --------------------------------------------------------

    candidates = load_buy_candidates()

    print()
    print(
        f"買い候補銘柄数 : {len(candidates)}"
    )

    # --------------------------------------------------------
    # 信用CSVが存在する銘柄だけに限定
    # --------------------------------------------------------

    credit_files = {
        path.stem.strip()
        for path in CREDIT_DIR.glob("*.csv")
    }

    candidates["コード"] = (
        candidates["コード"]
        .astype(str)
        .str.strip()
    )

    existing = candidates[
        candidates["コード"].isin(
            credit_files
        )
    ].copy()

    existing = (
        existing
        .drop_duplicates(
            subset=["コード"]
        )
        .reset_index(drop=True)
    )

    print(
        f"既存信用CSVあり : {len(existing)} 銘柄"
    )

    # --------------------------------------------------------
    # 念のため一覧表示
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("検証対象銘柄")
    print("=" * 70)

    print(
        existing[
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
    # 信用データ読み込み・判定
    # --------------------------------------------------------

    rows = []

    for _, candidate in existing.iterrows():

        code = str(
            candidate["コード"]
        ).strip()

        credit_df = load_credit_csv(
            code
        )

        latest = get_latest(
            credit_df
        )

        result = judge_credit(
            latest
        )

        row = {
            "コード": code,
            "銘柄名": candidate["銘柄名"],
            "強気度": candidate["強気度"],
            "信用日付": (
                latest["日付"].strftime(
                    "%Y-%m-%d"
                )
                if latest is not None
                else ""
            ),
            "売残": (
                latest["売残"]
                if latest is not None
                else None
            ),
            "買残": (
                latest["買残"]
                if latest is not None
                else None
            ),
            "売残増減": (
                latest["売残増減"]
                if latest is not None
                else None
            ),
            "買残増減": (
                latest["買残増減"]
                if latest is not None
                else None
            ),
            "信用倍率": (
                latest["信用倍率"]
                if latest is not None
                else None
            ),
        }

        row.update(result)

        rows.append(row)

    result_df = pd.DataFrame(
        rows
    )

    # --------------------------------------------------------
    # 件数
    # --------------------------------------------------------

    count_3 = (
        result_df["信用3条件達成数"] == 3
    ).sum()

    count_2 = (
        result_df["信用3条件達成数"] == 2
    ).sum()

    count_1 = (
        result_df["信用3条件達成数"] == 1
    ).sum()

    count_0 = (
        result_df["信用3条件達成数"] == 0
    ).sum()

    ratio_count = (
        result_df["信用倍率条件"] == "○"
    ).sum()

    sell_count = (
        result_df["売残増加条件"] == "○"
    ).sum()

    buy_count = (
        result_df["買残減少条件"] == "○"
    ).sum()

    # --------------------------------------------------------
    # 結果表示
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("信用3条件の充足状況")
    print("=" * 70)

    print(
        f"3条件達成 : {count_3:4d} 銘柄"
    )

    print(
        f"2条件達成 : {count_2:4d} 銘柄"
    )

    print(
        f"1条件達成 : {count_1:4d} 銘柄"
    )

    print(
        f"0条件達成 : {count_0:4d} 銘柄"
    )

    # --------------------------------------------------------
    # 各条件
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("各信用条件の達成数")
    print("=" * 70)

    print(
        f"信用倍率 < 1 : {ratio_count:4d} 銘柄"
    )

    print(
        f"売残増加     : {sell_count:4d} 銘柄"
    )

    print(
        f"買残減少     : {buy_count:4d} 銘柄"
    )

    # --------------------------------------------------------
    # 3条件達成
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("3条件すべて達成")
    print("=" * 70)

    three = result_df[
        result_df["信用3条件達成数"] == 3
    ]

    if three.empty:

        print("該当銘柄なし")

    else:

        print(
            three[
                [
                    "コード",
                    "銘柄名",
                    "強気度",
                    "信用倍率",
                    "売残増減",
                    "買残増減",
                ]
            ].to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # 2条件達成
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("2条件達成")
    print("=" * 70)

    two = result_df[
        result_df["信用3条件達成数"] == 2
    ]

    if two.empty:

        print("該当銘柄なし")

    else:

        print(
            two[
                [
                    "コード",
                    "銘柄名",
                    "強気度",
                    "信用倍率",
                    "売残増減",
                    "買残減少条件",
                ]
            ].to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # 全15銘柄の詳細
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("全対象銘柄の詳細")
    print("=" * 70)

    print(
        result_df[
            [
                "コード",
                "銘柄名",
                "強気度",
                "信用倍率",
                "売残増減",
                "買残増減",
                "信用倍率条件",
                "売残増加条件",
                "買残減少条件",
                "信用3条件達成数",
            ]
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # CSV保存
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