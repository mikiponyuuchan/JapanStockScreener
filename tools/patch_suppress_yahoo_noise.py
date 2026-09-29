from pathlib import Path

files = [
    Path("src/services/tracking_service.py"),
    Path("tools/create_short_sale_trigger_rebound_ver1.py"),
]

for path in files:
    text = path.read_text(encoding="utf-8")

    if "import io" not in text:
        text = "import io\n" + text

    if "redirect_stderr" not in text:
        if "from contextlib import redirect_stdout" in text:
            text = text.replace(
                "from contextlib import redirect_stdout",
                "from contextlib import redirect_stdout, redirect_stderr",
            )
        else:
            text = (
                "from contextlib import redirect_stdout, redirect_stderr\n"
                + text
            )

    if path.name == "tracking_service.py":
        text = text.replace(
            "with redirect_stdout(io.StringIO()):",
            "with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):",
        )

    if path.name == "create_short_sale_trigger_rebound_ver1.py":
        old = '''    try:
        df = yf.download(
            f"{code}.T",'''

        new = '''    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            df = yf.download(
                f"{code}.T",'''

        if old not in text:
            raise RuntimeError(
                "SSR yf.download block not found; no changes written."
            )

        text = text.replace(old, new, 1)

        # yf.download arguments now need one extra indentation level.
        start_marker = '''            df = yf.download(
                f"{code}.T",'''
        start_pos = text.find(start_marker)

        if start_pos < 0:
            raise RuntimeError("SSR replacement verification failed.")

        close_marker = '''            threads=False,
        )'''
        close_pos = text.find(close_marker, start_pos)

        if close_pos < 0:
            raise RuntimeError("SSR download closing block not found.")

        block_end = close_pos + len(close_marker)
        block = text[start_pos:block_end]

        lines = block.splitlines()
        fixed = [lines[0]]
        fixed.extend("    " + line for line in lines[1:])

        text = (
            text[:start_pos]
            + "\n".join(fixed)
            + text[block_end:]
        )

    path.write_text(
        text,
        encoding="utf-8",
    )

    print("PATCHED :", path)

print("COMPLETE")
