"""
盤中即時報價服務
多來源備援、快取保護、請求節流、錯誤重試
"""
import asyncio
import aiohttp
import logging
import time
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# 快取設定
CACHE_TTL = 15  # 15 秒快取（從 30 秒降低）
CACHE_MAX_SIZE = 500

# 請求設定
BATCH_SIZE = 80  # 每批最多 80 檔（從 50 提升）
BATCH_DELAY = 1.5  # 批次間隔秒數（從 3 秒降低）
REQUEST_TIMEOUT = 10  # 請求超時秒數
MAX_RETRIES = 3  # 最大重試次數
RETRY_DELAY = 1.0  # 重試延遲秒數

# User-Agent 輪換池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


@dataclass
class QuoteData:
    """即時報價資料結構"""
    symbol: str
    name: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[int] = None  # 成交量（張）
    bid_price: Optional[float] = None  # 買一價
    ask_price: Optional[float] = None  # 賣一價
    update_time: Optional[str] = None
    source: str = "unknown"
    error: Optional[str] = None


@dataclass
class SourceStatus:
    """資料來源狀態"""
    name: str
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    total_requests: int = 0
    total_failures: int = 0


class RealtimeQuotesService:
    """即時報價服務"""

    def __init__(self):
        # 快取
        self._cache: TTLCache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)
        self._batch_cache: TTLCache = TTLCache(maxsize=50, ttl=CACHE_TTL)

        # 資料來源狀態
        self._sources: Dict[str, SourceStatus] = {
            "twse": SourceStatus(name="證交所 MIS"),
            "yahoo": SourceStatus(name="Yahoo Finance"),
        }

        # 請求鎖（防止並發過載）
        self._request_lock = asyncio.Lock()
        self._last_request_time: float = 0

        # 統計
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0,
            "source_switches": 0,
        }

    def _get_random_headers(self) -> Dict[str, str]:
        """取得隨機 User-Agent"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": "https://mis.twse.com.tw/stock/fibest.jsp",
        }

    async def _throttle(self):
        """請求節流"""
        async with self._request_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < 1.0:  # 至少間隔 1 秒
                await asyncio.sleep(1.0 - elapsed + random.uniform(0.1, 0.5))
            self._last_request_time = time.time()

    def _parse_twse_quote(self, item: Dict) -> QuoteData:
        """解析證交所報價資料"""
        symbol = item.get("c", "")
        name = item.get("n", "")

        def safe_float(val: Any) -> Optional[float]:
            if val is None or val == "-" or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        def safe_int(val: Any) -> Optional[int]:
            if val is None or val == "-" or val == "":
                return None
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None

        price = safe_float(item.get("z"))  # 成交價
        prev_close = safe_float(item.get("y"))  # 昨收

        change = None
        change_pct = None
        if price is not None and prev_close is not None and prev_close > 0:
            change = round(price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2)

        # 解析五檔（取第一檔）
        bid_prices = item.get("b", "").split("_")
        ask_prices = item.get("a", "").split("_")
        bid_price = safe_float(bid_prices[0]) if bid_prices else None
        ask_price = safe_float(ask_prices[0]) if ask_prices else None

        return QuoteData(
            symbol=symbol,
            name=name,
            price=price,
            change=change,
            change_pct=change_pct,
            open_price=safe_float(item.get("o")),
            high_price=safe_float(item.get("h")),
            low_price=safe_float(item.get("l")),
            prev_close=prev_close,
            volume=safe_int(item.get("v")),
            bid_price=bid_price,
            ask_price=ask_price,
            update_time=item.get("t"),
            source="twse",
        )

    async def _fetch_twse_batch(self, symbols: List[str], session: aiohttp.ClientSession) -> List[QuoteData]:
        """從證交所抓取一批報價"""
        results = []

        # 建立查詢字串
        ex_ch_list = []
        for symbol in symbols:
            # 判斷上市(tse)或上櫃(otc)
            if symbol.startswith("6") or symbol.startswith("3") or symbol.startswith("4"):
                # 可能是上櫃，但也可能是上市，這裡簡化處理
                ex_ch_list.append(f"tse_{symbol}.tw")
                ex_ch_list.append(f"otc_{symbol}.tw")
            else:
                ex_ch_list.append(f"tse_{symbol}.tw")

        ex_ch = "|".join(ex_ch_list)
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}"

        try:
            await self._throttle()

            async with session.get(
                url,
                headers=self._get_random_headers(),
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}")

                data = await resp.json()
                msg_array = data.get("msgArray", [])

                # 用 symbol 去重（因為可能同時查 tse 和 otc）
                seen = set()
                for item in msg_array:
                    symbol = item.get("c", "")
                    if symbol and symbol not in seen:
                        # 只保留有成交價的
                        if item.get("z") and item.get("z") != "-":
                            seen.add(symbol)
                            quote = self._parse_twse_quote(item)
                            results.append(quote)
                            # 加入快取
                            self._cache[symbol] = quote

                # 標記來源健康
                self._sources["twse"].is_healthy = True
                self._sources["twse"].consecutive_failures = 0
                self._sources["twse"].last_success = time.time()
                self._sources["twse"].total_requests += 1

        except Exception as e:
            logger.warning(f"TWSE batch fetch error: {e}")
            self._sources["twse"].consecutive_failures += 1
            self._sources["twse"].last_failure = time.time()
            self._sources["twse"].total_failures += 1

            if self._sources["twse"].consecutive_failures >= MAX_RETRIES:
                self._sources["twse"].is_healthy = False

        return results

    async def _fetch_yahoo_quote(self, symbol: str, session: aiohttp.ClientSession) -> Optional[QuoteData]:
        """從 Yahoo Finance 抓取單檔報價（備援）"""
        try:
            await self._throttle()

            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.TW?interval=1d&range=1d"

            async with session.get(
                url,
                headers=self._get_random_headers(),
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                result = data.get("chart", {}).get("result", [])
                if not result:
                    return None

                meta = result[0].get("meta", {})
                indicators = result[0].get("indicators", {}).get("quote", [{}])[0]

                price = meta.get("regularMarketPrice")
                prev_close = meta.get("previousClose")

                change = None
                change_pct = None
                if price and prev_close:
                    change = round(price - prev_close, 2)
                    change_pct = round((change / prev_close) * 100, 2)

                quote = QuoteData(
                    symbol=symbol,
                    name=meta.get("shortName", symbol),
                    price=price,
                    change=change,
                    change_pct=change_pct,
                    open_price=indicators.get("open", [None])[-1] if indicators.get("open") else None,
                    high_price=indicators.get("high", [None])[-1] if indicators.get("high") else None,
                    low_price=indicators.get("low", [None])[-1] if indicators.get("low") else None,
                    prev_close=prev_close,
                    volume=indicators.get("volume", [None])[-1] if indicators.get("volume") else None,
                    source="yahoo",
                )

                self._cache[symbol] = quote
                self._sources["yahoo"].is_healthy = True
                self._sources["yahoo"].consecutive_failures = 0
                self._sources["yahoo"].last_success = time.time()

                return quote

        except Exception as e:
            logger.warning(f"Yahoo quote error for {symbol}: {e}")
            self._sources["yahoo"].consecutive_failures += 1
            self._sources["yahoo"].last_failure = time.time()
            return None

    async def get_quotes(self, symbols: List[str], force_refresh: bool = False) -> Dict[str, Any]:
        """
        取得多檔即時報價

        Args:
            symbols: 股票代號列表
            force_refresh: 是否強制刷新（忽略快取）

        Returns:
            {
                "success": True,
                "update_time": "2024-01-30 10:30:00",
                "source": "twse",
                "quotes": [...],
                "stats": {...}
            }
        """
        self._stats["total_requests"] += 1

        results: List[QuoteData] = []
        missing_symbols: List[str] = []

        # 1. 先從快取取
        if not force_refresh:
            for symbol in symbols:
                if symbol in self._cache:
                    results.append(self._cache[symbol])
                    self._stats["cache_hits"] += 1
                else:
                    missing_symbols.append(symbol)
                    self._stats["cache_misses"] += 1
        else:
            missing_symbols = symbols.copy()

        # 2. 抓取缺失的資料
        if missing_symbols:
            async with aiohttp.ClientSession() as session:
                # 優先使用證交所
                if self._sources["twse"].is_healthy:
                    # 分批查詢
                    for i in range(0, len(missing_symbols), BATCH_SIZE):
                        batch = missing_symbols[i:i + BATCH_SIZE]
                        batch_results = await self._fetch_twse_batch(batch, session)
                        results.extend(batch_results)

                        # 批次間延遲
                        if i + BATCH_SIZE < len(missing_symbols):
                            await asyncio.sleep(BATCH_DELAY + random.uniform(0, 1))

                    # 找出還是沒抓到的
                    fetched_symbols = {q.symbol for q in results}
                    still_missing = [s for s in missing_symbols if s not in fetched_symbols]

                    # 用 Yahoo 備援
                    if still_missing and self._sources["yahoo"].is_healthy:
                        for symbol in still_missing[:10]:  # 最多補 10 檔
                            quote = await self._fetch_yahoo_quote(symbol, session)
                            if quote:
                                results.append(quote)
                            await asyncio.sleep(0.5)

                # 證交所掛了，改用 Yahoo
                elif self._sources["yahoo"].is_healthy:
                    self._stats["source_switches"] += 1
                    for symbol in missing_symbols[:50]:  # Yahoo 較慢，限制數量
                        quote = await self._fetch_yahoo_quote(symbol, session)
                        if quote:
                            results.append(quote)
                        await asyncio.sleep(0.3)

        # 3. 整理結果
        quotes_list = []
        for q in results:
            quotes_list.append({
                "symbol": q.symbol,
                "name": q.name,
                "price": q.price,
                "change": q.change,
                "change_pct": q.change_pct,
                "open_price": q.open_price,
                "high_price": q.high_price,
                "low_price": q.low_price,
                "prev_close": q.prev_close,
                "volume": q.volume,
                "bid_price": q.bid_price,
                "ask_price": q.ask_price,
                "update_time": q.update_time,
                "source": q.source,
            })

        # 依 symbol 排序
        quotes_list.sort(key=lambda x: x["symbol"])

        return {
            "success": True,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": len(quotes_list),
            "quotes": quotes_list,
            "sources": {
                name: {
                    "name": status.name,
                    "is_healthy": status.is_healthy,
                    "consecutive_failures": status.consecutive_failures,
                }
                for name, status in self._sources.items()
            },
            "stats": self._stats.copy(),
        }

    async def get_top_turnover_realtime(self, limit: int = 50) -> Dict[str, Any]:
        """
        取得週轉率前 N 名的即時報價
        先從資料庫取得週轉率排名，再抓即時報價
        """
        from services.high_turnover_analyzer import high_turnover_analyzer

        # 取得今日週轉率前 200 名
        top200_result = await high_turnover_analyzer.get_top20_turnover()

        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        items = top200_result.get("items", [])[:limit]
        symbols = [item["symbol"] for item in items]

        # 抓即時報價
        quotes_result = await self.get_quotes(symbols)

        # 合併資料
        quotes_map = {q["symbol"]: q for q in quotes_result.get("quotes", [])}

        merged = []
        for item in items:
            symbol = item["symbol"]
            quote = quotes_map.get(symbol, {})

            merged.append({
                **item,
                "realtime_price": quote.get("price"),
                "realtime_change": quote.get("change"),
                "realtime_change_pct": quote.get("change_pct"),
                "realtime_volume": quote.get("volume"),
                "realtime_high": quote.get("high_price"),
                "realtime_low": quote.get("low_price"),
                "realtime_update": quote.get("update_time"),
                "realtime_source": quote.get("source"),
            })

        return {
            "success": True,
            "update_time": quotes_result.get("update_time"),
            "query_date": top200_result.get("query_date"),
            "total_count": len(merged),
            "items": merged,
            "sources": quotes_result.get("sources"),
        }

    def get_status(self) -> Dict[str, Any]:
        """取得服務狀態"""
        return {
            "cache_size": len(self._cache),
            "cache_max_size": CACHE_MAX_SIZE,
            "cache_ttl": CACHE_TTL,
            "sources": {
                name: {
                    "name": status.name,
                    "is_healthy": status.is_healthy,
                    "consecutive_failures": status.consecutive_failures,
                    "total_requests": status.total_requests,
                    "total_failures": status.total_failures,
                }
                for name, status in self._sources.items()
            },
            "stats": self._stats.copy(),
        }

    def clear_cache(self):
        """清除快取"""
        self._cache.clear()
        self._batch_cache.clear()

    def reset_sources(self):
        """重置資料來源狀態"""
        for source in self._sources.values():
            source.is_healthy = True
            source.consecutive_failures = 0


# 全域實例
realtime_quotes_service = RealtimeQuotesService()
