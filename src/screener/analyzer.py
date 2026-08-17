import time

import pandas as pd

from services.yahoo_service import get_history
from indicators.technical import add_indicators


# ================================================
# 初動スコア Ver4
# ================================================

def calculate_initial_score(latest, credit_row=None):
    """
    初動スコア Ver4

    コア4条件のみで加点する。

    前日比+5%以上       : +3
    出来高3倍以上       : +2
    ブレイク            : +1
    30日高値更新        : +1

    コア最大 : 7点

    RSIによる減点はこの関数では行わない。
    calculate_rsi_penalty() で別途処理する。

    強気度・信用需給・MA・MACD・5日騰落率・20日騰落率
    などはスコアに使用しない。
    """

    score = 0

    # ========================================
    # 1. 前日比 +5%以上
    # ========================================

    change_percent = latest.get(
        "ChangePercent",
        pd.NA
    )

    if pd.notna(change_percent):

        try:

            change_percent = float(
                change_percent
            )

            if change_percent >= 5.0:
                score += 3

        except Exception:
            pass

    # ========================================
    # 2. 出来高3倍以上
    # ========================================

    volume_ratio = latest.get(
        "VolumeRatio",
        pd.NA
    )

    if pd.notna(volume_ratio):

        try:

            volume_ratio = float(
                volume_ratio
            )

            if volume_ratio >= 3.0:
                score += 2

        except Exception:
            pass

    # ========================================
    # 3. ブレイク
    # ========================================
    #
    # BreakoutSignalのみを使用。
    # BreakoutFirstDayは別加点しない。
    # ========================================

    breakout_signal = latest.get(
        "BreakoutSignal",
        False
    )

    if bool(breakout_signal):
        score += 1

    # ========================================
    # 4. 30日高値更新
    # ========================================

    new_30_high = latest.get(
        "New30High",
        False
    )

    if bool(new_30_high):
        score += 1

    # ========================================
    # コア最大7点
    # ========================================

    return score

# ============================================================
# RSI過熱減点
# ============================================================

def calculate_rsi_penalty(latest):
    """
    RSIによる過熱減点

    RSI <= 84.99 :  0点
    RSI 85-89.99 : -1点
    RSI 90-94.99 : -2点
    RSI >= 95    : -3点
    """

    rsi = latest.get(
        "RSI",
        pd.NA
    )

    if pd.isna(rsi):
        return 0

    try:

        rsi = float(rsi)

        if rsi >= 95:
            return -3

        elif rsi >= 90:
            return -2

        elif rsi >= 85:
            return -1

    except Exception:
        pass

    return 0


# ============================================================
# 初動スコアコメント
# ============================================================

