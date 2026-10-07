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



NEW_LISTINGS_URL = "https://www.jpx.co.jp/listing/stocks/new/index.html"
NEW_LISTINGS_CACHE_PATH = Path("data/cache/jpx_new_listings.csv")

VALID_MARKETS = {
    "プライム": "プライム（内国株式）",
    "スタンダード": "スタンダード（内国株式）",
    "グロース": "グロース（内国株式）",
}


def parse_new_listing_table(raw):
    """
    Convert the JPX two-row-per-company new-listing table
    into one row per stock.
    """
    if raw is None or raw.empty:
        raise RuntimeError("JPX new-listing table is empty.")

    if raw.shape[1] < 3:
        raise RuntimeError("JPX new-listing table has too few columns.")

    work = raw.iloc[:, [0, 1, 2]].copy()
    work.columns = ["上場日", "銘柄名", "コード市場"]

    date_text = (
        work["上場日"]
        .astype(str)
        .str.extract(r"(\d{4}/\d{2}/\d{2})")[0]
    )

    work["上場日"] = pd.to_datetime(
        date_text,
        errors="coerce",
    )

    rows = []
    pending = None

    for _, row in work.iterrows():
        value = str(row["コード市場"]).strip()
        listing_date = row["上場日"]
        name = str(row["銘柄名"]).strip()

        # JPX page includes display-only annotations in the company-name cell.
        name = name.replace("代表者インタビュー", "").strip()
        name = name.rstrip("*").strip()

        if not value or value.lower() == "nan":
            continue

        if value in VALID_MARKETS:
            if pending is None:
                continue

            if (
                pending["上場日"] == listing_date
                and pending["銘柄名"] == name
            ):
                pending["市場区分"] = value
                rows.append(pending)

            pending = None
            continue

        code = normalize_code(value)

        if not code:
            pending = None
            continue

        pending = {
            "上場日": listing_date,
            "銘柄名": name,
            "コード": code,
        }

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "No valid JPX new listings could be parsed."
        )

    df = df[
        df["上場日"].notna()
        & df["市場区分"].isin(VALID_MARKETS)
        & (df["コード"] != "")
    ].copy()

    if df.empty:
        raise RuntimeError(
            "JPX new listings contain no valid domestic stocks."
        )

    df = df.drop_duplicates(
        subset=["コード", "上場日"],
        keep="last",
    )

    df = df.sort_values(
        ["上場日", "コード"]
    ).reset_index(drop=True)

    return df


def refresh_new_listings_cache():
    """Download and safely cache the JPX new-listing table."""
    NEW_LISTINGS_CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tables = pd.read_html(NEW_LISTINGS_URL)

    if not tables:
        raise RuntimeError("JPX new-listing table was not found.")

    df = parse_new_listing_table(tables[0])

    save_df = df.copy()
    save_df["上場日"] = save_df["上場日"].dt.strftime("%Y-%m-%d")

    temp_path = NEW_LISTINGS_CACHE_PATH.with_suffix(".tmp.csv")

    try:
        save_df.to_csv(
            temp_path,
            index=False,
            encoding="utf-8-sig",
        )

        check = pd.read_csv(
            temp_path,
            dtype={"コード": str},
        )

        required = {
            "上場日",
            "銘柄名",
            "コード",
            "市場区分",
        }

        if check.empty or not required.issubset(check.columns):
            raise RuntimeError(
                "Temporary JPX new-listing cache failed validation."
            )

        temp_path.replace(NEW_LISTINGS_CACHE_PATH)

    finally:
        if temp_path.exists():
            temp_path.unlink()

    return df


def load_new_listings_cache():
    """Load the last valid JPX new-listing cache."""
    if not NEW_LISTINGS_CACHE_PATH.exists():
        raise FileNotFoundError(
            f"JPX new-listing cache not found: "
            f"{NEW_LISTINGS_CACHE_PATH}"
        )

    df = pd.read_csv(
        NEW_LISTINGS_CACHE_PATH,
        dtype={"コード": str},
    )

    required = {
        "上場日",
        "銘柄名",
        "コード",
        "市場区分",
    }

    if df.empty or not required.issubset(df.columns):
        raise RuntimeError("JPX new-listing cache is invalid.")

    df["コード"] = df["コード"].map(normalize_code)
    df["上場日"] = pd.to_datetime(
        df["上場日"],
        errors="coerce",
    )

    df = df[
        df["上場日"].notna()
        & (df["コード"] != "")
        & df["市場区分"].isin(VALID_MARKETS)
    ].copy()

    if df.empty:
        raise RuntimeError(
            "JPX new-listing cache has no valid rows."
        )

    return df


def refresh_or_load_new_listings():
    """
    Prefer fresh JPX new-listing data.
    If refresh fails, use the last valid cache.
    """
    try:
        df = refresh_new_listings_cache()
        print(f"JPX新規上場一覧更新 : OK ({len(df)}件)")
        return df

    except Exception as exc:
        print(f"WARNING : JPX新規上場一覧更新失敗 : {exc}")
        print("前回の正常なJPX新規上場キャッシュを使用します。")
        return load_new_listings_cache()


def add_newly_listed_stocks(stocks, as_of_date=None):
    """
    Add JPX domestic stocks already listed by as_of_date
    when they are missing from the base stocks.csv universe.
    """
    if as_of_date is None:
        as_of_date = date.today()

    target_date = pd.Timestamp(as_of_date).normalize()

    listings = refresh_or_load_new_listings()

    listings["上場日"] = pd.to_datetime(
        listings["上場日"],
        errors="coerce",
    )

    listings = listings[
        listings["上場日"].notna()
        & (listings["上場日"] <= target_date)
        & listings["市場区分"].isin(VALID_MARKETS)
    ].copy()

    result = stocks.copy()
    result["_JPX_CODE"] = result["コード"].map(normalize_code)

    existing_codes = set(result["_JPX_CODE"])

    additions = listings[
        ~listings["コード"].isin(existing_codes)
    ].copy()

    new_rows = []

    for _, row in additions.iterrows():
        item = {column: pd.NA for column in result.columns}

        item["コード"] = row["コード"]
        item["銘柄名"] = row["銘柄名"]
        item["市場・商品区分"] = VALID_MARKETS[row["市場区分"]]
        item["_JPX_CODE"] = row["コード"]

        new_rows.append(item)

    if new_rows:
        result = pd.concat(
            [
                result,
                pd.DataFrame(new_rows),
            ],
            ignore_index=True,
        )

    print(f"JPX新規上場追加数 : {len(new_rows)}")

    for _, row in additions.iterrows():
        print(
            f"  追加 : {row['コード']} "
            f"{row['銘柄名']} / "
            f"{row['上場日'].strftime('%Y-%m-%d')} / "
            f"{row['市場区分']}"
        )

    result = result.drop(columns=["_JPX_CODE"])
    result = result.reset_index(drop=True)

    return result


def build_current_stock_universe(stocks, as_of_date=None):
    """
    Build the current production universe:
      1. add newly listed domestic stocks
      2. remove stocks already delisted
    """
    stocks = add_newly_listed_stocks(
        stocks,
        as_of_date=as_of_date,
    )

    stocks = filter_delisted_stocks(
        stocks,
        as_of_date=as_of_date,
    )

    print(f"JPX現在対象銘柄数 : {len(stocks)}")

    return stocks

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
