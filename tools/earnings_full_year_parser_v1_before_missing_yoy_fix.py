import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


YEN = "\u5e74"
MONTH = "\u6708"
TERM = "\u671f"
FORECAST = "\u4e88\u60f3"
FULL = "\u901a"


def normalize(text):
    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    return (
        text
        .replace(",", "")
        .replace("\u25b3", "-")
        .replace("\u25b2", "-")
        .replace("\u2212", "-")
        .replace("\uff0d", "-")
    )


def numbers(text):
    text = normalize(text)

    values = re.findall(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    return [
        float(x)
        for x in values
    ]


def parse_actual_row(line):
    vals = numbers(line)

    # Expected:
    # year, month,
    # sales, sales_yoy,
    # operating, operating_yoy,
    # ordinary, ordinary_yoy,
    # net, net_yoy
    if len(vals) < 10:
        return None

    return {
        "ActualSales": vals[2],
        "ActualSalesYoY": vals[3],
        "ActualOperating": vals[4],
        "ActualOperatingYoY": vals[5],
        "ActualOrdinary": vals[6],
        "ActualOrdinaryYoY": vals[7],
        "ActualNet": vals[8],
        "ActualNetYoY": vals[9],
    }


def parse_forecast_row(line):
    vals = numbers(line)

    # Expected:
    # sales, growth,
    # operating, growth,
    # ordinary, growth,
    # net, growth,
    # EPS
    if len(vals) < 8:
        return None

    return {
        "ForecastSales": vals[0],
        "ForecastSalesGrowth": vals[1],
        "ForecastOperating": vals[2],
        "ForecastOperatingGrowth": vals[3],
        "ForecastOrdinary": vals[4],
        "ForecastOrdinaryGrowth": vals[5],
        "ForecastNet": vals[6],
        "ForecastNetGrowth": vals[7],
    }


def is_full_year_actual_row(line):
    text = normalize(line)

    pattern = (
        r"^20\d{2}"
        + YEN
        + r"\d{1,2}"
        + MONTH
        + TERM
        + r"\s"
    )

    if re.match(
        pattern,
        text,
    ) is None:
        return False

    if FORECAST in text:
        return False

    vals = numbers(text)

    return len(vals) >= 10


def is_forecast_row(line):
    text = normalize(line)

    pattern = (
        r"^"
        + FULL
        + r"\s*"
        + TERM
        + r"\s"
    )

    if re.match(
        pattern,
        text,
    ) is None:
        return False

    vals = numbers(text)

    return len(vals) >= 8


def parse_pdf(pdf_path):
    reader = PdfReader(pdf_path)

    pages = []

    for page in reader.pages[:3]:
        text = page.extract_text() or ""

        lines = [
            x.strip()
            for x in text.splitlines()
            if x.strip()
        ]

        pages.append(lines)

    actual_row = None
    forecast_row = None

    # Search first page for the latest full-year
    # actual performance row.
    for line in pages[0]:
        if is_full_year_actual_row(line):
            actual_row = line
            break

    # Search first 3 pages for next-year
    # full-year company forecast.
    for lines in pages:
        for line in lines:
            if is_forecast_row(line):
                forecast_row = line
                break

        if forecast_row is not None:
            break

    if actual_row is None:
        return {
            "ParseStatus": "ACTUAL_NOT_FOUND",
        }

    if forecast_row is None:
        return {
            "ParseStatus": "FORECAST_NOT_FOUND",
            "ActualRow": actual_row,
        }

    actual = parse_actual_row(
        actual_row
    )

    forecast = parse_forecast_row(
        forecast_row
    )

    if actual is None:
        return {
            "ParseStatus": "ACTUAL_PARSE_FAIL",
            "ActualRow": actual_row,
            "ForecastRow": forecast_row,
        }

    if forecast is None:
        return {
            "ParseStatus": "FORECAST_PARSE_FAIL",
            "ActualRow": actual_row,
            "ForecastRow": forecast_row,
        }

    result = {
        "ParseStatus": "OK",
        "ActualRow": actual_row,
        "ForecastRow": forecast_row,
    }

    result.update(actual)
    result.update(forecast)

    result["MinForecastGrowth4"] = min(
        result["ForecastSalesGrowth"],
        result["ForecastOperatingGrowth"],
        result["ForecastOrdinaryGrowth"],
        result["ForecastNetGrowth"],
    )

    return result


if __name__ == "__main__":
    root = Path(
        "data/analysis/earnings_pdf"
    )

    files = list(
        root.rglob("584A.pdf")
    )

    if not files:
        raise SystemExit(
            "584A PDF NOT FOUND"
        )

    result = parse_pdf(
        files[0]
    )

    print("=" * 80)
    print("FULL YEAR PARSER V1 TEST")
    print("=" * 80)

    for key, value in result.items():
        print(
            f"{key:<28}: {value}"
        )
