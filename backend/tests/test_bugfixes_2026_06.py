"""
test_bugfixes_2026_06.py
驗證長期錯誤修復：
1. 漲停價浮點數計算錯誤 (floor 除法少一檔 → 漏判漲停)
2. 回測未計交易成本 (報酬率系統性高估)
3. RSI 統一為 Wilder 平滑、KD 統一為 9,3,3 (含 smooth_k)
4. 連 5 日平均漲幅在降序資料下取錯區間
5. 自訂公式名稱可覆蓋既有欄位 (毒化後續規則)
6. ScreenRequest 未強制規則/公式數量上限
7. 歷史日期查詢被 TWSE 最新快照誤標
8. 振幅/昨收除零防護
"""
import sys, os
import pandas as pd
import pytest
from decimal import Decimal, ROUND_FLOOR

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.high_turnover_analyzer import HighTurnoverAnalyzer
from services.backtest_engine import net_return_pct, FEE_RATE, TAX_RATE, BacktestEngine
from services.calculator import StockCalculator
from utils.indicators import wilder_rsi, stoch_kd
from app.engine.formula_parser import safe_eval_formula, validate_formula_name
from app.schemas.screen import ScreenRequest


# ──────────────────────────────────────────────
# 1. 漲停價計算
# ──────────────────────────────────────────────

class TestLimitUpPrice:
    analyzer = HighTurnoverAnalyzer()

    @pytest.mark.parametrize("prev_close,expected", [
        (5.0, 5.5),       # 舊版浮點 bug 算出 5.49
        (45.5, 50.0),     # 50.05 非 50–100 元區間合法檔位 → 取 50.0
        (2.5, 2.75),      # 舊版算出 2.74
        (10.0, 11.0),
        (50.0, 55.0),
        (96.0, 105.5),    # 105.6 → 0.5 檔位捨去 → 105.5
        (100.0, 110.0),
        (500.0, 550.0),
        (1000.0, 1100.0),
        (4.6, 5.06),      # 舊版算出 5.05
        (1.07, 1.17),     # ×1.1 產生千分位 1.177 → 捨去到 1.17
    ])
    def test_exact_tick_values(self, prev_close, expected):
        assert self.analyzer._calculate_limit_up_price(prev_close) == pytest.approx(expected)

    def test_full_sweep_against_decimal_reference(self):
        """1.00 ~ 1000.00 全價位掃描，與 Decimal 精確算法比對"""
        def reference(prev):
            raw = Decimal(str(prev)) * Decimal("1.10")
            if raw < 10:
                tick = Decimal("0.01")
            elif raw < 50:
                tick = Decimal("0.05")
            elif raw < 100:
                tick = Decimal("0.1")
            elif raw < 500:
                tick = Decimal("0.5")
            elif raw < 1000:
                tick = Decimal("1.0")
            else:
                tick = Decimal("5.0")
            return float((raw / tick).to_integral_value(rounding=ROUND_FLOOR) * tick)

        mismatches = []
        for i in range(100, 100001, 7):  # 步長 7 分，覆蓋各檔位區間
            prev = i / 100.0
            got = self.analyzer._calculate_limit_up_price(prev)
            want = reference(prev)
            if abs(got - want) > 1e-9:
                mismatches.append((prev, got, want))
        assert mismatches == []

    def test_is_limit_up_detects_true_limit(self):
        """昨收 5.00 漲停 5.50 — 舊版因算出 5.49 而漏判"""
        assert self.analyzer._is_limit_up(5.5, 5.0) is True
        assert self.analyzer._is_limit_up(50.0, 45.5) is True

    def test_is_limit_up_rejects_non_limit(self):
        assert self.analyzer._is_limit_up(5.4, 5.0) is False
        assert self.analyzer._is_limit_up(0, 5.0) is False
        assert self.analyzer._is_limit_up(5.5, 0) is False


# ──────────────────────────────────────────────
# 2. 回測交易成本
# ──────────────────────────────────────────────

