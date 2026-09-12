from pathlib import Path
import re

from pypdf import PdfReader


Q1_MARKS = [
    "\u7b2c\uff11\u56db\u534a\u671f",
    "\u7b2c1\u56db\u534a\u671f",
]

Q2_MARKS = [
    "\u7b2c\uff12\u56db\u534a\u671f",
    "\u7b2c2\u56db\u534a\u671f",
    "\u4e2d\u9593\u671f",
]

Q3_MARKS = [
    "\u7b2c\uff13\u56db\u534a\u671f",
    "\u7b2c3\u56db\u534a\u671f",
]

FORECAST_WORD = "\u696d\u7e3e\u4e88\u60f3"
FULL_YEAR = "\u901a\u671f"
SALES = "\u58f2\u4e0a\u9ad8"
OPERATING = "\u55b6\u696d\u5229\u76ca"
EBITDA = "EBITDA"


def clean(line):
    return " ".join(
        str(line).split()
    )


def normalize_metric_text(text):
    text = text.replace(
        "\u25b3 ",
        "\u25b3",
    )

    text = text.replace(
        "\u25b2 ",
        "\u25b2",
    )

    text = text.replace(
        "\u2212 ",
        "\u2212",
    )

    return text


def parse_number(token):
    token = str(token).strip()

    if token in {
        "-",
        "\u30fc",
        "\u2015",
        "\u2014",
        "\u2212",
    }:
        return None

    token = token.replace(
        ",",
        "",
    )

    negative = False

    if token.startswith(
        (
            "\u25b3",
            "\u25b2",
        )
    ):
        negative = True
        token = token[1:]

    try:
        value = float(token)
    except Exception:
        return None

    if negative:
        value = -value

    return value


def extract_lines(path):
    reader = PdfReader(str(path))

    lines = []

    for page in reader.pages[:3]:
        text = page.extract_text() or ""

        for line in text.splitlines():
            line = clean(line)

            if line:
                lines.append(line)

    return lines


def detect_stage(lines):
    # Use the beginning of the document only.
    # This prevents later dividend text containing "Q2"
    # from changing a Q1 result into Q2.
    head = "\n".join(
        lines[:25]
    )

    for mark in Q3_MARKS:
        if mark in head:
            return "Q3"

    for mark in Q2_MARKS:
        if mark in head:
            return "Q2"

    for mark in Q1_MARKS:
        if mark in head:
            return "Q1"

    return "FY"


def quarter_marks(stage):
    if stage == "Q1":
        return Q1_MARKS

    if stage == "Q2":
        return Q2_MARKS

    if stage == "Q3":
        return Q3_MARKS

    return []


def strip_actual_label(line, stage):
    marks = quarter_marks(stage)

    for mark in marks:
        pos = line.find(mark)

        if pos >= 0:
            return line[
                pos + len(mark):
            ].strip()

    return None


def metric_tokens(text):
    if text is None:
        return []

    text = normalize_metric_text(
        text
    )

    return text.split()


def parse_standard_metrics(text):
    tokens = metric_tokens(text)

    if len(tokens) < 8:
        return None

    values = [
        parse_number(tokens[i])
        for i in [0, 2, 4, 6]
    ]

    if any(
        x is None
        for x in values
    ):
        return None

    return {
        "Sales": values[0],
        "Operating": values[1],
        "Ordinary": values[2],
        "Net": values[3],
    }


def parse_ebitda_metrics(text):
    tokens = metric_tokens(text)

    if len(tokens) < 10:
        return None

    # Sales / EBITDA / Operating /
    # Ordinary / Net
    values = [
        parse_number(tokens[i])
        for i in [0, 4, 6, 8]
    ]

    if any(
        x is None
        for x in values
    ):
        return None

    return {
        "Sales": values[0],
        "Operating": values[1],
        "Ordinary": values[2],
        "Net": values[3],
    }


def find_actual_row(lines, stage):
    if stage == "FY":
        return None

    marks = quarter_marks(stage)

    for line in lines[:40]:
        if not re.match(
            r"^20\d{2}\u5e74",
            line,
        ):
            continue

        if not any(
            mark in line
            for mark in marks
        ):
            continue

        rest = strip_actual_label(
            line,
            stage,
        )

        if rest is None:
            continue

        tokens = metric_tokens(
            rest
        )

        if len(tokens) >= 8:
            return line

    return None


