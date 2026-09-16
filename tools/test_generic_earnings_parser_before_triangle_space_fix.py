from pathlib import Path
import re
import sys

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

sys.path.insert(
    0,
    str(SRC),
)

from screener.loader import load_stock_list


DATE = "20260911"

API_URL = (
    "https://webapi.yanoshin.jp/"
    f"webapi/tdnet/list/{DATE}.json"
)

TARGET_CODES = {
    "3121",
    "3399",
    "3539",
    "5572",
    "9743",
}


def normalize_code(value):
    value = str(value).strip()

    if (
        len(value) == 5
        and value.endswith("0")
    ):
        return value[:-1]

    return value


def normalize_text(text):
    replacements = {
        "\u3000": " ",
        "\u25b3": "-",
        "\u25b2": "",
        "\u2212": "-",
        "\uff0d": "-",
        "\uff05": "%",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    return text


def to_float(value):
    if value is None:
        return None

    value = str(value).strip()

    value = value.replace(
        "%",
        "",
    )

    value = value.replace(
        ",",
        "",
    )

    try:
        return float(value)
    except Exception:
        return None


def download_pdf(url, code):
    out_dir = Path(
        "data/analysis/"
        "earnings_pdf_test"
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = out_dir / (
        f"{DATE}_{code}.pdf"
    )

    r = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent":
                "JapanStockScreener/1.0"
        },
    )

    r.raise_for_status()

    path.write_bytes(
        r.content
    )

    return path


def extract_first_page(path):
    reader = PdfReader(
        str(path)
    )

    if not reader.pages:
        return ""

    text = (
        reader.pages[0]
        .extract_text()
        or ""
    )

    return normalize_text(
        text
    )