class TestBacktestCosts:
    def test_gross_return_unchanged(self):
        assert net_return_pct(100, 110, include_costs=False) == pytest.approx(10.0)

    def test_net_return_includes_fee_and_tax(self):
        # 買 100：成本 100*(1+0.001425)=100.1425
        # 賣 110：淨收 110*(1-0.001425-0.003)=109.51325
        expected = (109.51325 - 100.1425) / 100.1425 * 100
        assert net_return_pct(100, 110, include_costs=True) == pytest.approx(expected)

    def test_flat_trade_is_negative_after_costs(self):
        """平盤出場含成本應為負報酬 (~ -0.585%)"""
        ret = net_return_pct(100, 100, include_costs=True)
        assert ret < 0
        assert ret == pytest.approx(-(FEE_RATE * 2 + TAX_RATE) * 100, abs=0.01)

    def test_profit_factor_in_stats(self):
        engine = BacktestEngine()
        signals = [
            {"returns": {1: 10.0}},
            {"returns": {1: 5.0}},
            {"returns": {1: -3.0}},
        ]
        stats = engine._calculate_stats(signals, [1])
        assert stats[0].profit_factor == pytest.approx(5.0)  # 15 / 3

    def test_profit_factor_none_when_no_losses(self):
        engine = BacktestEngine()
        signals = [{"returns": {1: 4.0}}, {"returns": {1: 2.0}}]
        stats = engine._calculate_stats(signals, [1])
        assert stats[0].profit_factor is None


# ──────────────────────────────────────────────
# 3. 指標：Wilder RSI / KD(9,3,3)
# ──────────────────────────────────────────────

class TestIndicators:
    def test_rsi_all_gains_is_100(self):
        closes = pd.Series(range(1, 31), dtype=float)
        rsi = wilder_rsi(closes)
        assert rsi.iloc[-1] == pytest.approx(100.0)

    def test_rsi_flat_is_50(self):
        closes = pd.Series([10.0] * 30)
        rsi = wilder_rsi(closes)
        assert rsi.iloc[-1] == pytest.approx(50.0)

    def test_rsi_uses_wilder_smoothing_not_sma(self):
        """交替漲跌序列：Wilder RSI 與 SMA (Cutler) RSI 必須可區分，且本實作為 Wilder"""
        vals = [100.0]
        for i in range(40):
            vals.append(vals[-1] + (3 if i % 2 == 0 else -1))
        closes = pd.Series(vals)

        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        # Wilder (RMA)
        ag_w = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        al_w = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        rsi_w = (100 - 100 / (1 + ag_w / al_w)).iloc[-1]
        # Cutler (SMA)
        ag_s = gain.rolling(14).mean()
        al_s = loss.rolling(14).mean()
        rsi_s = (100 - 100 / (1 + ag_s / al_s)).iloc[-1]

        got = wilder_rsi(closes).iloc[-1]
        assert got == pytest.approx(rsi_w)
        assert abs(got - rsi_s) > 1e-6  # 確認與 SMA 版可區分

    def test_kd_range_and_smoothing(self):
        import numpy as np
        rng = np.random.default_rng(42)
        n = 60
        close = pd.Series(100 + rng.normal(0, 1, n).cumsum())
        high = close + rng.uniform(0.1, 1.0, n)
        low = close - rng.uniform(0.1, 1.0, n)
        k, d = stoch_kd(high, low, close)
        valid_k = k.dropna()
        valid_d = d.dropna()
        assert len(valid_k) > 0 and len(valid_d) > 0
        assert ((valid_k >= 0) & (valid_k <= 100)).all()
        assert ((valid_d >= 0) & (valid_d <= 100)).all()
        # %K 經過 3 期平滑 → 第一個非 NaN 位置在 9+3-2=10 (index 10) 之後
        assert k.first_valid_index() == 10
        assert d.first_valid_index() == 12

    def test_kd_flat_window_yields_neutral_50(self):
        """連續一字線 (high==low) 區間為 0 → RSV 以 50 中性值取代，不產生 NaN/inf"""
        n = 20
        close = pd.Series([10.0] * n)
        high = pd.Series([10.0] * n)
        low = pd.Series([10.0] * n)
        k, _d = stoch_kd(high, low, close)
        assert k.dropna().iloc[-1] == pytest.approx(50.0)

    def test_technical_analyzer_kd_columns_unified(self):
        """get_indicators 與 kline 路徑都輸出 9,3,3 欄位"""
        from services.technical_analysis import TechnicalAnalyzer
        analyzer = TechnicalAnalyzer()
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=40).strftime("%Y-%m-%d"),
            "open": [100.0] * 40,
            "high": [101.0 + i * 0.1 for i in range(40)],
            "low": [99.0] * 40,
            "close": [100.0 + i * 0.1 for i in range(40)],
            "volume": [1000] * 40,
        })
        out1 = analyzer._calculate_indicators_manual(df.copy())
        out2 = analyzer._calculate_indicators_manual_full(df.copy())
        for out in (out1, out2):
            assert "STOCHk_9_3_3" in out.columns
            assert "STOCHd_9_3_3" in out.columns
            assert "STOCHk_14_3_3" not in out.columns
        # 兩路徑 KD 數值一致
        pd.testing.assert_series_equal(
            out1["STOCHk_9_3_3"], out2["STOCHk_9_3_3"], check_names=False
        )


