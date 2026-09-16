import re
from pathlib import Path

from pypdf import PdfReader


def normalize(text):
    return (
        text
        .replace(",", "")
        .replace("?", "-")
        .replace("?", "-")
        .replace("?", "-")
        .replace("?", "-")
        .replace("?", "%")
    )


def numbers(text):
    text = normalize(text)

    return [
        float(x)
        for x in re.findall(
            r"-?\d+(?:\.\d+)?",
            text,
        )
    ]


def parse_actual_row(line):
    vals = numbers(line)

    # Year, month, sales, sales_yoy,
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

    # sales, yoy,
    # operating, yoy,
    # ordinary, yoy,
    # net, yoy,
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

    # Full-year actual:
    # YYYY?MM?? ...
    for line in pages[0]:
        if (
            re.match(
                r"^20\d{2}?.+??\s",
                line,
            )
            and "??" not in line
        ):
            vals = numbers(line)

            if len(vals) >= 10:
                actual_row = line
                break

    # Next-year forecast:
    # usually "?? ..."
    for lines in pages:
        for line in lines:
            if re.match(
                r"^?\s*?\s",
                line,
            ):
                vals = numbers(line)

                if len(vals) >= 8:
                    forecast_row = line
                    break

        if forecast_row:
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

    growths = [
        result["ForecastSalesGrowth"],
        result["ForecastOperatingGrowth"],
        result["ForecastOrdinaryGrowth"],
        result["ForecastNetGrowth"],
    ]

    result["MinForecastGrowth4"] = min(
        growths
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

    for key, value in result.items():
        print(
            f"{key:<28}: {value}"
        )
