from intraday.rss_board_safe_writer import normalize_stock_code


FIRST_ROW = 2
LAST_ROW = 21

H1_FIRST = 2
H1_LAST = 11

J1_FIRST = 12
J1_LAST = 16


def split_labels(value):
    if not value:
        return []
    return [
        part.strip()
        for part in str(value).split("/")
        if part.strip()
    ]


def build_fixed_layout(
    current_layout,
    h1_codes,
    j1_codes,
    h1_decisions=None,
):
    """
    Pure calculation. No Excel access or writes.

    current_layout: {row: (code, label)}
    h1_codes: ordered TOP10
    j1_codes: ordered TOP5 candidates
    h1_decisions: {code: decision label}, optional

    Returns complete layout for rows 2..21.
    """

    h1_decisions = h1_decisions or {}

    if j1_codes is None:
        j1_codes = [
            current_layout.get(row, ("", ""))[0]
            for row in range(J1_FIRST, J1_LAST + 1)
            if any(
                part == "J1 BUY"
                or part.startswith("J1 BUY ")
                for part in split_labels(
                    current_layout.get(row, ("", ""))[1]
                )
            )
        ]

    old_labels_by_code = {}

    for row, (code, label) in current_layout.items():
        code = normalize_stock_code(code)
        if not code:
            continue

        old_labels_by_code.setdefault(code, [])

        for part in split_labels(label):
            if part not in old_labels_by_code[code]:
                old_labels_by_code[code].append(part)

    def preserved_labels(code):
        return [
            part
            for part in old_labels_by_code.get(code, [])
            if not part.startswith("H1 #")
            and not part.startswith("H1 CAND #")
            and not part.startswith("J1 BUY")
        ]

    layout = {
        row: (
            current_layout.get(row, ("", ""))[0],
            current_layout.get(row, ("", ""))[1],
        )
        if row >= 17
        else ("", "")
        for row in range(FIRST_ROW, LAST_ROW + 1)
    }

    normalized_h1 = [
        normalize_stock_code(code)
        for code in h1_codes
    ]
    normalized_h1 = [
        code for code in normalized_h1 if code
    ]

    if len(normalized_h1) > 10:
        raise ValueError("H1 exceeds TOP10")

    if len(set(normalized_h1)) != len(normalized_h1):
        raise ValueError("Duplicate H1 codes")

    h1_set = set(normalized_h1)

    for rank, code in enumerate(normalized_h1, start=1):
        row = H1_FIRST + rank - 1

        label = h1_decisions.get(code)
        if not label:
            label = f"H1 CAND #{rank}"

        labels = [label] + preserved_labels(code)
        layout[row] = (code, " / ".join(labels))

    seen_j1 = set()

    j1_filtered = []

    for raw_code in j1_codes:
        code = normalize_stock_code(raw_code)

        if (
            not code
            or code in h1_set
            or code in seen_j1
        ):
            continue

        seen_j1.add(code)
        j1_filtered.append(code)

        if len(j1_filtered) == 5:
            break

    for index, code in enumerate(j1_filtered):
        row = J1_FIRST + index

        labels = ["J1 BUY"] + preserved_labels(code)
        layout[row] = (code, " / ".join(labels))

    # Remove duplicates in overflow rows only when labels are preserved.
    fixed_by_code = {}

    for row in range(H1_FIRST, J1_LAST + 1):
        code, label = layout[row]
        code = normalize_stock_code(code)
        if code:
            fixed_by_code[code] = set(split_labels(label))

    for row in range(17, LAST_ROW + 1):
        code, label = layout[row]
        code = normalize_stock_code(code)

        if not code or code not in fixed_by_code:
            continue

        original_labels = set(split_labels(label))

        if not original_labels.issubset(fixed_by_code[code]):
            raise RuntimeError(
                "DUPLICATE REMOVAL BLOCKED: "
                + code
                + " has labels not preserved in fixed rows"
            )

        layout[row] = ("", "")

    # Relocate displaced SSR stocks into unused rows 17..21.
    placed_codes = {
        normalize_stock_code(code)
        for code, label in layout.values()
        if normalize_stock_code(code)
    }

    displaced_ssr = []

    for row in range(FIRST_ROW, LAST_ROW + 1):
        code, label = current_layout.get(row, ("", ""))
        code = normalize_stock_code(code)

        if not code or code in placed_codes:
            continue

        if not any(
            part.startswith("SSR")
            for part in split_labels(label)
        ):
            continue

        displaced_ssr.append((code, label))
        placed_codes.add(code)

    free_rows = [
        row
        for row in range(17, LAST_ROW + 1)
        if not normalize_stock_code(layout[row][0])
        and not str(layout[row][1] or "").strip()
    ]

    if len(displaced_ssr) > len(free_rows):
        raise RuntimeError(
            "SSR RELOCATION BLOCKED: insufficient free rows"
        )

    for (code, label), row in zip(displaced_ssr, free_rows):
        layout[row] = (code, label)

    # Never silently remove SSR-only stocks.
    old_ssr_codes = {
        normalize_stock_code(code)
        for code, label in current_layout.values()
        if normalize_stock_code(code)
        and any(
            part.startswith("SSR")
            for part in split_labels(label)
        )
    }

    new_codes = {
        normalize_stock_code(code)
        for code, label in layout.values()
        if normalize_stock_code(code)
    }

    missing_ssr = old_ssr_codes - new_codes

    if missing_ssr:
        raise RuntimeError(
            "SSR STOCK LOSS BLOCKED: "
            + ", ".join(sorted(missing_ssr))
        )

    return layout