def make_analysis_comment(
    final_score,
    latest=None,
    credit_row=None
):

    comments = []

    comments.append(
        f"初動スコア{final_score}点"
    )

    if latest is not None:

        # ----------------------------------------------------
        # 出来高
        # ----------------------------------------------------

        volume_ratio = latest.get(
            "VolumeRatio",
            pd.NA
        )

        if pd.notna(volume_ratio):

            try:

                volume_ratio = float(
                    volume_ratio
                )

                if volume_ratio >= 2:

                    comments.append(
                        f"出来高{volume_ratio:.1f}倍"
                    )

                elif volume_ratio >= 1.5:

                    comments.append(
                        f"出来高{volume_ratio:.1f}倍"
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # 当日上昇
        # ----------------------------------------------------

        change_percent = latest.get(
            "ChangePercent",
            pd.NA
        )

        if pd.notna(change_percent):

            try:

                change_percent = float(
                    change_percent
                )

                if change_percent >= 1:

                    comments.append(
                        f"当日+{change_percent:.1f}%"
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # MA5
        # ----------------------------------------------------

        if latest.get(
            "AboveMA5",
            False
        ):

            comments.append(
                "5日線上"
            )

        # ----------------------------------------------------
        # 初動シグナル
        # ----------------------------------------------------

        if latest.get(
            "InitialMoveSignal",
            False
        ):

            comments.append(
                "初動シグナル"
            )

        # ----------------------------------------------------
        # 押し目
        # ----------------------------------------------------

        if latest.get(
            "PullbackSignal",
            False
        ):

            comments.append(
                "押し目判定"
            )

        # ----------------------------------------------------
        # MACD GC
        # ----------------------------------------------------

        if latest.get(
            "MACD_GC",
            False
        ):

            comments.append(
                "MACD GC"
            )

        # ----------------------------------------------------
        # 30日高値
        # ----------------------------------------------------

        if latest.get(
            "New30High",
            False
        ):

            comments.append(
                "30日高値更新"
            )

        # ----------------------------------------------------
        # 年初来高値
        # ----------------------------------------------------

        if latest.get(
            "NewYearHigh",
            False
        ):

            comments.append(
                "年初来高値更新"
            )

        # ----------------------------------------------------
        # ブレイク
        # ----------------------------------------------------

        if latest.get(
            "BreakoutSignal",
            False
        ):

            comments.append(
                "ブレイクアウト"
            )

        # ----------------------------------------------------
        # 5日騰落率
        # ----------------------------------------------------

        change_5days = latest.get(
            "Change5Days",
            pd.NA
        )

        if pd.notna(change_5days):

            try:

                change_5days = float(
                    change_5days
                )

                if change_5days >= 5:

                    comments.append(
                        f"5日+{change_5days:.1f}%"
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # 20日騰落率
        # ----------------------------------------------------

        change_20days = latest.get(
            "Change20Days",
            pd.NA
        )

        if pd.notna(change_20days):

            try:

                change_20days = float(
                    change_20days
                )

                if change_20days >= 10:

                    comments.append(
                        f"20日+{change_20days:.1f}%"
                    )

            except Exception:
                pass

    # ========================================================
    # 信用情報
    # ========================================================

    if credit_row is not None:

        try:

            credit_ratio = float(
                str(
                    credit_row["信用倍率"]
                ).replace(
                    ",",
                    ""
                )
            )

            if credit_ratio < 1:

                comments.append(
                    "信用倍率1倍未満"
                )

            elif credit_ratio < 2:

                comments.append(
                    "信用倍率2倍未満"
                )

        except Exception:
            pass

        try:

            sell_change = float(
                str(
                    credit_row["売り残前週比"]
                ).replace(
                    ",",
                    ""
                )
            )

            if sell_change >= 5:

                comments.append(
                    f"売り残+{sell_change:.1f}%"
                )

        except Exception:
            pass

    return " / ".join(comments)


# ============================================================
# 銘柄分析
# ============================================================

def analyze_stock(
    stock,
    history_df=None,
    credit_row=None
):

    # ========================================================
    # 基本情報
    # ========================================================

    code = str(
        stock["コード"]
    )

    name = stock.get(
        "銘柄名",
        ""
    )

    market = stock.get(
        "市場・商品区分",
        ""
    )

    # ========================================================
    # データ取得
    # ========================================================

    data_start = time.time()

    if history_df is not None:

        df = history_df

    else:

        df = get_history(
            code
        )

    data_time = (
        time.time()
        - data_start
    )

    if df is None or df.empty:

        return None

    # ========================================================
    # テクニカル指標
    # ========================================================

    indicator_start = time.time()

    df = add_indicators(
        df
    )

    indicator_time = (
        time.time()
        - indicator_start
    )

    if df is None or df.empty:

        return None

    # ========================================================
    # 最新行
    # ========================================================

    latest = df.iloc[-1]

    # ========================================================
    # 信用情報
    # ========================================================

    credit_ratio = pd.NA
    credit_condition = "未判定"

    credit_sell = pd.NA
    credit_buy = pd.NA
    credit_sell_change = pd.NA
    credit_buy_change = pd.NA

    if credit_row is not None:

        # ----------------------------------------------------
        # 売り残
        # ----------------------------------------------------

        try:

            credit_sell = pd.to_numeric(
                credit_row.get(
                    "売残",
                    pd.NA
                ),
                errors="coerce"
            )

        except Exception:

            credit_sell = pd.NA

        # ----------------------------------------------------
        # 買い残
        # ----------------------------------------------------

        try:

            credit_buy = pd.to_numeric(
                credit_row.get(
                    "買残",
                    pd.NA
                ),
                errors="coerce"
            )

        except Exception:

            credit_buy = pd.NA

        # ----------------------------------------------------
        # 売り残前週比
        # ----------------------------------------------------

        try:

            credit_sell_change = pd.to_numeric(
                credit_row.get(
                    "売残前週比",
                    pd.NA
                ),
                errors="coerce"
            )

        except Exception:

            credit_sell_change = pd.NA

        # ----------------------------------------------------
        # 買い残前週比
        # ----------------------------------------------------

        try:

            credit_buy_change = pd.to_numeric(
                credit_row.get(
                    "買残前週比",
                    pd.NA
                ),
                errors="coerce"
            )

        except Exception:

            credit_buy_change = pd.NA

        # ----------------------------------------------------
        # Yahoo取得の信用倍率
        # ----------------------------------------------------

        try:

            credit_ratio = pd.to_numeric(
                credit_row.get(
                    "信用倍率",
                    pd.NA
                ),
                errors="coerce"
            )

        except Exception:

            credit_ratio = pd.NA

        # ----------------------------------------------------
        # 信用条件
        #
        # 信用倍率 < 1
        # かつ
        # 売り残前週比 > 0
        #
        # の場合のみ「該当」
        # ----------------------------------------------------

        try:

            ratio_for_condition = credit_ratio

            if (
                pd.notna(ratio_for_condition)
                and
                pd.notna(credit_sell_change)
            ):

                if (
                    float(ratio_for_condition) < 1
                    and
                    float(credit_sell_change) > 0
                ):

                    credit_condition = "該当"

                else:

                    credit_condition = ""

            else:

                credit_condition = "未判定"

        except (
            TypeError,
            ValueError,
        ):

            credit_condition = "未判定"

    # ========================================================
    # 初動スコア
    #
    # 基本スコアを計算。
    # RSIは基本スコアを変更せず、
    # 過熱時のみ減点する。
    # ========================================================

    judge_start = time.time()

    # 基本初動スコア
    initial_score = calculate_initial_score(
        latest,
        credit_row
    )

    # RSIによる過熱減点
    rsi_penalty = calculate_rsi_penalty(
        latest
    )

    # 最終初動スコア
    final_score = initial_score + rsi_penalty

    # コメントには基本スコアを表示
    analysis_comment = make_analysis_comment(
        final_score,
        latest,
        credit_row
    )

    rsi_value = latest.get(
        "RSI",
        pd.NA
    )

    if pd.notna(rsi_value):

        try:

            rsi_value = float(
                rsi_value
            )

            if rsi_penalty < 0:

                analysis_comment += (
                    f" / RSI{rsi_value:.2f}"
                    f" / RSI減点{rsi_penalty}点"
                    f" / 最終初動スコア{final_score}点"
                )

        except Exception:
            pass

    judge_time = (
        time.time()
        - judge_start
    )

    # ========================================================
    # 終値
    #
    # main.py / tracking_service.py / result_writer.py
    # が使用する正式な列名
    # ========================================================

    try:

        close_price = round(
            float(
                latest["Close"]
            ),
            2
        )

    except Exception:

        return None

    # ========================================================
    # データ日
    # ========================================================

    try:

        if "Date" in df.columns:

            data_date = (
                pd.to_datetime(
                    df["Date"]
                )
                .max()
                .strftime(
                    "%Y-%m-%d"
                )
            )

        else:

            data_date = (
                pd.to_datetime(
                    df.index
                )
                .max()
                .strftime(
                    "%Y-%m-%d"
                )
            )

    except Exception:

        data_date = ""

    # ========================================================
    # 結果
    #
    # 重要:
    # 「強気度」は完全に廃止。
    # 「初動スコア」を唯一のスコアとする。
    # ========================================================

    return {

        # ----------------------------------------------------
        # 基本情報
        # ----------------------------------------------------

        "コード":
            code,

        "銘柄名":
            name,

        "市場":
            market,

        # ----------------------------------------------------
        # 株価
        # ----------------------------------------------------

        "終値":
            close_price,

        "前日比":
            latest.get(
                "ChangePercent",
                pd.NA
            ),

        "5日騰落率":
            latest.get(
                "Change5Days",
                pd.NA
            ),

        "20日騰落率":
            latest.get(
                "Change20Days",
                pd.NA
            ),

        # ----------------------------------------------------
        # テクニカル
        # ----------------------------------------------------

        "RSI":
            latest.get(
                "RSI",
                pd.NA
            ),

        "ATR":
            latest.get(
                "ATR",
                pd.NA
            ),

        # ----------------------------------------------------
        # 初動スコア
        # ----------------------------------------------------

        "基本初動スコア":
            initial_score,

        "RSI減点":
            rsi_penalty,

        "初動スコア":
            final_score,

        "分析コメント":
            analysis_comment,

        # ----------------------------------------------------
        # 初動判定用
        # ----------------------------------------------------

        "InitialMoveSignal":
            latest.get(
                "InitialMoveSignal",
                False
            ),

        "PullbackSignal":
            latest.get(
                "PullbackSignal",
                False
            ),

        "BreakoutSignal":
            latest.get(
                "BreakoutSignal",
                False
            ),

        "BreakoutFirstDay":
            latest.get(
                "BreakoutFirstDay",
                False
            ),

        "MACD_GC":
            latest.get(
                "MACD_GC",
                False
            ),

        "New30High":
            latest.get(
                "New30High",
                False
            ),

        "NewYearHigh":
            latest.get(
                "NewYearHigh",
                False
            ),

        # ----------------------------------------------------
        # 出来高
        # ----------------------------------------------------

        "VolumeRatio":
            latest.get(
                "VolumeRatio",
                pd.NA
            ),

        "VolumeRatio20":
            latest.get(
                "VolumeRatio20",
                pd.NA
            ),

        "VolumeIncreaseDays":
            latest.get(
                "VolumeIncreaseDays",
                0
            ),

        # ----------------------------------------------------
        # トレンド
        # ----------------------------------------------------

        "AboveMA5":
            latest.get(
                "AboveMA5",
                False
            ),

        "AboveMA25":
            latest.get(
                "AboveMA25",
                False
            ),

        "AboveMA75":
            latest.get(
                "AboveMA75",
                False
            ),

        "TrendEvaluation":
            latest.get(
                "TrendEvaluation",
                ""
            ),

        "MAAlignment":
            latest.get(
                "MAAlignment",
                ""
            ),

        # ----------------------------------------------------
        # RSI / 連騰
        # ----------------------------------------------------

        "RSI_Strong":
            latest.get(
                "RSI_Strong",
                False
            ),

        "ConsecutiveUpDays":
            latest.get(
                "ConsecutiveUpDays",
                0
            ),

        # ----------------------------------------------------
        # MA25乖離
        # ----------------------------------------------------

        "MA25Deviation":
            latest.get(
                "MA25Deviation",
                pd.NA
            ),

        # ----------------------------------------------------
        # 信用情報
        # ----------------------------------------------------

        "信用情報日付":
            (
                credit_row["日付"]
                if (
                    credit_row is not None
                    and
                    "日付" in credit_row
                )
                else pd.NA
            ),

        "売残":
            credit_sell,

        "買残":
            credit_buy,

        "売残前週比":
            credit_sell_change,

        "買残前週比":
            credit_buy_change,

        "信用倍率":
            credit_ratio,

        "信用条件":
            credit_condition,

        # ----------------------------------------------------
        # 計測情報
        # ----------------------------------------------------

        "_data_date":
            data_date,

        "_data_time":
            data_time,

        "_indicator_time":
            indicator_time,

        "_judge_time":
            judge_time,
    }