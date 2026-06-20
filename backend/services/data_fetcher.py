"""
Data Fetcher - FinMind API + TWSE Open Data
"""
import httpx
import ssl
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union
import asyncio
import logging

from config import get_settings
from services.cache_manager import cache_manager

settings = get_settings()
logger = logging.getLogger(__name__)

# TWSE 相關的 host 清單（只對這些 host 套用寬鬆 SSL）
# 若日後 TWSE 新增子網域，在此補充即可
TWSE_HOSTS = (
    "www.twse.com.tw",
    "mis.twse.com.tw",
    "openapi.twse.com.tw",
)


def _build_twse_ssl_context() -> Union[bool, str, ssl.SSLContext]:
    """
    依 settings.twse_ssl_mode 建立適當的 SSL 驗證設定，
    回傳值可直接傳給 httpx.AsyncClient(verify=...) 或 client.get(…, verify=…)。

    modes:
      "default"  → True  (httpx/certifi 預設行為，不做任何改動)
      "certifi"  → certifi CA bundle 路徑 (str)
      "relaxed"  → ssl.SSLContext，關閉 X.509 strict 旗標
                   (允許缺少 Subject Key Identifier 等問題憑證)
      "insecure" → False (完全停用憑證驗證，由 config 啟用才生效)

    若設了 twse_ssl_ca_bundle，無論 mode 為何都以自訂 CA 路徑覆寫。
    """
    mode = settings.twse_ssl_mode
    ca_bundle = settings.twse_ssl_ca_bundle

    # 自訂 CA bundle 優先（覆寫所有 mode）
    if ca_bundle:
        logger.info(f"TWSE SSL: using custom CA bundle at {ca_bundle}")
        return ca_bundle

    if mode == "insecure":
        logger.warning("TWSE SSL: verification DISABLED (insecure mode) — not recommended in production")
        return False

    if mode == "certifi":
        try:
            import certifi
            path = certifi.where()
            logger.info(f"TWSE SSL: using certifi CA bundle ({path})")
            return path
        except ImportError:
            logger.warning("TWSE SSL: certifi not installed, falling back to default")
            return True

    if mode == "relaxed":
        # 建立預設 SSL context，再關閉 X.509 strict 旗標
        # 解決 Python 3.14 對 TWSE 憑證缺少 Subject Key Identifier 的拒絕
        ctx = ssl.create_default_context()
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
            logger.info("TWSE SSL: relaxed mode — VERIFY_X509_STRICT disabled")
        else:
            logger.info("TWSE SSL: relaxed mode requested but VERIFY_X509_STRICT not available, using default context")
        return ctx

    # "default" 或未知 mode → httpx 預設
    return True


def parse_number(val: Any, to_float: bool = False) -> Optional[Union[int, float]]:
    """統一的數值解析函式，處理各種格式的數值字串"""
    if val is None or val == "" or val == "--" or val == "X":
        return None
    val_str = str(val).replace(",", "").replace("+", "").replace(" ", "")
    try:
        return float(val_str) if to_float else int(float(val_str))
    except (ValueError, TypeError):
        return None


