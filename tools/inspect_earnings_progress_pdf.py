from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ("20260814", "3763"),
    ("20260814", "4476"),
    ("20260814", "9553"),
    ("20260909", "6966"),
    ("20260910", "6184"),
]


KEYWORDS = [
    "\u55b6\u696d\u5229\u76ca",
    "\u7d4c\u5e38\u5229\u76ca",
    "\u7d14\u5229\u76ca",
    "\u901a\u671f",
    "\u696d\u7e3e\u4e88\u60f3",
    "\u7d2f\u8a08",
    "\u9032\u6357",
    "\u7b2c1\u56db\u534a\u671f",
    "\u7b2c2\u56db\u534a\u671f",
    "\u7b2c3\u56db\u534a\u671f",
]


def clean(text):
    return " ".join(
        str(text).split()
    )


def main():
    print("=" * 90)
    print("EARNINGS PROGRESS PDF INSPECTION")
    print("=" * 90)

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
        print("=" * 90)
        print(
            code,
            path,
        )
        print("=" * 90)

        if not path.exists():
            print("PDF NOT FOUND")
            continue

        try:
            reader = PdfReader(
                str(path)
            )
        except Exception as e:
            print(
                "PDF ERROR:",
                e,
            )
            continue

        pages = min(
            len(reader.pages),
            3,
        )

        lines = []

        for page_no in range(pages):
            try:
                text = (
                    reader.pages[page_no]
                    .extract_text()
                    or ""
                )
            except Exception:
                text = ""

            for line in text.splitlines():
                line = clean(line)

                if line:
                    lines.append(
                        (
                            page_no + 1,
                            line,
                        )
                    )

        found = []

        for i, (page_no, line) in enumerate(lines):
            if any(
                key in line
                for key in KEYWORDS
            ):
                start = max(
                    0,
                    i - 2,
                )

                end = min(
                    len(lines),
                    i + 4,
                )

                for item in lines[
                    start:end
                ]:
                    if item not in found:
                        found.append(
                            item
                        )

        if not found:
            print(
                "No keyword lines found."
            )
            continue

        for page_no, line in found:
            print(
                f"[P{page_no}] {line}"
            )


if __name__ == "__main__":
    main()
