from datetime import datetime

import yfinance as yf
import pandas as pd


CODES = [
    "7203",  # Toyota
    "4420",  # eSOL
    "336A",
    "4707",
]


def main():

    print("=" * 70)
    print("Yahoo morning 1d value test")
    print("=" * 70)

    print(
        "Fetch time :",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print()

    tickers = [
        f"{code}.T"
        for code in CODES
    ]

    raw = yf.download(
        tickers=tickers,
        period="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    for code in CODES:

        ticker = f"{code}.T"

        print("-" * 70)
        print("Code :", code)

        try:

            if isinstance(
                raw.columns,
                pd.MultiIndex
            ):

                level0 = (
                    raw.columns
                    .get_level_values(0)
                )

                level1 = (
                    raw.columns
                    .get_level_values(1)
                )

                if ticker in level0:
                    df = raw[
                        ticker
                    ].copy()

                elif ticker in level1:
                    df = raw.loc[
                        :,
                        ticker
                    ].copy()

                else:
                    print(
                        "No ticker data"
                    )
                    continue

            else:
                df = raw.copy()

            df = df.dropna(
                how="all"
            )

            if df.empty:
                print(
                    "EMPTY"
                )
                continue

            print(
                df.to_string()
            )

        except Exception as e:

            print(
                "ERROR :",
                e
            )


if __name__ == "__main__":
    main()