"""
Enhanced K-Line Service
支援 5 年歷史資料、批次抓取、進度追蹤、資料驗證
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any, Literal, Tuple
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging
import asyncio
try:
    import pandas_ta as ta
except ImportError:
    ta = None

try:
    from services.technical_analysis import calculate_all_indicators as shared_calculate_indicators
except ImportError:
    from services.technical_analysis import calculate_all_indicators as shared_calculate_indicators

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from config import settings

from database import async_session_maker
from models.kline_cache import KLineCache, KLineFetchProgress
from services.data_fetcher import data_fetcher
from services.cache_manager import cache_manager
from utils.date_utils import get_taiwan_now, get_taiwan_today, get_latest_trading_day, get_market_status, format_date

logger = logging.getLogger(__name__)


class EnhancedKLineService:
    """增強版 K 線服務，支援 5 年資料"""
    
    # 預設抓取範圍
    DEFAULT_START_DATE = "2021-01-01"
    MAX_YEARS = 5
    CACHE_HOURS = 24  # 快取有效期（小時）
    
    def __init__(self):
        self.data_fetcher = data_fetcher
    
    async def get_kline_data_extended(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Literal["day", "week", "month"] = "day",
    ) -> Dict[str, Any]:
        """
        取得擴展 K 線資料（支援 5 年）
        
        Args:
            symbol: 股票代號
            start_date: 起始日期 YYYY-MM-DD（預設 2021-01-01）
            end_date: 結束日期 YYYY-MM-DD（預設今天）
            period: 週期 day/week/month
        
        Returns:
            完整 K 線資料結構
        """
        # 設定日期範圍
        if not end_date:
            end_date = await self.data_fetcher.get_latest_trading_date()
        if not start_date:
            start_date = self.DEFAULT_START_DATE
        
        # 驗證日期格式
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "日期格式錯誤，請使用 YYYY-MM-DD"}
        
        if start_dt > end_dt:
            return {"error": "起始日期不能大於結束日期"}
        
        logger.info(f"取得 K 線資料: {symbol} {start_date} ~ {end_date}")

        # 取得市場狀態，決定是否需要即時數據
        market_status, should_have_today = get_market_status()
        latest_trading_day = get_latest_trading_day()

        # 先嘗試從快取取得任何可用資料
        cached_any = await self._get_from_cache_any(symbol)
        if cached_any is not None and len(cached_any) > 0:
            logger.info(f"使用快取資料: {len(cached_any)} 筆")
            df = pd.DataFrame(cached_any)

            # 關鍵修復：檢查快取是否缺少今日數據
            if should_have_today:
                df = await self._ensure_today_candle(symbol, df, latest_trading_day, market_status)
        else:
            # 嘗試從快取取得指定範圍
            cached_data = await self._get_from_cache(symbol, start_dt, end_dt)

            if cached_data is not None and len(cached_data) > 0:
                logger.info(f"從快取取得 {len(cached_data)} 筆資料")
                df = pd.DataFrame(cached_data)
            else:
                # 從 API 抓取並快取
                df = await self._fetch_and_cache(symbol, start_date, end_date)

                if df.empty:
                    return {"error": f"無法取得 {symbol} 的歷史資料，API 暫時無法使用"}

            # 關鍵修復：這個路徑也要檢查今日數據
            if should_have_today:
                df = await self._ensure_today_candle(symbol, df, latest_trading_day, market_status)

        # 資料驗證與清理
        df = self._validate_and_clean_data(df)
        
        if df.empty:
            return {"error": "資料驗證後無有效資料"}
        
        # 計算技術指標
        df = shared_calculate_indicators(df)
        
        # 根據週期轉換
        if period == "week":
            df = self._resample_to_week(df)
        elif period == "month":
            df = self._resample_to_month(df)
        
        # 取得股票資訊
        stock_info = await self.data_fetcher.get_stock_info(symbol)
        
        # 格式化輸出
        kline_data = self._format_kline_data(df)
        
        # 最新報價
        latest_price = self._get_latest_price_info(df)
        
        return {
            "symbol": symbol,
            "name": stock_info.get("stock_name", symbol) if stock_info else symbol,
            "industry": stock_info.get("industry_category", "") if stock_info else "",
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "kline_data": kline_data,
            "latest_price": latest_price,
            "data_count": len(kline_data),
            "data_range": {
                "first_date": kline_data[0]["date"] if kline_data else None,
                "last_date": kline_data[-1]["date"] if kline_data else None,
            },
        }
    
    async def _get_from_cache(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date
    ) -> Optional[List[Dict]]:
        """從資料庫快取取得資料"""
        try:
            async with async_session_maker() as session:
                stmt = select(KLineCache).where(
                    KLineCache.symbol == symbol,
                    KLineCache.date >= start_date,
                    KLineCache.date <= end_date,
                    KLineCache.is_valid == 1
                ).order_by(KLineCache.date)
                
                result = await session.execute(stmt)
                rows = result.scalars().all()
                
                if not rows:
                    return None
                
                # 檢查是否過期
                if any(row.is_stale(self.CACHE_HOURS) for row in rows):
                    logger.info("快取資料已過期，需要重新抓取")
                    return None
                
                # 檢查資料完整性（允許 5% 缺失）
                expected_days = (end_date - start_date).days
                actual_days = len(rows)
                coverage = actual_days / max(expected_days * 0.7, 1)  # 約 70% 是交易日
                
                if coverage < 0.8:
                    logger.info(f"快取資料不完整: {actual_days}/{expected_days} ({coverage:.1%})")
                    return None
                
                return [row.to_dict() for row in rows]

        except Exception as e:
            logger.error(f"讀取快取失敗: {e}")
            return None

    async def _get_from_cache_any(self, symbol: str) -> Optional[List[Dict]]:
        """從資料庫取得任何可用的快取資料（不檢查完整性，但檢查過期）"""
        try:
            async with async_session_maker() as session:
                stmt = select(KLineCache).where(
                    KLineCache.symbol == symbol,
                    KLineCache.is_valid == 1
                ).order_by(KLineCache.date)

                result = await session.execute(stmt)
                rows = result.scalars().all()

                if not rows:
                    return None

                # 檢查是否有過期資料（使用較寬鬆的標準）
                # 盤中用較短 TTL，盤後用較長 TTL
                market_status, _ = get_market_status()
                cache_hours = 1 if market_status == "open" else self.CACHE_HOURS

                # 只檢查最新一筆是否過期
                if rows and rows[-1].is_stale(cache_hours):
                    logger.info(f"[EnhancedKLine] {symbol} 快取過期 (>{cache_hours}h)，但仍返回舊資料供快速顯示")
                    # 仍然返回舊資料，讓 _ensure_today_candle 去補充新資料

                return [row.to_dict() for row in rows]

        except Exception as e:
            logger.error(f"讀取快取失敗: {e}")
            return None

    async def _ensure_today_candle(
        self,
        symbol: str,
        df: pd.DataFrame,
        latest_trading_day: str,
        market_status: str
    ) -> pd.DataFrame:
        """
        確保 K 線數據包含今日蠟燭

        如果快取中最新日期 < 最新交易日，從 API 抓取缺失的數據並合併
        """
        if df.empty:
            return df

        # 取得快取中最新日期
        df_dates = df['date'].astype(str).str[:10]
        cached_latest = df_dates.max()

        # 如果快取已經是最新，直接返回
        if cached_latest >= latest_trading_day:
            logger.debug(f"[EnhancedKLine] {symbol} 快取已是最新 ({cached_latest})")
            return df

        # 需要補充數據
        logger.info(f"[EnhancedKLine] {symbol} 快取過期 ({cached_latest} < {latest_trading_day})，正在補充...")

        try:
            # 從 API 抓取缺失的數據
            from datetime import datetime, timedelta

            # 從快取最新日期的隔天開始抓取
            cached_date = datetime.strptime(cached_latest, "%Y-%m-%d").date()
            fetch_start = (cached_date + timedelta(days=1)).strftime("%Y-%m-%d")
            fetch_end = format_date(get_taiwan_today())

            delta_df = await self.data_fetcher.get_historical_data(
                symbol, fetch_start, fetch_end
            )

            if delta_df.empty:
                # 嘗試獲取即時報價作為今日蠟燭
                if market_status in ("open", "closed"):
                    today_candle = await self._get_realtime_candle(symbol, latest_trading_day)
                    if today_candle:
                        delta_df = pd.DataFrame([today_candle])

            if not delta_df.empty:
                # 準備數據
                delta_df = self._prepare_dataframe(delta_df)

                # 儲存到快取
                await self._save_to_cache(symbol, delta_df)

                # 合併數據
                df = pd.concat([df, delta_df], ignore_index=True)
                df = df.drop_duplicates(subset=['date'], keep='last')
                df = df.sort_values('date').reset_index(drop=True)

                logger.info(f"[EnhancedKLine] {symbol} 已補充 {len(delta_df)} 筆數據，最新日期: {df['date'].astype(str).str[:10].max()}")

        except Exception as e:
            logger.warning(f"[EnhancedKLine] {symbol} 補充數據失敗: {e}")

        return df

    async def _get_realtime_candle(self, symbol: str, date_str: str) -> Optional[Dict]:
        """
        從即時報價取得今日蠟燭數據
        確保 OHLC 有真實的不同值，避免產生 Doji 假蠟燭

        增強錯誤處理：
        - 加入 timeout 保護
        - 詳細日誌記錄
        - 多層 fallback
        """
        try:
            from services.realtime_quotes import realtime_quotes_service

            # Use get_quotes to fetch realtime data with timeout protection
            try:
                result = await asyncio.wait_for(
                    realtime_quotes_service.get_quotes([symbol]),
                    timeout=10.0  # 10 秒超時
                )
            except asyncio.TimeoutError:
                logger.warning(f"[EnhancedKLine] {symbol} 即時報價超時 (10s)")
                return None
            quotes = {q["symbol"]: q for q in result.get("quotes", [])}

            if quotes and symbol in quotes:
                q = quotes[symbol]

                # Extract current price (close)
                close = q.get("price")
                if not close or close <= 0:
                    logger.warning(f"[EnhancedKLine] {symbol} 無有效成交價")
                    return None

                # Extract OHLC - these fields come from TWSE MIS API
                open_price = q.get("open_price")
                high_price = q.get("high_price")
                low_price = q.get("low_price")
                # 注意：realtime_quotes 已將成交量轉為「張」，歷史數據也是「張」
                # 確保單位一致
                volume = q.get("volume") or 0

                # Validate OHL values are real numbers (not None, not 0)
                has_valid_ohlc = (
                    open_price and open_price > 0 and
                    high_price and high_price > 0 and
                    low_price and low_price > 0
                )

                if has_valid_ohlc:
                    # All OHLC values are valid
                    candle = {
                        "date": date_str,
                        "open": float(open_price),
                        "high": float(high_price),
                        "low": float(low_price),
                        "close": float(close),
                        "volume": int(volume) if volume else 0,
                    }
                    logger.info(f"[EnhancedKLine] {symbol} 即時蠟燭: O={open_price} H={high_price} L={low_price} C={close} V={volume}")
                    return candle
                else:
                    # OHL missing - use prev_close for open, calculate H/L from price movement
                    prev_close = q.get("prev_close")
                    if prev_close and prev_close > 0:
                        # Estimate: open = prev_close, high/low based on change direction
                        estimated_open = float(prev_close)
                        if close >= estimated_open:
                            # Up day: low = open, high = close
                            estimated_high = float(close)
                            estimated_low = estimated_open
                        else:
                            # Down day: high = open, low = close
                            estimated_high = estimated_open
                            estimated_low = float(close)

                        candle = {
                            "date": date_str,
                            "open": estimated_open,
                            "high": estimated_high,
                            "low": estimated_low,
                            "close": float(close),
                            "volume": int(volume) if volume else 0,
                        }
                        logger.info(f"[EnhancedKLine] {symbol} 估計蠟燭 (from prev_close): O={estimated_open} H={estimated_high} L={estimated_low} C={close}")
                        return candle
                    else:
                        # Last resort: use bid/ask spread to estimate range
                        bid = q.get("bid_price")
                        ask = q.get("ask_price")
                        if bid and ask and bid > 0 and ask > 0:
                            estimated_low = min(float(bid), float(close))
                            estimated_high = max(float(ask), float(close))
                            candle = {
                                "date": date_str,
                                "open": float(close),  # No better estimate
                                "high": estimated_high,
                                "low": estimated_low,
                                "close": float(close),
                                "volume": int(volume) if volume else 0,
                            }
                            logger.info(f"[EnhancedKLine] {symbol} 估計蠟燭 (from bid/ask): H={estimated_high} L={estimated_low} C={close}")
                            return candle

                    # Absolute fallback - toothpick (better than nothing)
                    logger.warning(f"[EnhancedKLine] {symbol} 無法取得完整OHLC，使用單一價格")
                    return {
                        "date": date_str,
                        "open": float(close),
                        "high": float(close),
                        "low": float(close),
                        "close": float(close),
                        "volume": int(volume) if volume else 0,
                    }

        except Exception as e:
            logger.warning(f"[EnhancedKLine] 即時報價失敗 {symbol}: {e}")

        return None

    async def _fetch_and_cache(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """從 API 抓取資料並快取"""
        # 批次按月抓取
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_data = []
        current = start_dt
        
        while current <= end_dt:
            month_end = min(
                current + relativedelta(months=1) - timedelta(days=1),
                end_dt
            )
            
            try:
                month_start_str = current.strftime("%Y-%m-%d")
                month_end_str = month_end.strftime("%Y-%m-%d")
                
                df = await self.data_fetcher.get_historical_data(
                    symbol, month_start_str, month_end_str
                )
                
                if not df.empty:
                    all_data.append(df)
                    logger.debug(f"抓取 {symbol} {current.strftime('%Y-%m')}: {len(df)} 筆")
                    
            except Exception as e:
                logger.warning(f"抓取 {symbol} {current.strftime('%Y-%m')} 失敗: {e}")
            
            current = current + relativedelta(months=1)
            
            # 避免 API 限流
            await asyncio.sleep(0.1)
        
        if not all_data:
            return pd.DataFrame()
        
        # 合併資料
        df = pd.concat(all_data, ignore_index=True)
        
        # 準備資料框
        df = self._prepare_dataframe(df)
        
        # 儲存到快取
        await self._save_to_cache(symbol, df)
        
        return df
    
    async def _save_to_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """儲存資料到快取"""
        if df.empty:
            return
            
        try:
            async with async_session_maker() as session:
                # 準備資料
                records = []
                for _, row in df.iterrows():
                    record = {
                        "symbol": symbol,
                        "date": row["date"] if isinstance(row["date"], date) else datetime.strptime(str(row["date"])[:10], "%Y-%m-%d").date(),
                        "open": float(row["open"]) if pd.notna(row.get("open")) else None,
                        "high": float(row["high"]) if pd.notna(row.get("high")) else None,
                        "low": float(row["low"]) if pd.notna(row.get("low")) else None,
                        "close": float(row["close"]) if pd.notna(row.get("close")) else None,
                        "volume": int(row["volume"]) if pd.notna(row.get("volume")) else None,
                        "is_valid": 1,
                        "cached_at": get_taiwan_now().replace(tzinfo=None),
                    }
                    records.append(record)
                
                # 使用 upsert - 自動選擇正確的資料庫方言
                is_postgresql = settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgresql")

                for record in records:
                    if is_postgresql:
                        # PostgreSQL 使用 ON CONFLICT DO UPDATE
                        stmt = pg_insert(KLineCache).values(**record)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["symbol", "date"],
                            set_={
                                "open": stmt.excluded.open,
                                "high": stmt.excluded.high,
                                "low": stmt.excluded.low,
                                "close": stmt.excluded.close,
                                "volume": stmt.excluded.volume,
                                "cached_at": stmt.excluded.cached_at,
                                "is_valid": stmt.excluded.is_valid,
                            }
                        )
                    else:
                        # SQLite 使用 INSERT OR REPLACE
                        stmt = sqlite_insert(KLineCache).values(**record)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["symbol", "date"],
                            set_={
                                "open": stmt.excluded.open,
                                "high": stmt.excluded.high,
                                "low": stmt.excluded.low,
                                "close": stmt.excluded.close,
                                "volume": stmt.excluded.volume,
                                "cached_at": stmt.excluded.cached_at,
                                "is_valid": stmt.excluded.is_valid,
                            }
                        )
                    await session.execute(stmt)
                
                await session.commit()
                logger.info(f"快取 {symbol} 共 {len(records)} 筆資料")
                
        except Exception as e:
            logger.error(f"儲存快取失敗: {e}")
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """準備資料框"""
        # 重命名欄位
        column_map = {
            "max": "high",
            "min": "low",
            "Trading_Volume": "volume"
        }
        df = df.rename(columns=column_map)
        
        # 確保必要欄位
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"缺少欄位: {col}")
                return pd.DataFrame()
        
        # 排序
        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        
        # 轉換數值
        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # 去重
        if "date" in df.columns:
            df = df.drop_duplicates(subset=["date"], keep="last")
        
        return df
    
    def _validate_and_clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """資料驗證與清理"""
        if df.empty:
            return df
        
        original_count = len(df)
        
        # 1. 移除空值
        df = df.dropna(subset=["close"])
        
        # 2. 驗證 OHLC 關係 (Low <= Open/Close <= High)
        valid_ohlc = (
            (df["low"] <= df["open"]) & 
            (df["low"] <= df["close"]) &
            (df["high"] >= df["open"]) & 
            (df["high"] >= df["close"])
        )
        df = df[valid_ohlc | df["low"].isna() | df["high"].isna()]
        
        # 3. 過濾異常價格（0 元或超過 10000 元）
        price_valid = (df["close"] > 0) & (df["close"] < 10000)
        df = df[price_valid]
        
        # 4. 過濾異常成交量（負數）
        if "volume" in df.columns:
            df = df[df["volume"] >= 0]
        
        # 5. 確保日期排序
        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        
        cleaned_count = len(df)
        if original_count != cleaned_count:
            logger.info(f"資料清理: {original_count} -> {cleaned_count} 筆")
        
        return df
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算所有技術指標"""
        if df.empty or len(df) < 14:
            return df
        
        if ta is not None:
            try:
                # 移動平均線
                df["SMA_5"] = ta.sma(df["close"], length=5)
                df["SMA_10"] = ta.sma(df["close"], length=10)
                df["SMA_20"] = ta.sma(df["close"], length=20)
                df["SMA_60"] = ta.sma(df["close"], length=60)
                df["SMA_120"] = ta.sma(df["close"], length=120)
                
                # 成交量均線
                df["Volume_MA5"] = ta.sma(df["volume"], length=5)
                
                # RSI
                df["RSI_14"] = ta.rsi(df["close"], length=14)
                
                # MACD
                macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
                if macd is not None:
                    df = pd.concat([df, macd], axis=1)
                
                # KD
                stoch = ta.stoch(df["high"], df["low"], df["close"], k=9, d=3, smooth_k=3)
                if stoch is not None:
                    df = pd.concat([df, stoch], axis=1)
                
                # 布林通道
                bbands = ta.bbands(df["close"], length=20, std=2)
                if bbands is not None:
                    df = pd.concat([df, bbands], axis=1)
                    
            except Exception as e:
                logger.error(f"計算指標失敗: {e}")
                df = self._calculate_indicators_manual(df)
        else:
            df = self._calculate_indicators_manual(df)
        
        return df
    
    def _calculate_indicators_manual(self, df: pd.DataFrame) -> pd.DataFrame:
        """手動計算指標 (當 pandas_ta 不可用時的備援)"""
        # 移動平均線
        df["SMA_5"] = df["close"].rolling(window=5).mean()
        df["SMA_10"] = df["close"].rolling(window=10).mean()
        df["SMA_20"] = df["close"].rolling(window=20).mean()
        df["SMA_60"] = df["close"].rolling(window=60).mean()
        df["SMA_120"] = df["close"].rolling(window=120).mean()
        
        # 成交量均線
        df["Volume_MA5"] = df["volume"].rolling(window=5).mean()
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df["RSI_14"] = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD_12_26_9"] = ema12 - ema26
        df["MACDs_12_26_9"] = df["MACD_12_26_9"].ewm(span=9, adjust=False).mean()
        df["MACDh_12_26_9"] = df["MACD_12_26_9"] - df["MACDs_12_26_9"]
        
        # KD
        low9 = df["low"].rolling(window=9).min()
        high9 = df["high"].rolling(window=9).max()
        df["STOCHk_9_3_3"] = 100 * (df["close"] - low9) / (high9 - low9)
        df["STOCHd_9_3_3"] = df["STOCHk_9_3_3"].rolling(window=3).mean()
        
        # 布林通道
        df["BBM_20_2.0"] = df["close"].rolling(window=20).mean()
        std20 = df["close"].rolling(window=20).std()
        df["BBU_20_2.0"] = df["BBM_20_2.0"] + 2 * std20
        df["BBL_20_2.0"] = df["BBM_20_2.0"] - 2 * std20
        
        return df
    
    def _resample_to_week(self, df: pd.DataFrame) -> pd.DataFrame:
        """轉換為週 K"""
        if "date" not in df.columns:
            return df
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        weekly = df.resample("W").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()
        
        weekly = weekly.reset_index()
        weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")
        
        # 重新計算指標
        return self._calculate_all_indicators(weekly)
    
    def _resample_to_month(self, df: pd.DataFrame) -> pd.DataFrame:
        """轉換為月 K"""
        if "date" not in df.columns:
            return df
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        monthly = df.resample("ME").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()
        
        monthly = monthly.reset_index()
        monthly["date"] = monthly["date"].dt.strftime("%Y-%m-%d")
        
        return self._calculate_all_indicators(monthly)
    
    def _format_kline_data(self, df: pd.DataFrame) -> List[Dict]:
        """格式化 K 線資料"""
        result = []
        
        for _, row in df.iterrows():
            item = {
                "date": str(row.get("date", ""))[:10],
                "open": round(float(row["open"]), 2) if pd.notna(row.get("open")) else None,
                "high": round(float(row["high"]), 2) if pd.notna(row.get("high")) else None,
                "low": round(float(row["low"]), 2) if pd.notna(row.get("low")) else None,
                "close": round(float(row["close"]), 2) if pd.notna(row.get("close")) else None,
                "volume": int(row["volume"]) if pd.notna(row.get("volume")) else 0,
            }
            
            # 均線
            for col, key in [
                ("SMA_5", "ma5"), ("SMA_10", "ma10"), ("SMA_20", "ma20"),
                ("SMA_60", "ma60"), ("SMA_120", "ma120"),
                ("Volume_MA5", "volume_ma5")
            ]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 2) if pd.notna(val) else None
            
            # MACD
            for col, key in [
                ("MACD_12_26_9", "macd"),
                ("MACDs_12_26_9", "macd_signal"),
                ("MACDh_12_26_9", "macd_hist"),
            ]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 4) if pd.notna(val) else None
            
            # KD
            for col, key in [("STOCHk_9_3_3", "k"), ("STOCHd_9_3_3", "d")]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 2) if pd.notna(val) else None
            
            # RSI
            if "RSI_14" in df.columns:
                val = row.get("RSI_14")
                item["rsi"] = round(float(val), 2) if pd.notna(val) else None
            
            # 布林通道
            for col, key in [
                ("BBU_20_2.0", "bb_upper"),
                ("BBM_20_2.0", "bb_middle"),
                ("BBL_20_2.0", "bb_lower"),
            ]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 2) if pd.notna(val) else None
            
            result.append(item)
        
        return result
    
    def _get_latest_price_info(self, df: pd.DataFrame) -> Optional[Dict]:
        """取得最新報價資訊"""
        if df.empty:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None
        
        change = float(latest["close"]) - float(prev["close"]) if prev is not None else 0
        change_pct = (change / float(prev["close"]) * 100) if prev is not None and prev["close"] != 0 else 0
        
        return {
            "close": round(float(latest["close"]), 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": int(latest["volume"]) if pd.notna(latest.get("volume")) else 0,
            "amount": round(float(latest["close"]) * int(latest["volume"]) / 100000000, 2) if pd.notna(latest.get("volume")) else 0,
            "high": round(float(latest["high"]), 2) if pd.notna(latest.get("high")) else None,
            "low": round(float(latest["low"]), 2) if pd.notna(latest.get("low")) else None,
            "open": round(float(latest["open"]), 2) if pd.notna(latest.get("open")) else None,
        }
    
    async def get_fetch_progress(self, symbol: str) -> Optional[Dict]:
        """取得抓取進度"""
        try:
            async with async_session_maker() as session:
                stmt = select(KLineFetchProgress).where(
                    KLineFetchProgress.symbol == symbol
                )
                result = await session.execute(stmt)
                progress = result.scalar_one_or_none()
                
                if progress:
                    return progress.to_dict()
                return None
                
        except Exception as e:
            logger.error(f"取得進度失敗: {e}")
            return None


# 全域實例
enhanced_kline_service = EnhancedKLineService()
