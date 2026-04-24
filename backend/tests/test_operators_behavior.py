"""
test_operators_behavior.py
驗證 cross_up / cross_down 實際偵測交叉的行為
（原 test_operators.py 只驗不汙染 DataFrame / 回傳型別，未驗偵測正確性）
"""
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.operators import cross_up, cross_down


# ──────────────────────────────────────────────
# 輔助 fixture
# ──────────────────────────────────────────────

def _df_two_rows(ticker: str, close_prev: float, close_today: float,
                 ma5_prev: float, ma5_today: float) -> pd.DataFrame:
    """建立兩天資料的 DataFrame（單一 ticker）"""
    return pd.DataFrame({
        "ticker_id": [ticker, ticker],
        "close": [close_prev, close_today],
        "ma5": [ma5_prev, ma5_today],
    })


def _df_three_rows(ticker: str, closes: list, ma5s: list) -> pd.DataFrame:
    """建立三天資料的 DataFrame（單一 ticker）"""
    return pd.DataFrame({
        "ticker_id": [ticker] * 3,
        "close": closes,
        "ma5": ma5s,
    })


# ──────────────────────────────────────────────
# CROSS_UP 測試
# ──────────────────────────────────────────────

class TestCrossUpDetection:

    def test_cross_up_detects_golden_cross(self):
        """前日 close < ma5、今日 close >= ma5 → 今日該 ticker 應為 True"""
        df = _df_two_rows("2330",
                          close_prev=99.0,  close_today=102.0,
                          ma5_prev=100.0,   ma5_today=100.0)
        result = cross_up(df, "close", "ma5")
        # 第一筆（index 0）無前日 → False；第二筆（index 1）→ True
        assert result.iloc[0] == False
        assert result.iloc[1] == True

    def test_cross_up_no_repeat_when_already_above(self):
        """連續兩天 close >= ma5 → 第二天不應再觸發交叉"""
        df = _df_three_rows("2330",
                            closes=[99.0, 105.0, 110.0],
                            ma5s=[100.0, 100.0, 100.0])
        result = cross_up(df, "close", "ma5")
        # index 1 第一次穿越 → True；index 2 仍在 ma5 之上 → False
        assert result.iloc[1] == True
        assert result.iloc[2] == False

    def test_cross_up_first_row_is_false(self):
        """第一筆資料沒有前日，不應視為交叉"""
        df = _df_two_rows("2330",
                          close_prev=99.0, close_today=105.0,
                          ma5_prev=100.0,  ma5_today=100.0)
        result = cross_up(df, "close", "ma5")
        assert result.iloc[0] == False

    def test_cross_up_no_cross_when_already_above_from_start(self):
        """前日已在 ma5 之上 → 今日不觸發交叉"""
        df = _df_two_rows("2330",
                          close_prev=105.0, close_today=108.0,
                          ma5_prev=100.0,   ma5_today=100.0)
        result = cross_up(df, "close", "ma5")
        assert result.iloc[1] == False

    def test_cross_up_multi_ticker_isolated(self):
        """2330 發生黃金交叉，不應影響 2317 的判斷（各 ticker 獨立 groupby）"""
        df = pd.DataFrame({
            "ticker_id": ["2330", "2330", "2317", "2317"],
            "close":     [99.0,  102.0,  120.0, 118.0],
            "ma5":       [100.0, 100.0,  115.0, 115.0],
        })
        result = cross_up(df, "close", "ma5")
        # 2330 index 1 → 交叉 True
        assert result.iloc[1] == True
        # 2317 index 3 → 前日 close(120) 已 > ma5(115)，不算交叉
        assert result.iloc[3] == False

    def test_cross_up_float_boundary(self):
        """99.99 < 100.0 → 100.01 >= 100.0 → 應觸發交叉"""
        df = _df_two_rows("1234",
                          close_prev=99.99, close_today=100.01,
                          ma5_prev=100.0,   ma5_today=100.0)
        result = cross_up(df, "close", "ma5")
        assert result.iloc[1] == True

    def test_cross_up_exactly_equal_today_triggers(self):
        """今日 close 剛好等於 ma5 時也算穿越（>= 條件）"""
        df = _df_two_rows("5566",
                          close_prev=99.0, close_today=100.0,
                          ma5_prev=100.0,  ma5_today=100.0)
        result = cross_up(df, "close", "ma5")
        assert result.iloc[1] == True

    def test_cross_up_with_scalar_target(self):
        """target 為純數值（float）時也能正確偵測穿越"""
        df = _df_two_rows("3008",
                          close_prev=49.0, close_today=51.0,
                          ma5_prev=50.0,   ma5_today=50.0)
        result = cross_up(df, "close", 50.0)
        assert result.iloc[1] == True

    def test_operator_does_not_mutate_df_double_check(self):
        """雙重保險：cross_up 執行後原 DataFrame 欄位數不變"""
        df = _df_two_rows("2330", 99.0, 102.0, 100.0, 100.0)
        cols_before = list(df.columns)
        cross_up(df, "close", "ma5")
        assert list(df.columns) == cols_before


# ──────────────────────────────────────────────
# CROSS_DOWN 測試
# ──────────────────────────────────────────────

class TestCrossDownDetection:

    def test_cross_down_detects_death_cross(self):
        """前日 close > ma5、今日 close <= ma5 → 今日應為 True"""
        df = _df_two_rows("2330",
                          close_prev=105.0, close_today=98.0,
                          ma5_prev=100.0,   ma5_today=100.0)
        result = cross_down(df, "close", "ma5")
        assert result.iloc[0] == False
        assert result.iloc[1] == True

    def test_cross_down_first_row_is_false(self):
        """第一筆資料無前日 → False"""
        df = _df_two_rows("2330",
                          close_prev=105.0, close_today=98.0,
                          ma5_prev=100.0,   ma5_today=100.0)
        result = cross_down(df, "close", "ma5")
        assert result.iloc[0] == False

    def test_cross_down_no_repeat_when_already_below(self):
        """連續兩天 close <= ma5 → 第二天不再觸發"""
        df = _df_three_rows("2330",
                            closes=[105.0, 95.0, 90.0],
                            ma5s=[100.0, 100.0, 100.0])
        result = cross_down(df, "close", "ma5")
        assert result.iloc[1] == True
        assert result.iloc[2] == False

    def test_cross_down_exactly_equal_today_triggers(self):
        """今日 close 等於 ma5 也算穿越（<= 條件）"""
        df = _df_two_rows("2330",
                          close_prev=105.0, close_today=100.0,
                          ma5_prev=100.0,   ma5_today=100.0)
        result = cross_down(df, "close", "ma5")
        assert result.iloc[1] == True

    def test_cross_down_with_scalar_target(self):
        """target 為純數值（float）時能正確偵測死亡交叉"""
        df = _df_two_rows("3008",
                          close_prev=51.0, close_today=49.0,
                          ma5_prev=50.0,   ma5_today=50.0)
        result = cross_down(df, "close", 50.0)
        assert result.iloc[1] == True

    def test_cross_down_does_not_mutate_df(self):
        """cross_down 執行後原 DataFrame 欄位數不變"""
        df = _df_two_rows("2317", 105.0, 98.0, 100.0, 100.0)
        cols_before = list(df.columns)
        cross_down(df, "close", "ma5")
        assert list(df.columns) == cols_before
