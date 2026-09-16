from pathlib import Path
import re

from pypdf import PdfReader


PDF_PATH = Path(
    "data/analysis/3121_20260911_q3.pdf"
)


def normalize_text(text):
    text = text.replace("\u3000", " ")
    text = text.replace("\u25b3", "-")
    text = text.replace("\u2212", "-")
    text = text.replace("\uff0d", "-")
    text = re.sub(r"[ \t]+", " ", text)
    return text


def extract_first_page(path):
    reader = PdfReader(str(path))

    if not reader.pages:
        raise RuntimeError("PDF has no pages")

    text = reader.pages[0].extract_text() or ""

    return normalize_text(text)


def parse_percent(value):
    value = value.strip()

    value = value.replace(
        "\u25b3",
        "-",
    )

    value = value.replace(
        "\u2212",
        "-",
    )

    value = value.replace(
        "%",
        "",
    )

    value = value.replace(
        "\uff05",
        "",
    )

    try:
        return float(value)
    except Exception:
        return None


def extract_performance(text):
    pattern = re.compile(
        r"2026\u5e7410\u6708\u671f"
        r"\u7b2c\uff13\u56db\u534a\u671f"
        r"\s+"
        r"([\d,]+)\s+([\-0-9.]+)"
        r"\s+"
        r"([\d,]+)\s+([\-0-9.]+)"
        r"\s+"
        r"([\d,]+)\s+([\-0-9.]+)"
        r"\s+"
        r"([\d,]+)\s+([\-0-9.]+)"
    )

    match = pattern.search(text)

    if not match:
        return None

    return {
        "sales": int(
            match.group(1).replace(",", "")
        ),
        "sales_yoy": parse_percent(
            match.group(2)
        ),
        "operating_profit": int(
            match.group(3).replace(",", "")
        ),
        "operating_yoy": parse_percent(
            match.group(4)
        ),
        "ordinary_profit": int(
            match.group(5).replace(",", "")
        ),
        "ordinary_yoy": parse_percent(
            match.group(6)
        ),
        "net_profit": int(
            match.group(7).replace(",", "")
        ),
        "net_yoy": parse_percent(
            match.group(8)
        ),
    }


def extract_forecast_revision(text):
    marker = (
        "\u76f4\u8fd1\u306b\u516c\u8868"
        "\u3055\u308c\u3066\u3044\u308b"
        "\u696d\u7e3e\u4e88\u60f3"
        "\u304b\u3089\u306e\u4fee\u6b63"
        "\u306e\u6709\u7121"
    )

    pos = text.find(marker)

    if pos < 0:
        return None

    area = text[pos:pos + 100]

    if "\uff1a \u6709" in area:
        return True

    if "\uff1a \u7121" in area:
        return False

    if ":\u6709" in area:
        return True

    if ":\u7121" in area:
        return False

    return None


def evaluate(result, revision):
    if result is None:
        return "PARSE_ERROR"

    op = result["operating_yoy"]
    ordinary = result["ordinary_yoy"]
    net = result["net_yoy"]

    values = [
        value
        for value in [
            op,
            ordinary,
            net,
        ]
        if value is not None
    ]

    if not values:
        return "UNKNOWN"

    severe_negative = sum(
        value <= -30.0
        for value in values
    )

    positive = sum(
        value >= 10.0
        for value in values
    )

    strong_positive = sum(
        value >= 30.0
        for value in values
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
    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)

    text = extract_first_page(
        PDF_PATH
    )

    result = extract_performance(
        text
    )

    revision = extract_forecast_revision(
        text
    )

    print("=" * 70)
    print("EARNINGS PARSER TEST")
    print("=" * 70)

    print("PDF :", PDF_PATH)
    print()

    if result is None:
        print("Performance : PARSE ERROR")
        return

    print(
        "Sales YoY      :",
        result["sales_yoy"],
        "%",
    )

    print(
        "Operating YoY  :",
        result["operating_yoy"],
        "%",
    )

    print(
        "Ordinary YoY   :",
        result["ordinary_yoy"],
        "%",
    )

    print(
        "Net Profit YoY :",
        result["net_yoy"],
        "%",
    )

    print()

    if revision is True:
        revision_text = "YES"
    elif revision is False:
        revision_text = "NO"
    else:
        revision_text = "UNKNOWN"

    print(
        "Forecast revision :",
        revision_text,
    )

    print(
        "Earnings rating   :",
        evaluate(
            result,
            revision,
        ),
    )


if __name__ == "__main__":
    main()
