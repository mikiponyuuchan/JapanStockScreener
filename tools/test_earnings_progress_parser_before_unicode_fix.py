from pathlib import Path
import re

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ("20260814", "3763"),
    ("20260814", "4476"),
    ("20260814", "9553"),
    ("20260909", "6966"),
    ("20260910", "6184"),
]


def clean(text):
    return " ".join(str(text).split())


def parse_num(text):
    text = str(text)
    text = text.replace(",", "")
    text = text.replace("?", "-")
    text = text.replace("?", "-")

    m = re.search(r"-?\d+(?:\.\d+)?", text)

    if not m:
        return None

    try:
        return float(m.group())
    except Exception:
        return None


def detect_quarter(text):
    if "?????" in text or "1Q" in text or "??" in text:
        return "Q1"

    if (
        "?????" in text
        or "???" in text
        or "2Q" in text
        or "??" in text
    ):
        return "Q2"

    if "?????" in text or "3Q" in text or "??" in text:
        return "Q3"

    return None


def extract_first_pages(path):
    reader = PdfReader(str(path))

    texts = []

    for page in reader.pages[:3]:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        texts.append(text)

    return "\n".join(texts)


def find_actual_row(lines):
    for line in lines:
        if (
            ("?????" in line
             or "?????" in line
             or "?????" in line
             or "???" in line)
            and "???" not in line
            and re.search(r"\d[\d,]*\s+[-??]?\d", line)
        ):
            return line

    return None


def find_forecast_row(lines):
    for line in lines:
        if line.startswith("?? "):
            return line

    return None


def infer_value_pairs(row):
    if not row:
        return []

    parts = row.split()

    values = []

    for part in parts:
        val = parse_num(part)

        if val is not None:
            values.append(val)

    return values


def parse_standard_row(actual_row, forecast_row):
    actual = infer_value_pairs(actual_row)
    forecast = infer_value_pairs(forecast_row)

    # First number can be fiscal year from date text.
    # Keep only the tail values that look like:
    # amount, yoy, amount, yoy, amount, yoy, amount, yoy
    if len(actual) >= 8:
        actual = actual[-8:]

    if len(forecast) >= 9:
        forecast = forecast[-9:]

    if len(actual) < 8:
        return None

    if len(forecast) < 8:
        return None

    result = {
        "ActualSales": actual[0],
        "ActualOperating": actual[2],
        "ActualOrdinary": actual[4],
        "ActualNet": actual[6],
        "ForecastSales": forecast[0],
        "ForecastOperating": forecast[2],
        "ForecastOrdinary": forecast[4],
        "ForecastNet": forecast[6],
    }

    return result


def parse_6184_like(actual_row, forecast_row):
    actual = infer_value_pairs(actual_row)
    forecast = infer_value_pairs(forecast_row)

    # 6184-type:
    # Sales, EBITDA, Operating, Ordinary, Net
    # each amount + yoy
    if len(actual) >= 10:
        actual = actual[-10:]

    if len(forecast) >= 11:
        forecast = forecast[-11:]

    if len(actual) < 10:
        return None

    if len(forecast) < 10:
        return None

    return {
        "ActualSales": actual[0],
        "ActualOperating": actual[4],
        "ActualOrdinary": actual[6],
        "ActualNet": actual[8],
        "ForecastSales": forecast[0],
        "ForecastOperating": forecast[4],
        "ForecastOrdinary": forecast[6],
        "ForecastNet": forecast[8],
    }


def parse_pdf(path):
    text = extract_first_pages(path)

    lines = [
        clean(x)
        for x in text.splitlines()
        if clean(x)
    ]

    quarter = detect_quarter(text)

    actual_row = find_actual_row(lines)
    forecast_row = find_forecast_row(lines)

    has_ebitda = "???EBITDA" in text

    if has_ebitda:
        values = parse_6184_like(
            actual_row,
            forecast_row,
        )
    else:
        values = parse_standard_row(
            actual_row,
            forecast_row,
        )

    result = {
        "Quarter": quarter,
        "ActualRow": actual_row,
        "ForecastRow": forecast_row,
    }

    if not values:
        return result

    result.update(values)

    op_actual = values["ActualOperating"]
    op_forecast = values["ForecastOperating"]

    net_actual = values["ActualNet"]
    net_forecast = values["ForecastNet"]

    result["OperatingProgress"] = (
        op_actual / op_forecast * 100
        if op_forecast not in (None, 0)
        else None
    )

    result["NetProgress"] = (
        net_actual / net_forecast * 100
        if net_forecast not in (None, 0)
        else None
    )

    expected = {
        "Q1": 25.0,
        "Q2": 50.0,
        "Q3": 75.0,
    }.get(quarter)

    result["ExpectedProgress"] = expected

    if expected is not None:
        result["OperatingProgressExcess"] = (
            result["OperatingProgress"] - expected
        )

        result["NetProgressExcess"] = (
            result["NetProgress"] - expected
        )

    return result


def fmt(v):
    if v is None:
        return "None"

    if isinstance(v, float):
        return f"{v:.2f}"

    return str(v)


def main():
    print("=" * 100)
    print("EARNINGS PROGRESS PARSER TEST")
    print("=" * 100)

    for date, code in TARGETS:
        path = (
            ROOT
            / "data"
            / "analysis"
            / "earnings_pdf"
            / date
            / f"{code}.pdf"
        )

        print()
        print("-" * 100)
        print(code)
        print("-" * 100)

        result = parse_pdf(path)

        for key in [
            "Quarter",
            "ActualOperating",
            "ForecastOperating",
            "OperatingProgress",
            "OperatingProgressExcess",
            "ActualNet",
            "ForecastNet",
            "NetProgress",
            "NetProgressExcess",
        ]:
            print(
                f"{key:<26}: {fmt(result.get(key))}"
            )

        print()
        print(
            "ActualRow  :",
            result.get("ActualRow"),
        )

        print(
            "ForecastRow:",
            result.get("ForecastRow"),
        )


if __name__ == "__main__":
    main()
