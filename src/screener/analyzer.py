import time
import pandas as pd

from services.yahoo_service import get_history
from indicators.technical import add_indicators

def calculate_initial_score(latest, credit_row=None):
    """
    初動スコア Ver3

    目的:
        「すでに大きく上昇した銘柄」ではなく、
        「上昇が始まったばかりの銘柄」を上位にする。

    基本方針:
        1. 出来高急増を重視
        2. ブレイク初日を最重要級に評価
        3. 30日高値更新を強く評価
        4. 前日比は補助評価に縮小
        5. 出来高増加日数は短いほど高評価
        6. 5日・20日の上昇が進みすぎた銘柄は減点
        7. MA・MACD・信用需給は補助材料
        8. RSIによる過熱減点は別処理

    点数は固定の満点を設けない。
    初動を捕まえるための相対評価を目的とする。
    """

    score = 0

    # ========================================================
    # 1. 出来高急増
    # ========================================================
    # 初動では「値上がり」よりも
    # 「資金が入り始めたこと」を重視する。
    # ========================================================

    volume_ratio = latest.get(
        "VolumeRatio",
        pd.NA
    )

    if pd.notna(volume_ratio):

        try:
            volume_ratio = float(volume_ratio)

            if volume_ratio >= 5.0:
                score += 5

            elif volume_ratio >= 3.0:
                score += 4

            elif volume_ratio >= 2.0:
                score += 3

            elif volume_ratio >= 1.5:
                score += 2

            elif volume_ratio >= 1.2:
                score += 1

        except Exception:
            pass

    # ========================================================
    # 2. 前日比
    # ========================================================
    # 前日比は「急騰した銘柄」を過大評価しない。
    #
    # +1～3%   → +1
    # +3～5%   → +2
    # +5%以上  → +2
    #
    # +10%、+20%でも追加点は与えない。
    # ========================================================

    change_percent = latest.get(
        "ChangePercent",
        pd.NA
    )

    if pd.notna(change_percent):

        try:
            change_percent = float(change_percent)

            if change_percent >= 3.0:
                score += 2

            elif change_percent >= 1.0:
                score += 1

        except Exception:
            pass

    # ========================================================
    # 3. ブレイクアウト
    # ========================================================

    breakout_signal = latest.get(
        "BreakoutSignal",
        False
    )

    breakout_first_day = latest.get(
        "BreakoutFirstDay",
        False
    )

    new_30_high = latest.get(
        "New30High",
        False
    )

    # ブレイクアウト発生
    if bool(breakout_signal):
        score += 2

    # ブレイク初日は最重要級
    if bool(breakout_first_day):
        score += 5

    # 30日高値更新
    if bool(new_30_high):
        score += 2

    # ========================================================
    # 4. 出来高増加日数
    # ========================================================
    # 初動では「出来高増加が始まったばかり」を評価。
    #
    # 1日 → +3
    # 2日 → +2
    # 3日 → +1
    # 4日以上 → 0
    #
    # 長期間出来高が増えている銘柄を
    # 初動として過大評価しない。
    # ========================================================

    volume_increase_days = latest.get(
        "VolumeIncreaseDays",
        0
    )

    if pd.notna(volume_increase_days):

        try:
            volume_increase_days = int(
                volume_increase_days
            )

            if volume_increase_days == 1:
                score += 3

            elif volume_increase_days == 2:
                score += 2

            elif volume_increase_days == 3:
                score += 1

        except Exception:
            pass

    # ========================================================
    # 5. 5日騰落率
    # ========================================================
    # ここは「初動からどれだけ進んでいるか」の減点。
    #
    # 5%未満   → 0
    # 5～10%   → -1
    # 10～20%  → -2
    # 20%以上  → -3
    # ========================================================

    change_5days = latest.get(
        "Change5Days",
        pd.NA
    )

    if pd.notna(change_5days):

        try:
            change_5days = float(
                change_5days
            )

            if change_5days >= 20.0:
                score -= 3

            elif change_5days >= 10.0:
                score -= 2

            elif change_5days >= 5.0:
                score -= 1

        except Exception:
            pass

    # ========================================================
    # 6. 20日騰落率
    # ========================================================
    # 中期的にすでに上がりすぎている銘柄を減点。
    #
    # 10%未満   → 0
    # 10～20%   → -1
    # 20～30%   → -2
    # 30%以上   → -3
    # ========================================================

    change_20days = latest.get(
        "Change20Days",
        pd.NA
    )

    if pd.notna(change_20days):

        try:
            change_20days = float(
                change_20days
            )

            if change_20days >= 30.0:
                score -= 3

            elif change_20days >= 20.0:
                score -= 2

            elif change_20days >= 10.0:
                score -= 1

        except Exception:
            pass

    # ========================================================
    # 7. MAトレンド
    # ========================================================
    # MAは初動判定の補助。
    # ========================================================

    if bool(
        latest.get(
            "AboveMA5",
            False
        )
    ):
        score += 1

    if bool(
        latest.get(
            "AboveMA25",
            False
        )
    ):
        score += 1

    if bool(
        latest.get(
            "AboveMA75",
            False
        )
    ):
        score += 1

    # ========================================================
    # 8. MACDゴールデンクロス
    # ========================================================

    if bool(
        latest.get(
            "MACD_GC",
            False
        )
    ):
        score += 2

    # ========================================================
    # 9. 信用需給
    # ========================================================

    if credit_row is not None:

        # ----------------------------------------------------
        # 信用倍率
        # ----------------------------------------------------

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
                score += 1

        except Exception:
            pass

        # ----------------------------------------------------
        # 売り残前週比
        # ----------------------------------------------------

        try:

            sell_change = float(
                str(
                    credit_row["売り残前週比"]
                ).replace(
                    ",",
                    ""
                )
            )

            if sell_change >= 10:
                score += 2

            elif sell_change >= 5:
                score += 1

        except Exception:
            pass

    return score


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
    initial_score,
    latest=None,
    credit_row=None
):

    comments = []

    comments.append(
        f"初動スコア{initial_score}点"
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
                ).replace(",", "")
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
                ).replace(",", "")
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
    # 基本スコアは15点満点。
    # RSIは基本スコアを変更せず、過熱時のみ減点する。
    # ========================================================

    judge_start = time.time()

    # 15点満点の原点スコア
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

    # コメントには原点スコアとRSI減点を残す
    analysis_comment = make_analysis_comment(
        initial_score,
        latest,
        credit_row
    )

    rsi_value = latest.get(
        "RSI",
        pd.NA
    )

    if pd.notna(rsi_value):

        try:

            rsi_value = float(rsi_value)

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
    # 重要：
    # 「強気度」は完全に廃止
    # 「初動スコア」を唯一のスコアとする
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
                if credit_row is not None
                and "日付" in credit_row
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
        # Sprint / 計測情報
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