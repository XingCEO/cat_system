"""
Data Fetcher - FinMind API + TWSE Open Data
"""
import json
import httpx
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union
import asyncio
import logging

from config import get_settings
from services.cache_manager import cache_manager

settings = get_settings()
logger = logging.getLogger(__name__)


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

    # Class-level flag to skip FinMind when it's unavailable
    _finmind_available = True
    # Shared HTTP client for connection pooling
    _http_client: Optional[httpx.AsyncClient] = None
    _client_lock = asyncio.Lock()

    def __init__(self):
        self.finmind_url = settings.finmind_base_url
        self.twse_url = settings.twse_base_url
        self.token = settings.finmind_api_token
        self.retry_count = settings.api_retry_count
        self.retry_delay = settings.api_retry_delay

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """取得共享的 HTTP Client（連線池重用）"""
        if cls._http_client is None or cls._http_client.is_closed:
            async with cls._client_lock:
                if cls._http_client is None or cls._http_client.is_closed:
                    cls._http_client = httpx.AsyncClient(
                        timeout=30.0,
                        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                        headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                        }
                    )
        return cls._http_client

    @classmethod
    async def close_client(cls):
        """關閉共享的 HTTP Client"""
        if cls._http_client and not cls._http_client.is_closed:
            await cls._http_client.aclose()
            cls._http_client = None
    
    async def fetch_with_retry(self, url: str, params: dict) -> Optional[dict]:
        """Fetch data with retry logic using shared client"""
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

        # Use TWSE OpenAPI for stock info
        twse_openapi_url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

        try:
            client = await self.get_client()
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
                    except (ValueError, TypeError):
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
        """
        cache_key = f"daily_{trade_date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return pd.DataFrame(cached)

        # Skip FinMind if unavailable
        if not DataFetcher._finmind_available:
            logger.debug("Skipping FinMind (unavailable), using TWSE for daily data")
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
            if response.status_code == 402:
                DataFetcher._finmind_available = False
                logger.warning("FinMind API quota exceeded, switching to TWSE")
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
        """Fetch daily data from TWSE OpenAPI (more reliable)"""
        cache_key = f"daily_{trade_date}"

        try:
            # Use TWSE OpenAPI - returns today's data
            url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

            client = await self.get_client()
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data:
                stocks = []
                for item in data:
                    try:
                        symbol = item.get("Code", "").strip()
                        # Skip ETFs and special securities
                        if symbol.startswith("00") or len(symbol) > 6:
                            continue
                        if symbol.startswith("7") or symbol.startswith("9"):
                            continue

                        def parse_num(val, to_float=False):
                            if not val or val == "--":
                                return None
                            val_str = str(val).replace(",", "")
                            try:
                                return float(val_str) if to_float else int(float(val_str))
                            except (ValueError, TypeError):
                                return None

                        volume = parse_num(item.get("TradeVolume"))
                        if volume is None or volume < 1000:
                            continue

                        close_price = parse_num(item.get("ClosingPrice"), True)
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
                            "open": parse_num(item.get("OpeningPrice"), True),
                            "max": parse_num(item.get("HighestPrice"), True),
                            "min": parse_num(item.get("LowestPrice"), True),
                            "close": close_price,
                            "spread": parse_num(item.get("Change"), True) or 0,
                            "date": actual_date
                        })
                    except Exception as e:
                        continue

                if stocks:
                    df = pd.DataFrame(stocks)
                    logger.info(f"Loaded {len(stocks)} stocks from TWSE OpenAPI")
                    cache_manager.set(cache_key, df.to_dict("records"), "daily")
                    return df

        except Exception as e:
            logger.error(f"TWSE OpenAPI daily fetch failed: {e}")

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

        # Skip FinMind if it's been marked unavailable (402 error)
        if not DataFetcher._finmind_available:
            logger.debug(f"Skipping FinMind (unavailable), using TWSE for {symbol}")
            return await self._fetch_twse_historical(symbol, start_date, end_date)

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
            if response.status_code == 402:
                # Mark FinMind as unavailable for this session
                DataFetcher._finmind_available = False
                logger.warning("FinMind API quota exceeded (402), switching to TWSE fallback for all requests")
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
        return await self._fetch_twse_historical(symbol, start_date, end_date)
    
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
    
    async def _fetch_twse_daily(self, trade_date: str) -> pd.DataFrame:
        """Fallback: Fetch from TWSE Open Data"""
        try:
            # Convert date format for TWSE (YYYYMMDD)
            date_obj = datetime.strptime(trade_date, "%Y-%m-%d")
            twse_date = date_obj.strftime("%Y%m%d")

            # Use STOCK_DAY_ALL endpoint for all stock daily data
            url = f"{self.twse_url}/STOCK_DAY_ALL"
            params = {
                "response": "json",
                "date": twse_date,
            }

            data = await self.fetch_with_retry(url, params)

            if data and data.get("stat") == "OK" and data.get("data"):
                # Parse TWSE STOCK_DAY_ALL format
                # Columns: [0]代號, [1]名稱, [2]成交股數, [3]成交金額, [4]開盤, [5]最高, [6]最低, [7]收盤, [8]漲跌價差, [9]成交筆數
                rows = data["data"]
                stocks = []

                # Parse values with comma removal
                def parse_num(val, to_float=False):
                    if val == "--" or val == "" or val is None:
                        return None
                    val_str = str(val).replace(",", "").replace("+", "").replace(" ", "")
                    try:
                        return float(val_str) if to_float else int(float(val_str))
                    except (ValueError, TypeError):
                        return None

                for row in rows:
                    try:
                        symbol = str(row[0]).strip()
                        # Skip ETFs (0050, 006208, etc) and special securities
                        if symbol.startswith("00") or len(symbol) > 6:
                            continue
                        # Skip special types (warrants start with 7, etc)
                        if symbol.startswith("7") or symbol.startswith("9"):
                            continue

                        volume = parse_num(row[2])
                        if volume is None or volume < 1000:  # Skip low volume
                            continue

                        close_price = parse_num(row[7], True)  # Column 7 is 收盤價
                        if close_price is None:
                            continue

                        # Calculate spread from change string (Column 8)
                        spread = parse_num(row[8], True) or 0

                        stocks.append({
                            "stock_id": symbol,
                            "stock_name": str(row[1]).strip(),
                            "Trading_Volume": volume,
                            "open": parse_num(row[4], True),   # Column 4 is 開盤
                            "max": parse_num(row[5], True),    # Column 5 is 最高
                            "min": parse_num(row[6], True),    # Column 6 is 最低
                            "close": close_price,              # Column 7 is 收盤
                            "spread": spread,                  # Column 8 is 漲跌價差
                            "date": trade_date
                        })
                    except (ValueError, IndexError, TypeError) as e:
                        continue

                logger.info(f"Loaded {len(stocks)} stocks from TWSE for {trade_date}")
                return pd.DataFrame(stocks)

        except Exception as e:
            logger.error(f"TWSE fallback failed: {e}")

        return pd.DataFrame()

    async def _fetch_twse_historical(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fallback: Fetch historical data - try TWSE first, then Yahoo Finance for full range"""
        # 直接先嘗試 Yahoo Finance 抓取完整資料（更穩定）
        logger.info(f"Fetching {symbol} historical data via Yahoo Finance ({start_date} ~ {end_date})")
        yahoo_df = await self._fetch_yahoo_historical(symbol, start_date, end_date)

        if not yahoo_df.empty and len(yahoo_df) >= 100:
            logger.info(f"Yahoo Finance loaded {len(yahoo_df)} records for {symbol}")
            return yahoo_df

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
                    client = await self.get_client()
                    response = await client.get(url, params=params, timeout=15.0, follow_redirects=True)
                    if response.status_code == 307:
                        consecutive_failures += 1
                        current = self._next_month(current)
                        continue

                    if response.status_code == 200:
                        consecutive_failures = 0
                        try:
                            data = response.json()
                        except (ValueError, json.JSONDecodeError):
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
            # Yahoo Finance uses .TW suffix for Taiwan stocks
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
                                    dt = datetime.fromtimestamp(ts)
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
                                except (ValueError, IndexError, TypeError):
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
            
            client = await self.get_client()
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
        
        Strategy:
        1. First use date_utils for fast calendar-based check (no API call)
        2. If calendar says it should be trading day, verify with lightweight API
        3. Cache result to avoid repeated API calls
        """
        from utils.date_utils import get_previous_trading_day, format_date, is_trading_day as calendar_is_trading_day
        
        # Check cache first
        cache_key = "latest_trading_date"
        cached = cache_manager.get(cache_key, "general")
        if cached:
            logger.debug(f"Using cached latest trading date: {cached}")
            return cached
        
        today = date.today()
        
        # Fast path: use calendar-based check first
        for i in range(10):  # Check last 10 days
            check_date = today - timedelta(days=i)
            date_str = check_date.strftime("%Y-%m-%d")
            
            # Skip weekends and known holidays (fast, no API)
            if not calendar_is_trading_day(check_date):
                logger.debug(f"{date_str} is non-trading (calendar)")
                continue
            
            # For today, verify with API (market might not be open yet)
            if i == 0:
                # Use lightweight API verification
                if await self.verify_trading_day_via_api(date_str):
                    logger.info(f"Latest trading date (verified): {date_str}")
                    cache_manager.set(cache_key, date_str, "general")
                    return date_str
                else:
                    logger.debug(f"Today {date_str} has no trading data yet")
                    continue
            
            # For past dates, calendar check is usually sufficient
            # But we can do a quick API verify to be sure
            logger.info(f"Latest trading date (calendar): {date_str}")
            cache_manager.set(cache_key, date_str, "general")
            return date_str
        
        # Fallback: use date_utils
        fallback = format_date(get_previous_trading_day(today))
        logger.warning(f"Using fallback trading date: {fallback}")
        return fallback


# Global instance
data_fetcher = DataFetcher()