# ──────────────────────────────────────────────
# 4. calculate_avg_change_5d 排序
# ──────────────────────────────────────────────

class TestAvgChange5d:
    def test_descending_input_uses_latest_5_days(self):
        """降序資料 (本服務慣例) 也要取「最近」5 日"""
        dates = pd.date_range("2026-01-01", periods=10).strftime("%Y-%m-%d")
        # 升序收盤: 100,101,...,109 → 最近5日漲幅約 1%/日
        df_desc = pd.DataFrame({
            "date": list(dates)[::-1],
            "close": list(range(109, 99, -1)),
            # 已含 change_percent (降序排列): 最新在前
            "change_percent": [1.0, 1.0, 1.0, 1.0, 1.0, 9.9, 9.9, 9.9, 9.9, 9.9],
        })
        result = StockCalculator.calculate_avg_change_5d(df_desc)
        # 升序後最後 5 筆 = 最新 5 筆 = 1.0 (舊版會抓到 9.9 那批)
        assert result == pytest.approx(1.0)

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({
            "date": ["2026-01-02", "2026-01-01"],
            "close": [101.0, 100.0],
        })
        snapshot = df.copy()
        StockCalculator.calculate_avg_change_5d(df)
        pd.testing.assert_frame_equal(df, snapshot)


# ──────────────────────────────────────────────
# 5. 公式名稱防護
# ──────────────────────────────────────────────

class TestFormulaNameProtection:
    def _df(self):
        return pd.DataFrame({"close": [10.0, 20.0], "ma5": [9.0, 19.0]})

    def test_overwriting_existing_field_rejected(self):
        with pytest.raises(ValueError, match="名稱"):
            safe_eval_formula(self._df(), "close", "ma5 * 0")

    def test_protected_meta_columns_rejected(self):
        for bad in ("ticker_id", "name", "date"):
            ok, _ = validate_formula_name(bad)
            assert ok is False

    def test_invalid_identifier_rejected(self):
        for bad in ("1abc", "a b", "", "x" * 33):
            ok, _ = validate_formula_name(bad)
            assert ok is False

    def test_valid_custom_name_accepted(self):
        df = safe_eval_formula(self._df(), "my_avg", "(close + ma5) / 2")
        assert "my_avg" in df.columns
        assert df["my_avg"].iloc[0] == pytest.approx(9.5)


# ──────────────────────────────────────────────
# 6. ScreenRequest 數量上限
# ──────────────────────────────────────────────