class DataFetcher:
    """Fetch stock data from FinMind API and TWSE Open Data"""

    # Timestamp-based FinMind cooldown: None = available, otherwise the time it was disabled.
    # FinMind is considered available again after _FINMIND_COOLDOWN_SECS seconds.
    _finmind_disabled_at: Optional[float] = None
    _FINMIND_COOLDOWN_SECS: float = 1800.0  # 30 minutes

    # 兩個獨立 client：
    #   _twse_client    — 僅對 TWSE_HOSTS 使用，套用 _build_twse_ssl_context() 的 verify 設定
    #   _default_client — Yahoo Finance / FinMind 等，維持 httpx 預設嚴格驗證
    _twse_client: Optional[httpx.AsyncClient] = None
    _default_client: Optional[httpx.AsyncClient] = None
    _client_lock = asyncio.Lock()

    _COMMON_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    _COMMON_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=10)

    def __init__(self):
        self.finmind_url = settings.finmind_base_url
        self.twse_url = settings.twse_base_url
        self.token = settings.finmind_api_token
        self.retry_count = settings.api_retry_count
        self.retry_delay = settings.api_retry_delay

    @classmethod
    def _is_finmind_available(cls) -> bool:
        """Return True if FinMind is available (no cooldown active or cooldown expired)."""
        import time
        if cls._finmind_disabled_at is None:
            return True
        elapsed = time.monotonic() - cls._finmind_disabled_at
        if elapsed >= cls._FINMIND_COOLDOWN_SECS:
            cls._finmind_disabled_at = None  # cooldown expired — reset
            logger.info("FinMind cooldown expired; re-enabling FinMind")
            return True
        return False

    @classmethod
    def _mark_finmind_unavailable(cls) -> None:
        """Record the time FinMind was disabled to start the cooldown timer."""
        import time
        cls._finmind_disabled_at = time.monotonic()

    @classmethod
    async def get_twse_client(cls) -> httpx.AsyncClient:
        """取得 TWSE 專用 HTTP Client（套用 twse_ssl_mode 的 SSL 設定）"""
        if cls._twse_client is None or cls._twse_client.is_closed:
            async with cls._client_lock:
                if cls._twse_client is None or cls._twse_client.is_closed:
                    ssl_verify = _build_twse_ssl_context()
                    cls._twse_client = httpx.AsyncClient(
                        verify=ssl_verify,
                        timeout=30.0,
                        limits=cls._COMMON_LIMITS,
                        headers=cls._COMMON_HEADERS,
                    )
        return cls._twse_client

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """取得預設 HTTP Client（Yahoo / FinMind，維持嚴格 SSL 驗證）"""
        if cls._default_client is None or cls._default_client.is_closed:
            async with cls._client_lock:
                if cls._default_client is None or cls._default_client.is_closed:
                    cls._default_client = httpx.AsyncClient(
                        timeout=30.0,
                        limits=cls._COMMON_LIMITS,
                        headers=cls._COMMON_HEADERS,
                    )
        return cls._default_client

    @classmethod
    async def close_client(cls):
        """關閉所有共享的 HTTP Client"""
        for attr in ("_twse_client", "_default_client"):
            client = getattr(cls, attr, None)
            if client and not client.is_closed:
                await client.aclose()
            setattr(cls, attr, None)

    async def fetch_with_retry(self, url: str, params: dict) -> Optional[dict]:
        """Fetch data with retry logic using default client (non-TWSE endpoints)"""
        client = await self.get_client()
        for attempt in range(self.retry_count):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"All retry attempts failed for {url}")
                    return None
        return None

    # TWSE industry code mapping
    INDUSTRY_MAP = {
        "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
        "05": "電機機械", "06": "電器電纜", "07": "化學生技醫療", "08": "玻璃陶瓷",
        "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業",
        "13": "電子工業", "14": "建材營造", "15": "航運業", "16": "觀光事業",
        "17": "金融保險", "18": "貿易百貨", "19": "綜合", "20": "其他",
        "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業",
        "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業", "28": "電子零組件業",
        "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業", "32": "文化創意業",
        "33": "農業科技業", "34": "電商及數位化業", "35": "居家生活業", "36": "觀光餐飲業"
    }

    async def get_stock_list(self) -> pd.DataFrame:
        """Get list of all listed stocks from TWSE OpenAPI"""
        cache_key = "stock_list_twse"
        cached = cache_manager.get(cache_key, "industry")
        if cached is not None:
            return pd.DataFrame(cached)

        # Use TWSE OpenAPI for stock info (uses TWSE SSL client)
        twse_openapi_url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

        try:
            client = await self.get_twse_client()
            response = await client.get(twse_openapi_url)
            response.raise_for_status()
            data = response.json()

            if data:
                stocks = []
                for item in data:
                    symbol = item.get("公司代號", "").strip()
                    if not symbol or symbol.startswith("00"):
                        continue

                    # Parse issued shares (流通股數)
                    shares_str = item.get("已發行普通股數或TDR原股發行股數", "0")
                    try:
                        float_shares = int(shares_str.replace(",", "")) // 1000  # Convert to 張(lots)
                    except (ValueError, AttributeError):
                        float_shares = 0

                    industry_code = item.get("產業別", "")
                    industry_name = self.INDUSTRY_MAP.get(industry_code, "其他")

                    stocks.append({
                        "stock_id": symbol,
                        "stock_name": item.get("公司簡稱", symbol),
                        "industry_category": industry_name,
                        "float_shares": float_shares,
                        "type": "stock"
                    })

                df = pd.DataFrame(stocks)
                logger.info(f"Loaded {len(stocks)} stocks from TWSE OpenAPI")

                # Data integrity check - log stocks with missing fields
                missing_name = [s["stock_id"] for s in stocks if not s.get("stock_name") or s["stock_name"] == s["stock_id"]]
                missing_industry = [s["stock_id"] for s in stocks if not s.get("industry_category") or s["industry_category"] == "其他"]
                missing_shares = [s["stock_id"] for s in stocks if not s.get("float_shares") or s["float_shares"] == 0]

                if missing_name:
                    logger.warning(f"Data integrity: {len(missing_name)} stocks missing name")
                if missing_industry:
                    logger.info(f"Data integrity: {len(missing_industry)} stocks with industry='其他'")
                if missing_shares:
                    logger.warning(f"Data integrity: {len(missing_shares)} stocks missing float_shares")

                cache_manager.set(cache_key, df.to_dict("records"), "industry")
                return df

        except Exception as e:
            logger.error(f"TWSE OpenAPI failed: {e}")

        return pd.DataFrame()

    async def get_daily_data(self, trade_date: str) -> pd.DataFrame:
        """
        Get daily trading data for all stocks on a specific date

        Args:
            trade_date: Date string in YYYY-MM-DD format

        Note:
            TWSE STOCK_DAY_ALL 永遠回傳最新交易日資料，
            快取 key 使用「實際資料日期」而非查詢日期，避免重複請求。
        """
        # 先嘗試用查詢日期找快取
        cache_key = f"daily_{trade_date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return pd.DataFrame(cached)

        # 也嘗試用 canonical key（可能已被其他查詢日期快取）
        canonical_key = cache_manager.get("_daily_canonical_key", "general")
        if canonical_key and canonical_key != cache_key:
            cached = cache_manager.get(canonical_key, "daily")
            if cached is not None:
                # 同時在查詢日期的 key 下也建快取，避免下次 miss
                cache_manager.set(cache_key, cached, "daily")
                return pd.DataFrame(cached)

        # Skip FinMind if cooldown is active
        if not DataFetcher._is_finmind_available():
            logger.debug("Skipping FinMind (cooldown active), using TWSE for daily data")
            return await self._fetch_twse_daily_openapi(trade_date)

        params = {
            "dataset": "TaiwanStockPrice",
            "start_date": trade_date,
            "end_date": trade_date,
        }
        if self.token:
            params["token"] = self.token

        # Try FinMind with single attempt
        try:
            client = await self.get_client()
            response = await client.get(self.finmind_url, params=params, timeout=10.0)
            if response.status_code in (400, 402, 403, 404, 429):
                DataFetcher._mark_finmind_unavailable()
                logger.warning(f"FinMind API error {response.status_code}, switching to TWSE (cooldown 30 min)")
                return await self._fetch_twse_daily_openapi(trade_date)
            response.raise_for_status()
            data = response.json()
            if data and data.get("status") == 200 and data.get("data"):
                df = pd.DataFrame(data["data"])
                cache_manager.set(cache_key, df.to_dict("records"), "daily")
                return df
        except Exception as e:
            logger.warning(f"FinMind daily data failed: {e}")

        # Fallback to TWSE OpenAPI
        return await self._fetch_twse_daily_openapi(trade_date)

    async def _fetch_twse_daily_openapi(self, trade_date: str) -> pd.DataFrame:
        """Fetch daily data from TWSE OpenAPI (more reliable)

        TWSE STOCK_DAY_ALL 永遠回傳最近交易日資料，
        快取 key 使用 API 回傳的實際日期。
        """
        query_cache_key = f"daily_{trade_date}"

        def _parse_num(val, to_float=False):
            """TWSE 資料欄位數值解析（迴圈外定義避免重複建立）"""
            if not val or val == "--":
                return None
            val_str = str(val).replace(",", "")
            try:
                return float(val_str) if to_float else int(float(val_str))
            except (ValueError, TypeError):
                return None

        # Retry TWSE API up to 3 times with backoff
        last_error = None
        for attempt in range(3):
            try:
                url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

                client = await self.get_twse_client()
                response = await client.get(url, timeout=20.0)
                response.raise_for_status()
                data = response.json()

                if not data:
                    logger.warning(f"TWSE OpenAPI returned empty response (attempt {attempt+1})")
                    if attempt < 2:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    return pd.DataFrame()

                stocks = []
                for item in data:
                    try:
                        symbol = item.get("Code", "").strip()
                        if not symbol:
                            continue
                        # Skip ETFs and special securities at data layer
                        if symbol.startswith("00") or len(symbol) > 6:
                            continue
                        if symbol.startswith("7") or symbol.startswith("9"):
                            continue

                        volume = _parse_num(item.get("TradeVolume"))
                        if volume is None or volume < 1000:
                            continue

                        close_price = _parse_num(item.get("ClosingPrice"), True)
                        if close_price is None:
                            continue

                        # Parse date from API (format: 1150128 = 民國115年01月28日)
                        api_date = item.get("Date", "")
                        if api_date and len(api_date) >= 7:
                            roc_year = int(api_date[:3])
                            month = api_date[3:5]
                            day = api_date[5:7]
                            actual_date = f"{roc_year + 1911}-{month}-{day}"
                        else:
                            actual_date = trade_date

                        stocks.append({
                            "stock_id": symbol,
                            "stock_name": item.get("Name", symbol),
                            "Trading_Volume": volume,
                            "open": _parse_num(item.get("OpeningPrice"), True),
                            "max": _parse_num(item.get("HighestPrice"), True),
                            "min": _parse_num(item.get("LowestPrice"), True),
                            "close": close_price,
                            "spread": _parse_num(item.get("Change"), True),
                            "date": actual_date
                        })
                    except Exception:
                        continue

                if stocks:
                    df = pd.DataFrame(stocks)
                    actual_date = stocks[0].get("date", trade_date)
                    actual_cache_key = f"daily_{actual_date}"
                    records = df.to_dict("records")
                    # 用實際日期作為 canonical key
                    cache_manager.set(actual_cache_key, records, "daily")
                    cache_manager.set("_daily_canonical_key", actual_cache_key, "general")
                    # 也用查詢日期快取（避免重複請求）
                    if query_cache_key != actual_cache_key:
                        cache_manager.set(query_cache_key, records, "daily")
                    logger.info(f"Loaded {len(stocks)} stocks from TWSE OpenAPI (date={actual_date})")
                    return df
                else:
                    logger.warning(f"TWSE OpenAPI returned data but 0 stocks parsed (attempt {attempt+1})")
                    if attempt < 2:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue

            except Exception as e:
                last_error = e
                logger.warning(f"TWSE OpenAPI daily fetch attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))

        if last_error:
            logger.error(f"TWSE OpenAPI daily fetch failed after 3 attempts: {last_error}")
        return pd.DataFrame()

    async def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get historical data for a specific stock

        Args:
            symbol: Stock symbol (e.g., "2330")
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
        """
        cache_key = f"history_{symbol}_{start_date}_{end_date}"
        cached = cache_manager.get(cache_key, "historical")
        if cached is not None:
            return pd.DataFrame(cached)

        # Skip FinMind if cooldown is active
        if not DataFetcher._is_finmind_available():
            logger.debug(f"Skipping FinMind (cooldown active), using Yahoo/TWSE for {symbol}")
            df = await self._fetch_twse_historical(symbol, start_date, end_date)
            if not df.empty:
                cache_manager.set(cache_key, df.to_dict("records"), "historical")
            return df

        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": symbol,
            "start_date": start_date,
            "end_date": end_date,
        }
        if self.token:
            params["token"] = self.token

        # Try FinMind with only 1 attempt to fail fast
        try:
            client = await self.get_client()
            response = await client.get(self.finmind_url, params=params, timeout=10.0)
            if response.status_code in (400, 402, 403, 404, 429):
                DataFetcher._mark_finmind_unavailable()
                logger.warning(f"FinMind API error {response.status_code}, switching to TWSE fallback (cooldown 30 min)")
                return await self._fetch_twse_historical(symbol, start_date, end_date)
            response.raise_for_status()
            data = response.json()
            if data and data.get("status") == 200 and data.get("data"):
                df = pd.DataFrame(data["data"])
                if not df.empty:
                    cache_manager.set(cache_key, df.to_dict("records"), "historical")
                return df
        except Exception as e:
            logger.warning(f"FinMind request failed: {e}")

        # Fallback to TWSE
        logger.info(f"Using TWSE fallback for {symbol}")
        df = await self._fetch_twse_historical(symbol, start_date, end_date)
        if not df.empty:
            cache_manager.set(cache_key, df.to_dict("records"), "historical")
        return df

    async def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """Get basic info for a specific stock"""
        stock_list = await self.get_stock_list()
        if stock_list.empty:
            return None

        stock = stock_list[stock_list["stock_id"] == symbol]
        if stock.empty:
            return None

        return stock.iloc[0].to_dict()

    async def get_industries(self) -> List[str]:
        """Get list of all industries"""
        cache_key = "industries"
        cached = cache_manager.get(cache_key, "industry")
        if cached is not None:
            return cached

        stock_list = await self.get_stock_list()
        if stock_list.empty:
            return []

        industries = stock_list["industry_category"].dropna().unique().tolist()
        cache_manager.set(cache_key, industries, "industry")
        return industries

    async def get_date_range_data(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Get data for a date range (for batch operations)"""
        cache_key = f"range_{start_date}_{end_date}"
        cached = cache_manager.get(cache_key, "historical")
        if cached is not None:
            return pd.DataFrame(cached)

        params = {
            "dataset": "TaiwanStockPrice",
            "start_date": start_date,
            "end_date": end_date,
        }
        if self.token:
            params["token"] = self.token

        data = await self.fetch_with_retry(self.finmind_url, params)

        if data and data.get("status") == 200:
            df = pd.DataFrame(data["data"])
            if not df.empty:
                cache_manager.set(cache_key, df.to_dict("records"), "historical")
            return df

        return pd.DataFrame()

    async def _fetch_twse_historical(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fallback: Fetch historical data - try Yahoo first, then TWSE for full range"""
        # 直接先嘗試 Yahoo Finance 抓取完整資料（更穩定）
        logger.info(f"Fetching {symbol} historical data via Yahoo Finance ({start_date} ~ {end_date})")
        yahoo_df = await self._fetch_yahoo_historical(symbol, start_date, end_date)

        # 根據請求的日期範圍計算預期筆數（每月約 22 交易日）
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days_diff = (end_dt - start_dt).days
        expected_records = max(int(days_diff * 0.65), 10)  # 約 65% 是交易日
        # For long requests (≥300 daily rows needed, e.g. weekly MA60 backfill),
        # require at least 80% of expected rows so a short Yahoo response
        # triggers the TWSE fallback instead of silently returning a truncated series.
        # For short requests keep the lenient 30% bar to avoid unnecessary TWSE hits.
        if expected_records >= 300:
            min_acceptable = min(int(expected_records * 0.8), expected_records)
        else:
            min_acceptable = max(int(expected_records * 0.3), 5)

        if not yahoo_df.empty and len(yahoo_df) >= min_acceptable:
            logger.info(f"Yahoo Finance loaded {len(yahoo_df)} records for {symbol} (min={min_acceptable})")
            # 快取 Yahoo 結果
            cache_key = f"history_{symbol}_{start_date}_{end_date}"
            cache_manager.set(cache_key, yahoo_df.to_dict("records"), "historical")
            return yahoo_df

        # #8: 新上市股 Yahoo 列數少屬正常（上市未久）。若資料已更新到近端
        # (最後一筆距 end_date <= 7 天) 且 >= 10 筆，視為完整，直接接受，
        # 避免對每檔新股執行昂貴的 TWSE 逐月迴圈（每檔約 5 秒 / 16 次請求）。
        if not yahoo_df.empty and len(yahoo_df) >= 10:
            try:
                latest = pd.to_datetime(yahoo_df["date"]).max().date()
                if (end_dt.date() - latest).days <= 7:
                    logger.info(
                        f"Accepting Yahoo {len(yahoo_df)} records for {symbol} "
                        f"(up-to-date through {latest}; likely newly listed, skipping TWSE loop)"
                    )
                    cache_key = f"history_{symbol}_{start_date}_{end_date}"
                    cache_manager.set(cache_key, yahoo_df.to_dict("records"), "historical")
                    return yahoo_df
            except Exception:
                pass

        # 如果 Yahoo 資料不足，嘗試 TWSE（通常會被 307 擋）
        logger.info(f"Yahoo data insufficient ({len(yahoo_df) if not yahoo_df.empty else 0} records), trying TWSE for {symbol}")

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            all_data = []
            current = start_dt

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.twse.com.tw/",
            }

            consecutive_failures = 0
            while current <= end_dt and consecutive_failures < 3:
                url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
                params = {
                    "date": current.strftime("%Y%m%d"),
                    "stockNo": symbol,
                    "response": "json",
                }

                try:
                    client = await self.get_twse_client()
                    response = await client.get(url, params=params, timeout=15.0, follow_redirects=True)
                    if response.status_code == 307:
                        consecutive_failures += 1
                        current = self._next_month(current)
                        continue

                    if response.status_code == 200:
                        consecutive_failures = 0
                        try:
                            data = response.json()
                        except (ValueError, Exception):
                            current = self._next_month(current)
                            continue

                        if data.get("stat") == "OK" and data.get("data"):
                            for row in data["data"]:
                                try:
                                    date_parts = row[0].split("/")
                                    if len(date_parts) == 3:
                                        year = int(date_parts[0]) + 1911
                                        month = int(date_parts[1])
                                        day = int(date_parts[2])
                                        row_date = date(year, month, day)

                                        if start_dt.date() <= row_date <= end_dt.date():
                                            all_data.append({
                                                "date": row_date.strftime("%Y-%m-%d"),
                                                "stock_id": symbol,
                                                "Trading_Volume": parse_number(row[1]),
                                                "open": parse_number(row[3], True),
                                                "max": parse_number(row[4], True),
                                                "min": parse_number(row[5], True),
                                                "close": parse_number(row[6], True),
                                                "spread": parse_number(row[7], True),
                                            })
                                except (ValueError, IndexError):
                                    continue
                except Exception as e:
                    logger.warning(f"TWSE fetch failed for {symbol} {current.strftime('%Y-%m')}: {e}")
                    consecutive_failures += 1

                current = self._next_month(current)
                await asyncio.sleep(0.3)

            if all_data and len(all_data) > len(yahoo_df if not yahoo_df.empty else []):
                df = pd.DataFrame(all_data)
                logger.info(f"TWSE loaded {len(df)} records for {symbol}")
                return df

        except Exception as e:
            logger.error(f"TWSE historical failed for {symbol}: {e}")

        # 返回 Yahoo 資料（即使不完整也比沒有好）
        if not yahoo_df.empty:
            return yahoo_df

        return pd.DataFrame()

    def _next_month(self, dt: datetime) -> datetime:
        """Get first day of next month"""
        if dt.month == 12:
            return datetime(dt.year + 1, 1, 1)
        return datetime(dt.year, dt.month + 1, 1)

    async def _fetch_yahoo_historical(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch historical data from Yahoo Finance API"""
        try:
            # Yahoo Finance uses .TW suffix for Taiwan stocks,
            # but special symbols like ^TWII, ^DJI etc. are already fully qualified
            if symbol.startswith("^") or "." in symbol:
                yahoo_symbol = symbol
            else:
                yahoo_symbol = f"{symbol}.TW"

            # Calculate range based on date difference
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days_diff = (end_dt - start_dt).days

            # Select appropriate range - always use max for 5 year requests
            if days_diff <= 7:
                range_param = "5d"
            elif days_diff <= 30:
                range_param = "1mo"
            elif days_diff <= 90:
                range_param = "3mo"
            elif days_diff <= 180:
                range_param = "6mo"
            elif days_diff <= 365:
                range_param = "1y"
            elif days_diff <= 730:
                range_param = "2y"
            elif days_diff <= 1825:
                range_param = "5y"
            else:
                range_param = "max"

            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            params = {
                "interval": "1d",
                "range": range_param,
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            }

            client = await self.get_client()
            response = await client.get(url, params=params)
            if response.status_code == 200:
                    data = response.json()
                    result = data.get("chart", {}).get("result", [])

                    if result and len(result) > 0:
                        chart_data = result[0]
                        timestamps = chart_data.get("timestamp", [])
                        quote = chart_data.get("indicators", {}).get("quote", [{}])[0]

                        if timestamps:
                            records = []
                            opens = quote.get("open", [])
                            highs = quote.get("high", [])
                            lows = quote.get("low", [])
                            closes = quote.get("close", [])
                            volumes = quote.get("volume", [])

                            for i, ts in enumerate(timestamps):
                                try:
                                    from datetime import timezone
                                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                                    # Filter by date range
                                    if start_dt.date() <= dt.date() <= end_dt.date():
                                        open_val = opens[i] if i < len(opens) else None
                                        high_val = highs[i] if i < len(highs) else None
                                        low_val = lows[i] if i < len(lows) else None
                                        close_val = closes[i] if i < len(closes) else None
                                        vol_val = volumes[i] if i < len(volumes) else None

                                        # Skip if no valid price data
                                        if close_val is None:
                                            continue

                                        records.append({
                                            "date": dt.strftime("%Y-%m-%d"),
                                            "stock_id": symbol,
                                            "open": open_val,
                                            "max": high_val,
                                            "min": low_val,
                                            "close": close_val,
                                            "Trading_Volume": vol_val,
                                        })
                                except (ValueError, TypeError, IndexError):
                                    continue

                            if records:
                                df = pd.DataFrame(records)
                                logger.info(f"Yahoo Finance loaded {len(df)} records for {symbol}")
                                return df

        except Exception as e:
            logger.warning(f"Yahoo Finance fetch failed for {symbol}: {e}")

        return pd.DataFrame()

    async def is_trading_day(self, check_date: str) -> bool:
        """Check if a date is a trading day by verifying data exists"""
        df = await self.get_daily_data(check_date)
        return not df.empty

    async def verify_trading_day_via_api(self, check_date: str) -> bool:
        """
        Verify if a date is a trading day by checking TWSE API
        More lightweight than fetching full daily data
        """
        try:
            date_obj = datetime.strptime(check_date, "%Y-%m-%d")
            twse_date = date_obj.strftime("%Y%m%d")

            # Use TWSE MI_INDEX endpoint (lighter than full stock data)
            url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
            params = {"date": twse_date, "response": "json"}

            client = await self.get_twse_client()
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 200:
                    data = response.json()
                    # Check if there's actual trading data
                    if data.get("stat") == "OK":
                        # Check for actual data presence
                        tables = data.get("tables", [])
                        if tables and len(tables) > 0:
                            logger.info(f"Verified {check_date} is a trading day via TWSE API")
                            return True
            return False
        except Exception as e:
            logger.warning(f"API verification for {check_date} failed: {e}")
            return False

    async def get_latest_trading_date(self) -> str:
        """
        Get the most recent trading date

        策略（零 API 呼叫）：
        1. 用日曆推算最近的交易日
        2. 使用快取結果避免重複計算
        3. 不再呼叫 verify_trading_day_via_api，因為會增加 0.5 秒延遲
        """
        from utils.date_utils import get_previous_trading_day, format_date

        cache_key = "latest_trading_date"
        cached = cache_manager.get(cache_key, "general")
        if cached:
            return cached

        result = format_date(get_previous_trading_day())
        cache_manager.set(cache_key, result, "general")
        logger.info(f"Latest trading date (calendar): {result}")
        return result

    async def get_realtime_quotes(self, symbols: List[str]) -> List[Dict]:
        """
        盤中即時報價 — TWSE MIS API (免費、官方、無需註冊)
        每次最多 50 檔，建議間隔 3 秒
        """
        cache_key = f"realtime_{'_'.join(sorted(symbols))}"
        cached = cache_manager.get(cache_key, "realtime")
        if cached:
            return cached

        # Query both tse_ (上市) and otc_ (上櫃) channels for every symbol.
        # TWSE MIS accepts multiple "|"-joined channels in a single request and
        # returns only the channels that have data, so symbols listed under the
        # wrong market type are simply absent from the response — no fake zeros.
        batch = symbols[:50]
        ex_ch = "|".join(
            f"tse_{s}.tw|otc_{s}.tw" for s in batch
        )
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

        try:
            client = await self.get_twse_client()
            resp = await client.get(url, params={"ex_ch": ex_ch}, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("msgArray", []):
                z = item.get("z", "-")  # 成交價
                if z == "-" or z == "":
                    z = item.get("y", "-")  # 沒成交用昨收

                # Skip items where we still have no usable price — do NOT coerce
                # to 0, which would fabricate a fake quote.
                if z == "-" or z == "":
                    continue

                try:
                    close = float(z)
                    yesterday = float(item.get("y", "0") or "0")
                    change = round(close - yesterday, 2) if yesterday else 0
                    change_pct = round(change / yesterday * 100, 2) if yesterday else 0
                except (ValueError, ZeroDivisionError):
                    continue  # skip rather than emit fake zeros

                results.append({
                    "stock_id": item.get("c", ""),
                    "stock_name": item.get("n", ""),
                    "close": close,
                    "open": float(item.get("o", "0") or "0"),
                    "high": float(item.get("h", "0") or "0"),
                    "low": float(item.get("l", "0") or "0"),
                    "volume": int(float(item.get("v", "0") or "0")),
                    "yesterday_close": yesterday,
                    "change": change,
                    "change_pct": change_pct,
                    "time": item.get("t", ""),
                    "realtime": True,
                })

            if results:
                cache_manager.set(cache_key, results, "realtime")
            return results

        except Exception as e:
            logger.warning(f"TWSE MIS realtime failed: {e}")
            return []

    async def get_institutional_net(self) -> pd.DataFrame:
        """
        三大法人買賣超 (個股) — TWSE RWD T86 (最近交易日全市場)。
        回傳 DataFrame[stock_id, foreign_buy, trust_buy]（單位：股，可為負）。
        欄位順序固定：0=證券代號, 4=外陸資買賣超股數(不含外資自營商), 10=投信買賣超股數。
        """
        cache_key = "inst_net_daily"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return pd.DataFrame(cached)

        url = "https://www.twse.com.tw/rwd/zh/fund/T86"
        try:
            client = await self.get_twse_client()
            resp = await client.get(
                url, params={"response": "json", "selectType": "ALL"},
                timeout=20.0, follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data or data.get("stat") != "OK" or not data.get("data"):
                logger.warning("T86 institutional data unavailable (stat != OK)")
                return pd.DataFrame()

            rows = []
            for r in data["data"]:
                if len(r) < 11:
                    continue
                rows.append({
                    "stock_id": str(r[0]).strip(),
                    "foreign_buy": parse_number(r[4]),
                    "trust_buy": parse_number(r[10]),
                })
            df = pd.DataFrame(rows)
            if not df.empty:
                cache_manager.set(cache_key, df.to_dict("records"), "daily")
            logger.info(f"T86 institutional: {len(df)} rows (date={data.get('date')})")
            return df
        except Exception as e:
            logger.warning(f"T86 institutional fetch failed: {e}")
            return pd.DataFrame()

    async def get_margin_balance(self) -> pd.DataFrame:
        """
        融資餘額 (個股) — TWSE OpenAPI MI_MARGN (最近交易日全市場)。
        回傳 DataFrame[stock_id, margin_balance]（單位：張）。
        """
        cache_key = "margin_balance_daily"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return pd.DataFrame(cached)

        url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
        try:
            client = await self.get_twse_client()
            resp = await client.get(url, timeout=20.0, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list) or not data:
                return pd.DataFrame()

            rows = []
            for item in data:
                sid = str(item.get("股票代號", "")).strip()
                if not sid:
                    continue
                rows.append({
                    "stock_id": sid,
                    "margin_balance": parse_number(item.get("融資今日餘額")),
                })
            df = pd.DataFrame(rows)
            if not df.empty:
                cache_manager.set(cache_key, df.to_dict("records"), "daily")
            logger.info(f"MI_MARGN margin: {len(df)} rows")
            return df
        except Exception as e:
            logger.warning(f"MI_MARGN margin fetch failed: {e}")
            return pd.DataFrame()

    async def get_per_pbr(self) -> pd.DataFrame:
        """
        本益比 / 股價淨值比 (個股) — TWSE OpenAPI BWIBBU_ALL (最近交易日全市場)。
        回傳 DataFrame[stock_id, pe_ratio, pbr]。PEratio 可能為空字串 → None。
        """
        cache_key = "per_pbr_daily"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return pd.DataFrame(cached)

        url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        try:
            client = await self.get_twse_client()
            resp = await client.get(url, timeout=20.0, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list) or not data:
                return pd.DataFrame()

            rows = []
            for item in data:
                sid = str(item.get("Code", "")).strip()
                if not sid:
                    continue
                rows.append({
                    "stock_id": sid,
                    "pe_ratio": parse_number(item.get("PEratio"), True),
                    "pbr": parse_number(item.get("PBratio"), True),
                })
            df = pd.DataFrame(rows)
            if not df.empty:
                cache_manager.set(cache_key, df.to_dict("records"), "daily")
            logger.info(f"BWIBBU_ALL per/pbr: {len(df)} rows")
            return df
        except Exception as e:
            logger.warning(f"BWIBBU_ALL per/pbr fetch failed: {e}")
            return pd.DataFrame()


# Global instance
data_fetcher = DataFetcher()