def find_forecast_row(lines):
    # First prefer an explicit full-year row.
    for line in lines:
        compact = line.replace(
            " ",
            "",
        )

        if compact.startswith(
            FULL_YEAR
        ):
            return line

    # Some companies do not use "full year".
    # Find the first forecast section and inspect
    # the nearby fiscal-year rows.
    forecast_start = None

    for i, line in enumerate(lines):
        if FORECAST_WORD in line:
            forecast_start = i
            break

    if forecast_start is None:
        return None

    end = min(
        len(lines),
        forecast_start + 25,
    )

    for line in lines[
        forecast_start:end
    ]:
        if not re.match(
            r"^20\d{2}\u5e74",
            line,
        ):
            continue

        # Do not mistake quarter actual rows
        # for a forecast row.
        if any(
            mark in line
            for mark in (
                Q1_MARKS
                + Q2_MARKS
                + Q3_MARKS
            )
        ):
            continue

        m = re.match(
            r"^20\d{2}\u5e74[^ ]*\s+(.+)$",
            line,
        )

        if not m:
            continue

        tokens = metric_tokens(
            m.group(1)
        )

        if len(tokens) >= 8:
            return line

    return None


def strip_forecast_label(line):
    if line is None:
        return None

    compact = line.replace(
        " ",
        "",
    )

    if compact.startswith(
        FULL_YEAR
    ):
        m = re.match(
            r"^\u901a\s*\u671f\s+(.+)$",
            line,
        )

        if m:
            return m.group(1)

    m = re.match(
        r"^20\d{2}\u5e74.*?\s+(.+)$",
        line,
    )

    if m:
        return m.group(1)

    return None


def parse_pdf(path):
    lines = extract_lines(path)

    stage = detect_stage(lines)

    if stage == "FY":
        return {
            "ParseStatus": "FULL_YEAR",
            "Quarter": "FY",
            "ActualRow": None,
            "ForecastRow": find_forecast_row(
                lines
            ),
        }

    actual_row = find_actual_row(
        lines,
        stage,
    )

    forecast_row = find_forecast_row(
        lines
    )

    if actual_row is None:
        return {
            "ParseStatus": "ACTUAL_NOT_FOUND",
            "Quarter": stage,
            "ActualRow": None,
            "ForecastRow": forecast_row,
        }

    if forecast_row is None:
        return {
            "ParseStatus": "NO_FORECAST",
            "Quarter": stage,
            "ActualRow": actual_row,
            "ForecastRow": None,
        }

    actual_text = strip_actual_label(
        actual_row,
        stage,
    )

    forecast_text = strip_forecast_label(
        forecast_row
    )

    # Detect EBITDA format from the forecast row structure.
    #
    # Standard forecast:
    # Sales / Operating / Ordinary / Net / EPS
    #
    # EBITDA forecast:
    # Sales / EBITDA / Operating / Ordinary / Net / EPS
    #
    # This is safer than searching the PDF for the word EBITDA,
    # because EBITDA may appear elsewhere in notes or commentary.
    forecast_tokens = metric_tokens(
        forecast_text
    )

    has_ebitda = (
        len(forecast_tokens) >= 11
    )

    if has_ebitda:
        actual = parse_ebitda_metrics(
            actual_text
        )

        forecast = parse_ebitda_metrics(
            forecast_text
        )
    else:
        actual = parse_standard_metrics(
            actual_text
        )

        forecast = parse_standard_metrics(
            forecast_text
        )

    if forecast is None:
        return {
            "ParseStatus":
                "NO_PROFIT_FORECAST",
            "Quarter": stage,
            "HasEBITDA": has_ebitda,
            "ActualRow": actual_row,
            "ForecastRow": forecast_row,
        }

    if actual is None:
        return {
            "ParseStatus":
                "ACTUAL_PARSE_FAIL",
            "Quarter": stage,
            "HasEBITDA": has_ebitda,
            "ActualRow": actual_row,
            "ForecastRow": forecast_row,
        }

    op_forecast = forecast[
        "Operating"
    ]

    net_forecast = forecast[
        "Net"
    ]

    # Progress is not meaningful against
    # zero or negative full-year profit forecast.
    if (
        op_forecast <= 0
        or net_forecast <= 0
    ):
        return {
            "ParseStatus":
                "NONPOSITIVE_FORECAST",
            "Quarter": stage,
            "HasEBITDA": has_ebitda,
            "ActualRow": actual_row,
            "ForecastRow": forecast_row,
        }

    expected = {
        "Q1": 25.0,
        "Q2": 50.0,
        "Q3": 75.0,
    }[stage]

    op_progress = (
        actual["Operating"]
        / op_forecast
        * 100.0
    )

    net_progress = (
        actual["Net"]
        / net_forecast
        * 100.0
    )

    return {
        "ParseStatus": "OK",
        "Quarter": stage,
        "HasEBITDA": has_ebitda,

        "ActualOperating":
            actual["Operating"],
        "ForecastOperating":
            op_forecast,
        "OperatingProgress":
            op_progress,
        "OperatingProgressExcess":
            op_progress - expected,

        "ActualNet":
            actual["Net"],
        "ForecastNet":
            net_forecast,
        "NetProgress":
            net_progress,
        "NetProgressExcess":
            net_progress - expected,

        "ActualRow":
            actual_row,
        "ForecastRow":
            forecast_row,
    }
