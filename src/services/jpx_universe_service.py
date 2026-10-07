from datetime import date
from pathlib import Path

import pandas as pd


DELISTED_URL = "https://www.jpx.co.jp/listing/stocks/delisted/index.html"
CACHE_PATH = Path("data/cache/jpx_delisted_stocks.csv")


def normalize_code(value):
    """Normalize JPX stock codes without converting alphanumeric codes to int."""
    if pd.isna(value):
        return ""

    code = str(value).strip()

    if code.endswith(".0"):
        code = code[:-2]

    return code.upper()


def refresh_delisted_cache():
    """Download the current JPX delisted-stock table and safely replace cache."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    tables = pd.read_html(DELISTED_URL)

    if not tables:
        raise RuntimeError("JPX delisted table was not found.")

    df = tables[0].copy()

    required = {
        "上場廃止日",
        "銘柄名",
        "コード",
        "市場区分",
        "上場廃止理由",
    }

    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            f"JPX delisted table columns are invalid: {sorted(missing)}"
        )

    df["コード"] = df["コード"].map(normalize_code)
    df["上場廃止日"] = pd.to_datetime(
        df["上場廃止日"],
        errors="coerce",
    )

    df = df[
        (df["コード"] != "")
        & df["上場廃止日"].notna()
    ].copy()

    if df.empty:
        raise RuntimeError("JPX delisted table contains no valid rows.")

    df["上場廃止日"] = df["上場廃止日"].dt.strftime("%Y-%m-%d")

    temp_path = CACHE_PATH.with_suffix(".tmp.csv")

    try:
        df.to_csv(
            temp_path,
            index=False,
            encoding="utf-8-sig",
        )

        check = pd.read_csv(
            temp_path,
            dtype={"コード": str},
        )

        if check.empty:
            raise RuntimeError("Temporary JPX delisted cache is empty.")

        if not required.issubset(check.columns):
            raise RuntimeError(
                "Temporary JPX delisted cache failed validation."
            )

        temp_path.replace(CACHE_PATH)

    finally:
        if temp_path.exists():
            temp_path.unlink()

    return df


def load_delisted_cache():
    """Load the last valid JPX delisted-stock cache."""
    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"JPX delisted cache not found: {CACHE_PATH}"
        )

    df = pd.read_csv(
        CACHE_PATH,
        dtype={"コード": str},
    )

    required = {
        "上場廃止日",
        "銘柄名",
        "コード",
        "市場区分",
        "上場廃止理由",
    }

    if df.empty or not required.issubset(df.columns):
        raise RuntimeError("JPX delisted cache is invalid.")

    df["コード"] = df["コード"].map(normalize_code)
    df["上場廃止日"] = pd.to_datetime(
        df["上場廃止日"],
        errors="coerce",
    )

    df = df[
        (df["コード"] != "")
        & df["上場廃止日"].notna()
    ].copy()

    if df.empty:
        raise RuntimeError("JPX delisted cache has no valid rows.")

    return df


def refresh_or_load_delisted():
    """
    Prefer fresh JPX data.
    If refresh fails, use the last valid cache.
    """
    try:
        df = refresh_delisted_cache()
        print(f"JPX上場廃止一覧更新 : OK ({len(df)}件)")
        return df

    except Exception as exc:
        print(f"WARNING : JPX上場廃止一覧更新失敗 : {exc}")
        print("前回の正常なJPX上場廃止キャッシュを使用します。")
        return load_delisted_cache()


def filter_delisted_stocks(stocks, as_of_date=None):
    """
    Remove stocks whose JPX delisting date is on or before as_of_date.
    This function is intended for the current production universe only.
    """
    if as_of_date is None:
        as_of_date = date.today()

    target_date = pd.Timestamp(as_of_date).normalize()

    delisted = refresh_or_load_delisted()

    # refresh path returns CSV-formatted date strings,
    # while cache path may already contain parsed timestamps.
    # Normalize both paths before date comparison.
    delisted["上場廃止日"] = pd.to_datetime(
        delisted["上場廃止日"],
        errors="coerce",
    )

    delisted = delisted[
        delisted["上場廃止日"].notna()
    ].copy()

    blocked = delisted[
        delisted["上場廃止日"] <= target_date
    ].copy()

    blocked_codes = set(
        blocked["コード"].map(normalize_code)
    )

    result = stocks.copy()

    result["_JPX_CODE"] = result["コード"].map(normalize_code)

    removed = result[
        result["_JPX_CODE"].isin(blocked_codes)
    ].copy()

    result = result[
        ~result["_JPX_CODE"].isin(blocked_codes)
    ].copy()

    result = result.drop(columns=["_JPX_CODE"])
    result = result.reset_index(drop=True)

    print(f"JPX上場廃止除外数 : {len(removed)}")

    if not removed.empty:
        name_map = dict(
            zip(
                blocked["コード"],
                blocked["銘柄名"],
            )
        )

        date_map = dict(
            zip(
                blocked["コード"],
                blocked["上場廃止日"],
            )
        )

        for code in removed["_JPX_CODE"]:
            delist_date = date_map.get(code)
            delist_text = (
                delist_date.strftime("%Y-%m-%d")
                if pd.notna(delist_date)
                else "UNKNOWN"
            )

            print(
                f"  除外 : {code} "
                f"{name_map.get(code, '')} / "
                f"{delist_text}"
            )

    return result
