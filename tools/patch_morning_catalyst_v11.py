from pathlib import Path

path = Path("tools/create_morning_catalyst.py")
text = path.read_text(encoding="utf-8")

backup = Path(
    "tools/create_morning_catalyst_before_noise_filter.py"
)
backup.write_text(text, encoding="utf-8")


old_rules = r'''    (
        "TOB/MBO",
        5,
        [
            "\u516c\u958b\u8cb7\u4ed8",
            "\u516c\u958b\u8cb7\u4ed8\u3051",
            "TOB",
            "MBO",
            "\u30de\u30cd\u30b8\u30e1\u30f3\u30c8\u30fb\u30d0\u30a4\u30a2\u30a6\u30c8",
        ],
        False,
    ),'''

new_rules = r'''    (
        "TOB/MBO",
        5,
        [
            "\u516c\u958b\u8cb7\u4ed8\u3051\u306e\u958b\u59cb",
            "\u516c\u958b\u8cb7\u4ed8\u306e\u958b\u59cb",
            "\u516c\u958b\u8cb7\u4ed8\u3051\u306b\u95a2\u3059\u308b\u8cdb\u540c",
            "\u516c\u958b\u8cb7\u4ed8\u306b\u95a2\u3059\u308b\u8cdb\u540c",
            "MBO",
            "\u30de\u30cd\u30b8\u30e1\u30f3\u30c8\u30fb\u30d0\u30a4\u30a2\u30a6\u30c8",
        ],
        False,
    ),'''

if old_rules not in text:
    raise SystemExit("ERROR: TOB rule marker not found")

text = text.replace(
    old_rules,
    new_rules,
    1,
)


old_buyback = r'''    (
        "\u81ea\u5df1\u682a\u5f0f\u53d6\u5f97",
        4,
        [
            "\u81ea\u5df1\u682a\u5f0f\u306e\u53d6\u5f97",
            "\u81ea\u5df1\u682a\u5f0f\u53d6\u5f97",
            "\u81ea\u793e\u682a\u8cb7\u3044",
        ],
        False,
    ),'''

new_buyback = r'''    (
        "\u81ea\u5df1\u682a\u5f0f\u53d6\u5f97",
        4,
        [
            "\u81ea\u5df1\u682a\u5f0f\u306e\u53d6\u5f97\u306b\u4fc2\u308b\u4e8b\u9805\u306e\u6c7a\u5b9a",
            "\u81ea\u5df1\u682a\u5f0f\u53d6\u5f97\u306b\u4fc2\u308b\u4e8b\u9805\u306e\u6c7a\u5b9a",
            "\u81ea\u5df1\u682a\u5f0f\u306e\u53d6\u5f97\u53ca\u3073\u6d88\u5374\u306b\u4fc2\u308b\u4e8b\u9805\u306e\u6c7a\u5b9a",
        ],
        False,
    ),'''

if old_buyback not in text:
    raise SystemExit("ERROR: buyback rule marker not found")

text = text.replace(
    old_buyback,
    new_buyback,
    1,
)


old_dividend = r'''    (
        "\u5897\u914d",
        3,
        [
            "\u5897\u914d",
            "\u914d\u5f53\u4e88\u60f3\u306e\u4fee\u6b63",
        ],
        False,
    ),'''

new_dividend = r'''    (
        "\u5897\u914d",
        3,
        [
            "\u5897\u914d",
            "\u7279\u5225\u914d\u5f53",
            "\u8a18\u5ff5\u914d\u5f53",
        ],
        False,
    ),'''

if old_dividend not in text:
    raise SystemExit("ERROR: dividend rule marker not found")

text = text.replace(
    old_dividend,
    new_dividend,
    1,
)


old_create = r'''        title = str(
            tdnet.get(
                "title",
                "",
            )
        ).strip()

        classification = classify_title(
            title
        )
'''

new_create = r'''        pubdate = str(
            tdnet.get(
                "pubdate",
                "",
            )
        ).strip()

        try:
            pub_dt = pd.to_datetime(
                pubdate
            )
        except Exception:
            continue

        cutoff_time = pd.Timestamp(
            pub_dt.date()
        ) + pd.Timedelta(
            hours=15,
            minutes=30,
        )

        if pub_dt < cutoff_time:
            continue

        title = str(
            tdnet.get(
                "title",
                "",
            )
        ).strip()

        tob_noise_words = [
            "\u516c\u958b\u8cb7\u4ed8\u3051\u306e\u7d50\u679c",
            "\u516c\u958b\u8cb7\u4ed8\u306e\u7d50\u679c",
            "\u516c\u958b\u8cb7\u4ed8\u3051\u306e\u5909\u66f4",
            "\u516c\u958b\u8cb7\u4ed8\u306e\u5909\u66f4",
            "\u516c\u958b\u8cb7\u4ed8\u5c4a\u51fa\u66f8\u306e\u8a02\u6b63",
        ]

        if any(
            word in title
            for word in tob_noise_words
        ):
            continue

        classification = classify_title(
            title
        )
'''

if old_create not in text:
    raise SystemExit("ERROR: create_dataframe marker not found")

text = text.replace(
    old_create,
    new_create,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print("PATCHED :", path)
print("BACKUP  :", backup)