class TestScreenRequestCaps:
    def _rule(self):
        return {
            "type": "indicator", "field": "close", "operator": ">",
            "target_type": "value", "target_value": 100,
        }

    def test_rules_within_cap_ok(self):
        req = ScreenRequest(rules=[self._rule()] * 32)
        assert len(req.rules) == 32

    def test_rules_over_cap_rejected(self):
        with pytest.raises(ValueError):
            ScreenRequest(rules=[self._rule()] * 33)

    def test_formulas_over_cap_rejected(self):
        f = {"name": "f1", "formula": "close + 1"}
        with pytest.raises(ValueError):
            ScreenRequest(custom_formulas=[f] * 9)


# ──────────────────────────────────────────────
# 7. 歷史日期不可被最新快照誤標
# ──────────────────────────────────────────────

class TestHistoricalDateIntegrity:
    @pytest.mark.asyncio
    async def test_historical_query_prefers_db(self, monkeypatch):
        from services.data_fetcher import DataFetcher
        fetcher = DataFetcher()

        db_df = pd.DataFrame([{
            "stock_id": f"{2000 + i}",
            "Trading_Volume": 1_000_000,
            "open": 100.0,
            "max": 101.0,
            "min": 99.0,
            "close": 100.5,
            "spread": 0.5,
            "date": "2026-05-04",
        } for i in range(501)])

        async def fake_db(target_date):
            assert target_date == "2026-05-04"
            return db_df

        monkeypatch.setattr(fetcher, "get_daily_from_db", fake_db)

        called = {"twse": False}

        async def fake_twse(trade_date):
            called["twse"] = True
            return pd.DataFrame()

        monkeypatch.setattr(fetcher, "_fetch_twse_daily_openapi", fake_twse)

        # 清掉殘留快取避免互相影響
        from services.cache_manager import cache_manager
        cache_manager.delete("daily_2026-05-04", "daily")

        df = await fetcher.get_daily_data("2026-05-04")
        assert not df.empty
        assert df["date"].iloc[0] == "2026-05-04"
        assert called["twse"] is False  # 歷史日有 DB 資料就不打 TWSE

        cache_manager.delete("daily_2026-05-04", "daily")


# ──────────────────────────────────────────────
# 8. 振幅/昨收除零防護 (stock_filter._apply_filters)
# ──────────────────────────────────────────────

class TestApplyFiltersSafety:
    def _params(self, **overrides):
        from schemas.stock import StockFilterParams
        base = dict(page=1, page_size=50)
        base.update(overrides)
        return StockFilterParams(**base)

    def test_amplitude_filter_excludes_zero_prev_close(self):
        from services.stock_filter import StockFilter
        sf = StockFilter()
        df = pd.DataFrame([
            # 正常: 昨收 100, 振幅 5%
            {"stock_id": "1101", "close": 102.0, "spread": 2.0,
             "max": 104.0, "min": 99.0, "Trading_Volume": 2_000_000},
            # 異常: spread == close → 昨收 0，不可除以零，應被排除
            {"stock_id": "9999", "close": 5.0, "spread": 5.0,
             "max": 5.5, "min": 4.5, "Trading_Volume": 2_000_000},
        ])
        out = sf._apply_filters(df, self._params(amplitude_min=1.0, exclude_etf=False))
        assert "1101" in out["stock_id"].values
        assert "9999" not in out["stock_id"].values

    def test_close_above_prev_zero_prev_excluded(self):
        from services.stock_filter import StockFilter
        sf = StockFilter()
        df = pd.DataFrame([
            {"stock_id": "1101", "close": 102.0, "spread": 2.0,
             "max": 104.0, "min": 99.0, "Trading_Volume": 2_000_000},
            {"stock_id": "9999", "close": 5.0, "spread": 5.0,
             "max": 5.5, "min": 4.5, "Trading_Volume": 2_000_000},
        ])
        out = sf._apply_filters(
            df, self._params(close_above_prev_min=0.5, exclude_etf=False)
        )
        assert "1101" in out["stock_id"].values
        assert "9999" not in out["stock_id"].values