def find_performance_row(text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    candidates = []

    for line in lines:
        #
        # Skip section headings and
        # explanatory date-range lines.
        #
        if (
            "\u9023\u7d50\u696d\u7e3e"
            in line
            or "\u696d\u7e3e\uff08"
            in line
            or "\u696d\u7e3e("
            in line
            or "\uff5e"
            in line
        ):
            continue

        #
        # A performance data row normally
        # starts with a fiscal period.
        #
        if not re.search(
            r"\d{4}\u5e74.*\u671f",
            line,
        ):
            continue

        numbers = re.findall(
            r"-?\d[\d,]*"
            r"(?:\.\d+)?",
            line,
        )

        #
        # Need at least:
        #
        # sales / yoy
        # operating / yoy
        # ordinary / yoy
        # net / yoy
        #
        if len(numbers) < 8:
            continue

        if (
            "\u914d\u5f53"
            in line
        ):
            continue

        tail = numbers[-8:]

        try:
            yoy_values = [
                float(
                    tail[1].replace(
                        ",",
                        "",
                    )
                ),
                float(
                    tail[3].replace(
                        ",",
                        "",
                    )
                ),
                float(
                    tail[5].replace(
                        ",",
                        "",
                    )
                ),
                float(
                    tail[7].replace(
                        ",",
                        "",
                    )
                ),
            ]
        except Exception:
            continue

        #
        # Reject obvious date/year values
        # accidentally parsed as YoY.
        #
        if any(
            abs(value) >= 1000
            for value in yoy_values
        ):
            continue

        candidates.append(
            (
                line,
                numbers,
            )
        )

    if not candidates:
        return None

    return candidates[0]


def extract_yoy(text):
    found = find_performance_row(
        text
    )

    if found is None:
        return None

    line, nums = found

    #
    # The row commonly contains:
    #
    # value, yoy
    # value, yoy
    # value, yoy
    # value, yoy
    #
    # The period year/month numbers
    # may appear at the front, so use
    # the last 8 numeric fields.
    #
    nums = nums[-8:]

    return {
        "line": line,
        "sales_yoy": to_float(
            nums[1]
        ),
        "operating_yoy": to_float(
            nums[3]
        ),
        "ordinary_yoy": to_float(
            nums[5]
        ),
        "net_yoy": to_float(
            nums[7]
        ),
    }


def extract_forecast_revision(
    text,
):
    key = (
        "\u696d\u7e3e\u4e88\u60f3"
        "\u304b\u3089\u306e\u4fee\u6b63"
        "\u306e\u6709\u7121"
    )

    pos = text.find(
        key
    )

    if pos < 0:
        return None

    area = text[
        pos:
        pos + 150
    ]

    if (
        "\uff1a \u6709"
        in area
        or ":\u6709"
        in area
    ):
        return True

    if (
        "\uff1a \u7121"
        in area
        or ":\u7121"
        in area
    ):
        return False

    return None


def evaluate(result):
    if result is None:
        return "PARSE_ERROR"

    values = [
        result["operating_yoy"],
        result["ordinary_yoy"],
        result["net_yoy"],
    ]

    values = [
        value
        for value in values
        if value is not None
    ]

    if len(values) < 2:
        return "UNKNOWN"

    severe_negative = sum(
        x <= -30.0
        for x in values
    )

    positive = sum(
        x >= 10.0
        for x in values
    )

    strong_positive = sum(
        x >= 30.0
        for x in values
    )

    if severe_negative >= 2:
        return "BAD"

    if (
        strong_positive >= 2
        and min(values) >= 0
    ):
        return "STRONG_GOOD"

    if (
        positive >= 2
        and min(values) > -10
    ):
        return "GOOD"

    return "MIXED"


def main():
    stocks = load_stock_list()

    universe = set(
        stocks["\u30b3\u30fc\u30c9"]
        .astype(str)
        .str.strip()
    )

    r = requests.get(
        API_URL,
        timeout=30,
        headers={
            "User-Agent":
                "JapanStockScreener/1.0"
        },
    )

    r.raise_for_status()

    data = r.json()

    disclosures = {}

    for item in data.get(
        "items",
        [],
    ):
        tdnet = item.get(
            "Tdnet",
            item,
        )

        code = normalize_code(
            tdnet.get(
                "company_code",
                "",
            )
        )

        if code not in universe:
            continue

        if code not in TARGET_CODES:
            continue

        title = str(
            tdnet.get(
                "title",
                "",
            )
        ).strip()

        if (
            "\u6c7a\u7b97\u77ed\u4fe1"
            not in title
        ):
            continue

        if (
            "\u8a02\u6b63"
            in title
        ):
            continue

        if (
            "IFRS"
            in title.upper()
            or "\uff29\uff26\uff32\uff33"
            in title
        ):
            continue

        disclosures[
            code
        ] = {
            "name": str(
                tdnet.get(
                    "company_name",
                    "",
                )
            ).strip(),
            "title": title,
            "url": str(
                tdnet.get(
                    "document_url",
                    "",
                )
            ).strip(),
        }

    print(
        "=" * 82
    )
    print(
        "GENERIC EARNINGS PARSER TEST"
    )
    print(
        "=" * 82
    )

    for code in sorted(
        TARGET_CODES
    ):
        info = disclosures.get(
            code
        )

        if info is None:
            print()
            print(
                code,
                ": NO DISCLOSURE",
            )
            continue

        print()
        print(
            "-" * 82
        )

        print(
            code,
            info["name"],
        )

        print(
            info["title"]
        )

        try:
            path = download_pdf(
                info["url"],
                code,
            )

            text = extract_first_page(
                path
            )

            result = extract_yoy(
                text
            )

            revision = (
                extract_forecast_revision(
                    text
                )
            )

            if result is None:
                print(
                    "PARSE ERROR"
                )
                continue

            print(
                "Sales YoY     :",
                result[
                    "sales_yoy"
                ],
            )

            print(
                "Operating YoY :",
                result[
                    "operating_yoy"
                ],
            )

            print(
                "Ordinary YoY  :",
                result[
                    "ordinary_yoy"
                ],
            )

            print(
                "Net YoY       :",
                result[
                    "net_yoy"
                ],
            )

            print(
                "Revision      :",
                revision,
            )

            print(
                "Rating        :",
                evaluate(
                    result
                ),
            )

            print(
                "Source row    :",
                result["line"][:250],
            )

        except Exception as e:
            print(
                "ERROR :",
                repr(e),
            )


if __name__ == "__main__":
    main()
