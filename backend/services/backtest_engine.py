"""
Backtest Engine - Backtest trading strategies
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio
import logging
import json

from services.data_fetcher import data_fetcher
from services.stock_filter import stock_filter
from schemas.backtest import BacktestRequest, BacktestStats, BacktestResponse
from schemas.stock import StockFilterParams

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Engine for backtesting stock filter strategies"""
    
    def __init__(self):
        self.data_fetcher = data_fetcher
        self.stock_filter = stock_filter

    async def run_backtest(self, request: BacktestRequest) -> BacktestResponse:
        """
        Run a backtest.

        Prefer the v1 DB (daily_prices) which holds correct per-date history.
        The legacy path filters each date via get_daily_data, which returns the
        latest TWSE snapshot regardless of the queried date, so historical
        signals collapse to one day — it is used only when the DB has no data
        in range (cold DB / out-of-range request).
        """
        try:
            max_hold = max(request.holding_days) if request.holding_days else 10
            df = await self._load_range_from_db(request.start_date, request.end_date, max_hold)
        except Exception as e:
            logger.warning(f"Backtest DB load failed ({e}); falling back to legacy path")
            df = pd.DataFrame()

        if not df.empty:
            return await asyncio.to_thread(self._compute_from_df, df, request)
        return await self._run_backtest_legacy(request)

    async def _load_range_from_db(
        self, start_date: str, end_date: str, max_holding: int
    ) -> pd.DataFrame:
        """
        Load all daily_prices in [start_date, end_date + holding window] from the
        v1 DB, joined with ticker name/industry. Returns columns:
        stock_id, date(str YYYY-MM-DD), open, high, low, close, volume,
        change_percent, industry, name. Empty DataFrame if nothing in range.
        """
        from database import async_session_maker
        from app.models.daily_price import DailyPrice
        from app.models.ticker import Ticker
        from sqlalchemy import select

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return pd.DataFrame()

        # Buffer days BEFORE start give a prev close for day-over-day change% on the
        # first signal day; extra days AFTER end cover the forward-return window.
        load_start = start - timedelta(days=15)
        ext_end = end + timedelta(days=max_holding * 2 + 21)

        async with async_session_maker() as session:
            rows = (await session.execute(
                select(
                    DailyPrice.ticker_id, DailyPrice.date,
                    DailyPrice.open, DailyPrice.high, DailyPrice.low,
                    DailyPrice.close, DailyPrice.volume, DailyPrice.change_percent,
                    Ticker.industry, Ticker.name,
                )
                .join(Ticker, Ticker.ticker_id == DailyPrice.ticker_id)
                .where(DailyPrice.date >= load_start, DailyPrice.date <= ext_end)
                .order_by(DailyPrice.ticker_id, DailyPrice.date)
            )).fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r._mapping) for r in rows])
        df["stock_id"] = df["ticker_id"].astype(str)
        df["date"] = df["date"].astype(str).str.slice(0, 10)
        return df

    def _filter_day(self, day: pd.DataFrame, request: BacktestRequest) -> pd.DataFrame:
        """Apply backtest filter criteria to a single trading day's rows."""
        if request.exclude_etf:
            day = day[~day["stock_id"].str.startswith("00")]

        cp = pd.to_numeric(day["_chg"], errors="coerce")
        # NaN change (no prev close) fails the comparison and is excluded (no signal)
        day = day[(cp >= request.change_min) & (cp <= request.change_max)]

        lots = pd.to_numeric(day["volume"], errors="coerce").fillna(0) // 1000
        vmask = lots >= request.volume_min
        if request.volume_max is not None:
            vmask = vmask & (lots <= request.volume_max)
        day = day[vmask]

        if request.price_min is not None:
            day = day[day["close"] >= request.price_min]
        if request.price_max is not None:
            day = day[day["close"] <= request.price_max]
        if request.industries:
            day = day[day["industry"].isin(request.industries)]
        return day

    def _forward_returns_from_df(
        self, signals: List[Dict], df: pd.DataFrame, holding_days: List[int]
    ) -> List[Dict]:
        """Compute forward returns for each signal using the loaded range data."""
        by_sym: Dict[str, list] = {}
        for sym, g in df.groupby("stock_id"):
            g2 = g.sort_values("date")
            by_sym[str(sym)] = list(zip(g2["date"].tolist(), g2["close"].tolist()))

        for sig in signals:
            series = by_sym.get(sig["symbol"], [])
            entry_date = sig["entry_date"]
            entry_price = sig["entry_price"]
            future = [c for (d, c) in series if d > entry_date]
            sig["returns"] = {}
            for days in holding_days:
                if len(future) >= days:
                    exit_price = future[days - 1]
                    if exit_price is not None and not pd.isna(exit_price) and exit_price > 0:
                        sig["returns"][days] = round((exit_price - entry_price) / entry_price * 100, 2)
        return signals

    def _compute_from_df(self, df: pd.DataFrame, request: BacktestRequest) -> BacktestResponse:
        """Build the full backtest response from v1 DB range data (CPU-bound, sync)."""
        df = df.sort_values(["stock_id", "date"]).reset_index(drop=True)
        # Day-over-day change% from each stock's own close series. Robust to the
        # sparsely-populated stored change_percent column; rows are consecutive
        # trading days (holidays/weekends are simply absent), so pct_change is
        # the change vs the previous trading day.
        df["_chg"] = pd.to_numeric(df["close"], errors="coerce").groupby(df["stock_id"]).pct_change() * 100

        name_map = dict(zip(df["stock_id"], df["name"])) if "name" in df.columns else {}

        signal_dates = sorted(
            d for d in df["date"].unique()
            if request.start_date <= d <= request.end_date
        )

        signals: List[Dict] = []
        for d in signal_dates:
            day = self._filter_day(df[df["date"] == d], request)
            for _, r in day.iterrows():
                ep = r["close"]
                if ep is None or pd.isna(ep) or ep <= 0:
                    continue
                cp = r["_chg"]
                signals.append({
                    "symbol": str(r["stock_id"]),
                    "name": name_map.get(str(r["stock_id"]), str(r["stock_id"])),
                    "entry_date": d,
                    "entry_price": float(ep),
                    "change_percent": float(cp) if pd.notna(cp) else 0.0,
                })

        if not signals:
            return BacktestResponse(
                total_signals=0, unique_stocks=0, stats=[],
                overall_win_rate=0, overall_avg_return=0,
                start_date=request.start_date, end_date=request.end_date,
                trading_days=len(signal_dates), return_distribution={},
            )

        signals = self._forward_returns_from_df(signals, df, request.holding_days)
        stats = self._calculate_stats(signals, request.holding_days)
        one_day = next((s for s in stats if s.holding_days == 1), None)

        return BacktestResponse(
            total_signals=len(signals),
            unique_stocks=len({s["symbol"] for s in signals}),
            stats=stats,
            overall_win_rate=one_day.win_rate if one_day else 0,
            overall_avg_return=one_day.avg_return if one_day else 0,
            start_date=request.start_date,
            end_date=request.end_date,
            trading_days=len(signal_dates),
            return_distribution=self._get_return_distribution(signals),
        )

    async def _run_backtest_legacy(self, request: BacktestRequest) -> BacktestResponse:
        """
        Legacy backtest path (FinMind + stock_filter). Fallback only — historical
        filtering is approximate because get_daily_data returns the latest TWSE
        snapshot regardless of the queried date.

        Run backtest for given filter conditions

        Args:
            request: Backtest parameters including date range and filter conditions
        """
        # Get all trading days in range
        all_data = await self.data_fetcher.get_date_range_data(
            request.start_date,
            request.end_date
        )
        
        if all_data.empty:
            return BacktestResponse(
                total_signals=0,
                unique_stocks=0,
                stats=[],
                overall_win_rate=0,
                overall_avg_return=0,
                start_date=request.start_date,
                end_date=request.end_date,
                trading_days=0
            )
        
        # Get unique trading days
        trading_dates = sorted(all_data["date"].unique())
        
        # Find signals for each day
        signals = []
        
        for trade_date in trading_dates:
            filter_params = StockFilterParams(
                date=str(trade_date),
                change_min=request.change_min,
                change_max=request.change_max,
                volume_min=request.volume_min,
                volume_max=request.volume_max,
                price_min=request.price_min,
                price_max=request.price_max,
                consecutive_up_min=request.consecutive_up_min,
                industries=request.industries,
                exclude_etf=request.exclude_etf,
                page=1,
                page_size=200
            )
            
            result = await self.stock_filter.filter_stocks(filter_params)
            
            for item in result.get("items", []):
                signals.append({
                    "symbol": item["symbol"],
                    "name": item.get("name", ""),
                    "entry_date": str(trade_date),
                    "entry_price": item.get("close_price", 0),
                    "change_percent": item.get("change_percent", 0)
                })
        
        if not signals:
            return BacktestResponse(
                total_signals=0,
                unique_stocks=0,
                stats=[],
                overall_win_rate=0,
                overall_avg_return=0,
                start_date=request.start_date,
                end_date=request.end_date,
                trading_days=len(trading_dates)
            )
        
        # Calculate forward returns for each signal
        signals_with_returns = await self._calculate_forward_returns(
            signals, 
            request.holding_days
        )
        
        # Calculate statistics
        stats = self._calculate_stats(signals_with_returns, request.holding_days)
        
        # Calculate overall metrics
        unique_stocks = len(set(s["symbol"] for s in signals))
        
        # Get 1-day stats for overall metrics
        one_day_stats = next((s for s in stats if s.holding_days == 1), None)
        overall_win_rate = one_day_stats.win_rate if one_day_stats else 0
        overall_avg = one_day_stats.avg_return if one_day_stats else 0
        
        # Return distribution for histogram
        return_distribution = self._get_return_distribution(signals_with_returns)
        
        return BacktestResponse(
            total_signals=len(signals),
            unique_stocks=unique_stocks,
            stats=stats,
            overall_win_rate=overall_win_rate,
            overall_avg_return=overall_avg,
            start_date=request.start_date,
            end_date=request.end_date,
            trading_days=len(trading_dates),
            return_distribution=return_distribution
        )
    
    async def _calculate_forward_returns(
        self,
        signals: List[Dict],
        holding_days: List[int]
    ) -> List[Dict]:
        """Calculate forward returns for each signal"""
        
        results = []
        max_holding = max(holding_days)
        
        # Get extended end date for forward returns
        end_date = datetime.strptime(signals[-1]["entry_date"], "%Y-%m-%d")
        extended_end = (end_date + timedelta(days=max_holding + 30)).strftime("%Y-%m-%d")
        start_date = signals[0]["entry_date"]
        
        # Fetch all data at once
        all_data = await self.data_fetcher.get_date_range_data(start_date, extended_end)
        
        if all_data.empty:
            return signals
        
        # Process each signal
        for signal in signals:
            symbol = signal["symbol"]
            entry_date = signal["entry_date"]
            entry_price = signal["entry_price"]
            
            if not entry_price or entry_price <= 0:
                continue
            
            # Filter data for this stock after entry date
            stock_data = all_data[
                (all_data["stock_id"] == symbol) & 
                (all_data["date"] > entry_date)
            ].sort_values("date")
            
            if stock_data.empty:
                continue
            
            # Calculate returns for each holding period
            signal["returns"] = {}
            
            for days in holding_days:
                if len(stock_data) >= days:
                    exit_price = stock_data.iloc[days - 1]["close"]
                    if exit_price and exit_price > 0:
                        ret = (exit_price - entry_price) / entry_price * 100
                        signal["returns"][days] = round(ret, 2)
            
            results.append(signal)
        
        return results
    
    def _calculate_stats(
        self,
        signals: List[Dict],
        holding_days: List[int]
    ) -> List[BacktestStats]:
        """Calculate statistics for each holding period"""
        
        stats = []
        
        for days in holding_days:
            returns = [
                s["returns"].get(days) 
                for s in signals 
                if "returns" in s and days in s.get("returns", {})
            ]
            
            if not returns:
                continue
            
            returns = [r for r in returns if r is not None]
            
            if not returns:
                continue
            
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r <= 0]
            
            win_rate = len(wins) / len(returns) * 100 if returns else 0
            avg_return = sum(returns) / len(returns) if returns else 0
            max_gain = max(returns) if returns else 0
            max_loss = min(returns) if returns else 0
            
            # Expected value = win_rate * avg_win - loss_rate * avg_loss
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = abs(sum(losses) / len(losses)) if losses else 0
            expected_value = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)
            
            # Median return
            median_return = float(np.median(returns)) if returns else 0
            
            stats.append(BacktestStats(
                holding_days=days,
                total_trades=len(returns),
                winning_trades=len(wins),
                losing_trades=len(losses),
                win_rate=round(win_rate, 2),
                avg_return=round(avg_return, 2),
                max_gain=round(max_gain, 2),
                max_loss=round(max_loss, 2),
                expected_value=round(expected_value, 2),
                median_return=round(median_return, 2)
            ))
        
        return stats
    
    def _get_return_distribution(self, signals: List[Dict]) -> Dict[str, int]:
        """Get return distribution for histogram"""
        
        # Get 1-day returns
        returns = [
            s["returns"].get(1) 
            for s in signals 
            if "returns" in s and 1 in s.get("returns", {})
        ]
        
        returns = [r for r in returns if r is not None]
        
        if not returns:
            return {}
        
        # Create buckets
        buckets = {
            "<-5%": 0,
            "-5%~-3%": 0,
            "-3%~-1%": 0,
            "-1%~0%": 0,
            "0%~1%": 0,
            "1%~3%": 0,
            "3%~5%": 0,
            ">5%": 0
        }
        
        for r in returns:
            if r < -5:
                buckets["<-5%"] += 1
            elif r < -3:
                buckets["-5%~-3%"] += 1
            elif r < -1:
                buckets["-3%~-1%"] += 1
            elif r < 0:
                buckets["-1%~0%"] += 1
            elif r < 1:
                buckets["0%~1%"] += 1
            elif r < 3:
                buckets["1%~3%"] += 1
            elif r < 5:
                buckets["3%~5%"] += 1
            else:
                buckets[">5%"] += 1
        
        return buckets


# Global instance
backtest_engine = BacktestEngine()
