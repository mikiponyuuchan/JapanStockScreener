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


Q1_A = "\u7b2c\uff11\u56db\u534a\u671f"
Q2_A = "\u7b2c\uff12\u56db\u534a\u671f"
Q3_A = "\u7b2c\uff13\u56db\u534a\u671f"

Q1_B = "\uff11\uff31"
Q2_B = "\uff12\uff31"
Q3_B = "\uff13\uff31"

Q1_C = "1Q"
Q2_C = "2Q"
Q3_C = "3Q"

INTERIM = "\u4e2d\u9593\u671f"
MILLION = "\u767e\u4e07\u5186"
FULL_YEAR = "\u901a\u671f"
ADJ_EBITDA = "\u8abf\u6574\u5f8cEBITDA"


def clean(text):
    return " ".join(str(text).split())


def parse_num(text):
    text = str(text)

    text = text.replace(",", "")
    text = text.replace("\u25b3", "-")
    text = text.replace("\u25b2", "-")

    m = re.search(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    if not m:
        return None

    try:
        return float(m.group())
    except Exception:
        return None


def detect_quarter(text):
    if not text:
        return None

    if (
        Q3_A in text
        or Q3_B in text
        or Q3_C in text
    ):
        return "Q3"

    if (
        Q2_A in text
        or INTERIM in text
        or Q2_B in text
        or Q2_C in text
    ):
        return "Q2"

    if (
        Q1_A in text
        or Q1_B in text
        or Q1_C in text
    ):
        return "Q1"

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


def is_period_row(line):
    # Actual table rows normally start with a fiscal year.
    # This rejects section headings such as:
    # "1. FY2027 Q2 results (date range)"
    if not re.match(
        r"^20\d{2}\u5e74",
        line,
    ):
        return False

    has_period = any(
        x in line
        for x in [
            Q1_A,
            Q2_A,
            Q3_A,
            INTERIM,
        ]
    )

    if not has_period:
        return False

    if MILLION in line:
        return False

    nums = re.findall(
        r"[-\u25b3\u25b2]?\d[\d,]*(?:\.\d+)?",
        line,
    )

    # Do not enforce exact column count here.
    # Dash placeholders can reduce numeric token count.
    return len(nums) >= 4


def find_actual_row(lines):
    for line in lines:
        if is_period_row(line):
            return line

    return None


def find_forecast_row(lines):
    for line in lines:
        if line.startswith(FULL_YEAR + " "):
            return line

        if line == FULL_YEAR:
            return line

    return None


def infer_values(row):
    if not row:
        return []

    values = []

    for part in row.split():
        val = parse_num(part)

        if val is not None:
            values.append(val)

    return values


def parse_standard_row(
    actual_row,
    forecast_row,
):
    actual = infer_values(actual_row)
    forecast = infer_values(forecast_row)

    if len(actual) >= 8:
        actual = actual[-8:]

    if len(forecast) >= 9:
        forecast = forecast[-9:]

    if len(actual) < 8:
        return None

    if len(forecast) < 8:
        return None

    return {
        "ActualSales": actual[0],
        "ActualOperating": actual[2],
        "ActualOrdinary": actual[4],
        "ActualNet": actual[6],
        "ForecastSales": forecast[0],
        "ForecastOperating": forecast[2],
        "ForecastOrdinary": forecast[4],
        "ForecastNet": forecast[6],
    }


def parse_ebitda_row(
    actual_row,
    forecast_row,
):
    actual = infer_values(actual_row)
    forecast = infer_values(forecast_row)

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
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]

    actual_row = find_actual_row(lines)
    forecast_row = find_forecast_row(lines)

    quarter = detect_quarter(actual_row)

    has_ebitda = ADJ_EBITDA in text

    if has_ebitda:
        values = parse_ebitda_row(
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
        "HasEBITDA": has_ebitda,
    }

    if values is None:
        return result

    result.update(values)

    op_actual = values["ActualOperating"]
    op_forecast = values["ForecastOperating"]

    net_actual = values["ActualNet"]
    net_forecast = values["ForecastNet"]

    op_progress = None
    net_progress = None

    if op_forecast not in (None, 0):
        op_progress = (
            op_actual
            / op_forecast
            * 100.0
        )

    if net_forecast not in (None, 0):
        net_progress = (
            net_actual
            / net_forecast
            * 100.0
        )

    result["OperatingProgress"] = op_progress
    result["NetProgress"] = net_progress

    expected = {
        "Q1": 25.0,
        "Q2": 50.0,
        "Q3": 75.0,
    }.get(quarter)

    result["ExpectedProgress"] = expected

    if (
        expected is not None
        and op_progress is not None
    ):
        result[
            "OperatingProgressExcess"
        ] = op_progress - expected

    if (
        expected is not None
        and net_progress is not None
    ):
        result[
            "NetProgressExcess"
        ] = net_progress - expected

    return result


def fmt(value):
    if value is None:
        return "None"

    if isinstance(value, float):
        return f"{value:.2f}"

    return str(value)


def main():
    print("=" * 100)
    print("EARNINGS PROGRESS PARSER TEST - UNICODE FIX")
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
            "HasEBITDA",
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
                f"{key:<26}: "
                f"{fmt(result.get(key))}"
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
