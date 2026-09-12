import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


YEAR = "\u5e74"
MONTH = "\u6708"
TERM = "\u671f"
FORECAST = "\u4e88\u60f3"
FULL = "\u901a"
QUARTER = "\u56db\u534a\u671f"


def normalize_basic(text):
    # Preserve missing-value dashes before NFKC.
    text = text.replace("\u2015", " NA ")
    text = text.replace("\uff0d", " NA ")
    text = text.replace("\u2014", " NA ")
    text = text.replace("\u2013", " NA ")

    # Triangle means a negative number, not missing.
    text = re.sub(
        r"[\u25b3\u25b2]\s*(?=\d)",
        "-",
        text,
    )

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    text = text.replace(",", "")

    return text


def cells(text):
    text = normalize_basic(text)

    values = re.findall(
        r"NA|-?\d+(?:\.\d+)?",
        text,
    )

    out = []

    for value in values:
        if value == "NA":
            out.append(None)
        else:
            out.append(float(value))

    return out


def strip_actual_label(line):
    text = normalize_basic(line)

    pattern = (
        r"^20\d{2}"
        + YEAR
        + r"\d{1,2}"
        + MONTH
        + TERM
        + r"\s*"
    )

    return re.sub(
        pattern,
        "",
        text,
        count=1,
    )


def strip_forecast_label(line):
    text = normalize_basic(line)

    pattern = (
        r"^"
        + FULL
        + r"\s*"
        + TERM
        + r"\s*"
    )

    return re.sub(
        pattern,
        "",
        text,
        count=1,
    )


def is_full_year_actual_row(line):
    text = normalize_basic(line)

    pattern = (
        r"^20\d{2}"
        + YEAR
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

    body = strip_actual_label(
        line
    )

    vals = cells(
        body
    )

    # sales/yoy, operating/yoy,
    # ordinary/yoy, net/yoy
    return len(vals) >= 8


def is_forecast_row(line):
    text = normalize_basic(line)

    pattern = (
        r"^"
        + FULL
        + r"\s*"
        + TERM
        + r"\s"
    )

    return re.match(
        pattern,
        text,
    ) is not None


def parse_actual_row(line):
    vals = cells(
        strip_actual_label(line)
    )

    if len(vals) < 8:
        return None

    return {
        "ActualSales": vals[0],
        "ActualSalesYoY": vals[1],
        "ActualOperating": vals[2],
        "ActualOperatingYoY": vals[3],
        "ActualOrdinary": vals[4],
        "ActualOrdinaryYoY": vals[5],
        "ActualNet": vals[6],
        "ActualNetYoY": vals[7],
    }


def parse_forecast_row(line):
    vals = cells(
        strip_forecast_label(line)
    )

    # Standard table:
    # sales/growth,
    # operating/growth,
    # ordinary/growth,
    # net/growth,
    # EPS
    #
    # At least 8 cells are required.
    # Do not guess missing operating-profit columns.
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


def is_irregular_period(pages):
    text = "\n".join(
        line
        for page in pages[:2]
        for line in page
    )

    # Examples such as "5th quarter" caused by
    # fiscal-year changes must not be treated
    # as ordinary full-year earnings.
    pattern = (
        r"\u7b2c[4-9\uff14-\uff19]"
        + QUARTER
    )

    return re.search(
        pattern,
        text,
    ) is not None


def parse_pdf(pdf_path):
    reader = PdfReader(
        pdf_path
    )

    pages = []

    for page in reader.pages[:3]:
        text = page.extract_text() or ""

        page_lines = [
            x.strip()
            for x in text.splitlines()
            if x.strip()
        ]

        pages.append(
            page_lines
        )

    if is_irregular_period(
        pages
    ):
        return {
            "ParseStatus": "IRREGULAR_PERIOD",
        }

    actual_row = None
    forecast_row = None

    # Prefer the first consolidated/full-year
    # performance row on page 1.
    for line in pages[0]:
        if is_full_year_actual_row(
            line
        ):
            actual_row = line
            break

    for page_lines in pages:
        for line in page_lines:
            if is_forecast_row(
                line
            ):
                forecast_row = line
                break

        if forecast_row is not None:
            break

    if actual_row is None:
        return {
            "ParseStatus": "ACTUAL_NOT_FOUND",
        }

    actual = parse_actual_row(
        actual_row
    )

    if actual is None:
        return {
            "ParseStatus": "ACTUAL_PARSE_FAIL",
            "ActualRow": actual_row,
        }

    if forecast_row is None:
        result = {
            "ParseStatus": "FORECAST_NOT_FOUND",
            "ActualRow": actual_row,
        }

        result.update(actual)
        return result

    forecast = parse_forecast_row(
        forecast_row
    )

    if forecast is None:
        result = {
            "ParseStatus": "FORECAST_INCOMPLETE",
            "ActualRow": actual_row,
            "ForecastRow": forecast_row,
        }

        result.update(actual)
        return result

    result = {
        "ParseStatus": "OK",
        "ActualRow": actual_row,
        "ForecastRow": forecast_row,
    }

    result.update(actual)
    result.update(forecast)

    growths = [
        result["ForecastSalesGrowth"],
        result["ForecastOperatingGrowth"],
        result["ForecastOrdinaryGrowth"],
        result["ForecastNetGrowth"],
    ]

    # Growth information itself can be unavailable
    # when comparison with the prior year is not
    # meaningful. Do not silently invent it.
    if any(
        x is None
        for x in growths
    ):
        result[
            "MinForecastGrowth4"
        ] = None

        result[
            "GrowthStatus"
        ] = "GROWTH_INCOMPLETE"
    else:
        result[
            "MinForecastGrowth4"
        ] = min(
            growths
        )

        result[
            "GrowthStatus"
        ] = "OK"

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
