from pathlib import Path
import re

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ("20260814", "3936"),
    ("20260814", "584A"),
    ("20260814", "7747"),
    ("20260818", "6327"),
    ("20260909", "2751"),
    ("20260814", "6092"),
    ("20260901", "4750"),
    ("20260814", "6538"),
    ("20260814", "7031"),
    ("20260814", "7084"),
]

KEYWORDS = [
    "\u58f2\u4e0a\u9ad8",
    "\u55b6\u696d\u5229\u76ca",
    "\u7d4c\u5e38\u5229\u76ca",
    "\u89aa\u4f1a\u793e\u682a\u4e3b\u306b\u5e30\u5c5e\u3059\u308b",
    "\u901a\u671f",
    "\u7b2c\uff11\u56db\u534a\u671f",
    "\u7b2c\uff12\u56db\u534a\u671f",
    "\u7b2c\uff13\u56db\u534a\u671f",
    "\u4e2d\u9593\u671f",
]

CONTEXT = 5


def clean(line):
    return " ".join(
        str(line).split()
    )


def extract_lines(path):
    reader = PdfReader(str(path))

    lines = []

    for page_no, page in enumerate(
        reader.pages[:3],
        start=1,
    ):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            lines.append(
                (
                    page_no,
                    f"[PAGE ERROR] {e}",
                )
            )
            continue

        for line in text.splitlines():
            line = clean(line)

            if line:
                lines.append(
                    (
                        page_no,
                        line,
                    )
                )

    return lines


def find_hits(lines):
    hits = []

    for i, (_, line) in enumerate(lines):
        if any(
            keyword in line
            for keyword in KEYWORDS
        ):
            hits.append(i)

    return hits


def merge_ranges(hits, total):
    ranges = []

    for hit in hits:
        start = max(
            0,
            hit - CONTEXT,
        )

        end = min(
            total,
            hit + CONTEXT + 1,
        )

        if (
            ranges
            and start <= ranges[-1][1]
        ):
            ranges[-1] = (
                ranges[-1][0],
                max(
                    ranges[-1][1],
                    end,
                ),
            )
        else:
            ranges.append(
                (start, end)
            )

    return ranges


def main():
    print("=" * 100)
    print(
        "FAILED EARNINGS PROGRESS CASE INSPECTOR"
    )
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
        print("#" * 100)
        print(
            f"{date}  {code}"
        )
        print("#" * 100)

        if not path.exists():
            print(
                "PDF NOT FOUND:",
                path,
            )
            continue

        try:
            lines = extract_lines(
                path
            )
        except Exception as e:
            print(
                "PDF READ ERROR:",
                e,
            )
            continue

        print(
            f"Extracted lines : {len(lines)}"
        )

        hits = find_hits(
            lines
        )

        print(
            f"Keyword hits    : {len(hits)}"
        )

        if not hits:
            print()
            print(
                "NO KEYWORD MATCH"
            )

            print()
            print(
                "--- FIRST 50 LINES ---"
            )

            for i, (
                page_no,
                line,
            ) in enumerate(
                lines[:50]
            ):
                print(
                    f"{i:04d} "
                    f"[P{page_no}] "
                    f"{line}"
                )

            continue

        ranges = merge_ranges(
            hits,
            len(lines),
        )

        for block_no, (
            start,
            end,
        ) in enumerate(
            ranges,
            start=1,
        ):
            print()
            print(
                f"--- BLOCK {block_no} "
                f"LINES {start}-{end - 1} ---"
            )

            for i in range(
                start,
                end,
            ):
                page_no, line = (
                    lines[i]
                )

                marker = "  "

                if any(
                    keyword in line
                    for keyword in KEYWORDS
                ):
                    marker = ">>"

                print(
                    f"{marker} "
                    f"{i:04d} "
                    f"[P{page_no}] "
                    f"{line}"
                )


if __name__ == "__main__":
    main()
