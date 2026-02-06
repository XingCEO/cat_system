"""
Delta Sync Service - Incremental data fetching and caching
只獲取缺失的數據，大幅提升載入速度
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_maker
from models.kline_cache import KLineCache
from services.data_fetcher import data_fetcher
from services.cache_manager import cache_manager
from utils.date_utils import get_latest_trading_day, is_trading_day, parse_date, format_date

logger = logging.getLogger(__name__)


class DeltaSyncService:
    """
    Delta Sync 服務 - 智能增量數據同步

    核心策略:
    1. 先查 DB 最新日期
    2. 只從 API 獲取缺失的 delta
    3. 合併新舊數據
    4. 增量計算技術指標
    """

    def __init__(self):
        self._memory_cache: Dict[str, Tuple[pd.DataFrame, datetime]] = {}
        self._cache_ttl_seconds = 3600  # 1 hour memory cache

    async def get_stock_history_fast(
        self,
        symbol: str,
        days: int = 500,  # ~2 years of trading days
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        快速獲取股票歷史數據 (< 0.5s for cached data)

        優先順序:
        1. Memory cache (instant)
        2. DB cache (fast)
        3. API fetch (only delta)
        """
        cache_key = f"history_{symbol}_{days}"

        # Layer 1: Memory cache check
        if not force_refresh and cache_key in self._memory_cache:
            df, cached_at = self._memory_cache[cache_key]
            age_seconds = (datetime.now() - cached_at).total_seconds()
            if age_seconds < self._cache_ttl_seconds:
                logger.debug(f"[DeltaSync] Memory cache hit for {symbol}")
                return df.copy()

        # Layer 2: DB cache + delta fetch
        df = await self._get_with_delta_sync(symbol, days)

        # Update memory cache
        if not df.empty:
            self._memory_cache[cache_key] = (df.copy(), datetime.now())

        return df

    async def _get_with_delta_sync(
        self,
        symbol: str,
        days: int
    ) -> pd.DataFrame:
        """
        從 DB 獲取數據，並只獲取缺失的 delta
        """
        try:
            async with async_session_maker() as session:
                # Step 1: Get latest date in DB
                latest_db_date = await self._get_latest_db_date(session, symbol)

                # Step 2: Calculate date range
                end_date = date.today()
                start_date = end_date - timedelta(days=int(days * 1.5))  # Buffer for non-trading days

                # Step 3: Get existing data from DB
                existing_df = await self._get_from_db(session, symbol, start_date, end_date)

                # Step 4: Determine if delta fetch is needed
                latest_trading = parse_date(get_latest_trading_day())

                needs_delta = (
                    latest_db_date is None or
                    (latest_trading and latest_db_date < latest_trading)
                )

                if needs_delta:
                    # Only fetch missing data
                    delta_start = (latest_db_date + timedelta(days=1)) if latest_db_date else start_date
                    logger.info(f"[DeltaSync] Fetching delta for {symbol}: {delta_start} -> {end_date}")

                    delta_df = await self._fetch_delta(symbol, delta_start, end_date)

                    if not delta_df.empty:
                        # Save delta to DB
                        await self._save_to_db(session, symbol, delta_df)

                        # Merge with existing data
                        if not existing_df.empty:
                            existing_df = pd.concat([existing_df, delta_df], ignore_index=True)
                            existing_df = existing_df.drop_duplicates(subset=['date'], keep='last')
                            existing_df = existing_df.sort_values('date', ascending=False)
                        else:
                            existing_df = delta_df
                else:
                    logger.debug(f"[DeltaSync] DB is up-to-date for {symbol}")

                # Limit to requested days
                if len(existing_df) > days:
                    existing_df = existing_df.head(days)

                return existing_df

        except Exception as e:
            logger.error(f"[DeltaSync] Error for {symbol}: {e}", exc_info=True)
            # Fallback to direct API fetch
            return await self._fallback_fetch(symbol, days)

    async def _get_latest_db_date(
        self,
        session: AsyncSession,
        symbol: str
    ) -> Optional[date]:
        """查詢 DB 中該股票的最新日期"""
        try:
            query = select(func.max(KLineCache.date)).where(
                KLineCache.symbol == symbol
            )
            result = await session.execute(query)
            max_date = result.scalar()
            return max_date
        except Exception as e:
            logger.debug(f"[DeltaSync] Cannot get latest date for {symbol}: {e}")
            return None

    async def _get_from_db(
        self,
        session: AsyncSession,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """從 DB 獲取歷史數據"""
        try:
            query = select(KLineCache).where(
                and_(
                    KLineCache.symbol == symbol,
                    KLineCache.date >= start_date,
                    KLineCache.date <= end_date
                )
            ).order_by(KLineCache.date.desc())

            result = await session.execute(query)
            rows = result.scalars().all()

            if not rows:
                return pd.DataFrame()

            data = []
            for row in rows:
                data.append({
                    'date': row.date,
                    'open': row.open,
                    'high': row.high,
                    'low': row.low,
                    'close': row.close,
                    'volume': row.volume,
                    'change_percent': row.change_percent,
                    # Cached indicators
                    'ma5': row.ma5,
                    'ma10': row.ma10,
                    'ma20': row.ma20,
                    'ma60': row.ma60,
                    'rsi': row.rsi,
                    'macd': row.macd,
                    'macd_signal': row.macd_signal,
                    'macd_hist': row.macd_hist,
                    'k': row.k,
                    'd': row.d,
                    'bb_upper': row.bb_upper,
                    'bb_middle': row.bb_middle,
                    'bb_lower': row.bb_lower,
                })

            return pd.DataFrame(data)

        except Exception as e:
            logger.debug(f"[DeltaSync] Cannot get from DB for {symbol}: {e}")
            return pd.DataFrame()

    async def _fetch_delta(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """從 API 獲取 delta 數據"""
        try:
            df = await data_fetcher.get_historical_data(
                symbol,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )

            if df.empty:
                return pd.DataFrame()

            # Calculate indicators for delta data
            df = self._calculate_indicators_incremental(df)

            return df

        except Exception as e:
            logger.error(f"[DeltaSync] Fetch delta failed for {symbol}: {e}")
            return pd.DataFrame()

    def _calculate_indicators_incremental(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算技術指標 (增量計算優化)"""
        if df.empty or 'close' not in df.columns:
            return df

        try:
            # Ensure sorted by date ascending for calculations
            df = df.sort_values('date', ascending=True).reset_index(drop=True)

            closes = df['close'].values

            # Moving Averages
            for period, col in [(5, 'ma5'), (10, 'ma10'), (20, 'ma20'), (60, 'ma60')]:
                if len(closes) >= period:
                    df[col] = df['close'].rolling(window=period).mean()

            # RSI (14-period)
            if len(closes) >= 15:
                delta = df['close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = (-delta).where(delta < 0, 0)
                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()
                rs = avg_gain / avg_loss.replace(0, float('inf'))
                df['rsi'] = 100 - (100 / (1 + rs))

            # MACD (12, 26, 9)
            if len(closes) >= 26:
                exp12 = df['close'].ewm(span=12, adjust=False).mean()
                exp26 = df['close'].ewm(span=26, adjust=False).mean()
                df['macd'] = exp12 - exp26
                df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                df['macd_hist'] = df['macd'] - df['macd_signal']

            # KD Stochastic (9, 3, 3)
            if len(closes) >= 9:
                low_9 = df['low'].rolling(window=9).min()
                high_9 = df['high'].rolling(window=9).max()
                df['k'] = 100 * (df['close'] - low_9) / (high_9 - low_9).replace(0, 1)
                df['d'] = df['k'].rolling(window=3).mean()

            # Bollinger Bands (20, 2)
            if len(closes) >= 20:
                df['bb_middle'] = df['close'].rolling(window=20).mean()
                std = df['close'].rolling(window=20).std()
                df['bb_upper'] = df['bb_middle'] + (std * 2)
                df['bb_lower'] = df['bb_middle'] - (std * 2)

            # Sort back to descending (newest first)
            df = df.sort_values('date', ascending=False).reset_index(drop=True)

        except Exception as e:
            logger.warning(f"[DeltaSync] Indicator calculation failed: {e}")

        return df

    async def _save_to_db(
        self,
        session: AsyncSession,
        symbol: str,
        df: pd.DataFrame
    ) -> None:
        """保存數據到 DB"""
        try:
            for _, row in df.iterrows():
                row_date = row.get('date')
                if isinstance(row_date, str):
                    row_date = parse_date(row_date)

                if row_date is None:
                    continue

                # Upsert logic: check if exists
                existing = await session.execute(
                    select(KLineCache).where(
                        and_(
                            KLineCache.symbol == symbol,
                            KLineCache.date == row_date
                        )
                    )
                )
                existing_row = existing.scalar_one_or_none()

                if existing_row:
                    # Update existing
                    existing_row.open = row.get('open')
                    existing_row.high = row.get('high')
                    existing_row.low = row.get('low')
                    existing_row.close = row.get('close')
                    existing_row.volume = row.get('volume')
                    existing_row.change_percent = row.get('change_percent')
                    existing_row.ma5 = row.get('ma5')
                    existing_row.ma10 = row.get('ma10')
                    existing_row.ma20 = row.get('ma20')
                    existing_row.ma60 = row.get('ma60')
                    existing_row.rsi = row.get('rsi')
                    existing_row.macd = row.get('macd')
                    existing_row.macd_signal = row.get('macd_signal')
                    existing_row.macd_hist = row.get('macd_hist')
                    existing_row.k = row.get('k')
                    existing_row.d = row.get('d')
                    existing_row.bb_upper = row.get('bb_upper')
                    existing_row.bb_middle = row.get('bb_middle')
                    existing_row.bb_lower = row.get('bb_lower')
                    existing_row.updated_at = datetime.utcnow()
                else:
                    # Insert new
                    cache_entry = KLineCache(
                        symbol=symbol,
                        date=row_date,
                        open=row.get('open'),
                        high=row.get('high'),
                        low=row.get('low'),
                        close=row.get('close'),
                        volume=row.get('volume'),
                        change_percent=row.get('change_percent'),
                        ma5=row.get('ma5'),
                        ma10=row.get('ma10'),
                        ma20=row.get('ma20'),
                        ma60=row.get('ma60'),
                        rsi=row.get('rsi'),
                        macd=row.get('macd'),
                        macd_signal=row.get('macd_signal'),
                        macd_hist=row.get('macd_hist'),
                        k=row.get('k'),
                        d=row.get('d'),
                        bb_upper=row.get('bb_upper'),
                        bb_middle=row.get('bb_middle'),
                        bb_lower=row.get('bb_lower'),
                    )
                    session.add(cache_entry)

            await session.commit()
            logger.debug(f"[DeltaSync] Saved {len(df)} rows to DB for {symbol}")

        except Exception as e:
            logger.error(f"[DeltaSync] Failed to save to DB for {symbol}: {e}")
            await session.rollback()

    async def _fallback_fetch(
        self,
        symbol: str,
        days: int
    ) -> pd.DataFrame:
        """Fallback: 直接從 API 獲取全部數據"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=int(days * 1.5))

            df = await data_fetcher.get_historical_data(
                symbol,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )

            if not df.empty:
                df = self._calculate_indicators_incremental(df)

            return df

        except Exception as e:
            logger.error(f"[DeltaSync] Fallback fetch failed for {symbol}: {e}")
            return pd.DataFrame()

    def clear_memory_cache(self, symbol: Optional[str] = None) -> None:
        """清除記憶體快取"""
        if symbol:
            keys_to_remove = [k for k in self._memory_cache if symbol in k]
            for key in keys_to_remove:
                del self._memory_cache[key]
        else:
            self._memory_cache.clear()
        logger.info(f"[DeltaSync] Memory cache cleared: {symbol or 'all'}")

    async def prefetch_symbols(self, symbols: List[str], days: int = 500) -> Dict[str, bool]:
        """預先載入多支股票數據（可用於背景預熱）"""
        results = {}
        for symbol in symbols:
            try:
                df = await self.get_stock_history_fast(symbol, days)
                results[symbol] = not df.empty
            except Exception as e:
                logger.warning(f"[DeltaSync] Prefetch failed for {symbol}: {e}")
                results[symbol] = False
        return results


# Global instance
delta_sync = DeltaSyncService()
