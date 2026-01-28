"""
Data Fetcher - FinMind API + TWSE Open Data
"""
import httpx
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import asyncio
import logging

from config import get_settings
from services.cache_manager import cache_manager

settings = get_settings()
logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetch stock data from FinMind API and TWSE Open Data"""
    
    def __init__(self):
        self.finmind_url = settings.finmind_base_url
        self.twse_url = settings.twse_base_url
        self.token = settings.finmind_api_token
        self.retry_count = settings.api_retry_count
        self.retry_delay = settings.api_retry_delay
    
    async def fetch_with_retry(self, url: str, params: dict) -> Optional[dict]:
        """Fetch data with retry logic"""
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    except:
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
        
        params = {
            "dataset": "TaiwanStockPrice",
            "start_date": trade_date,
            "end_date": trade_date,
        }
        if self.token:
            params["token"] = self.token
        
        data = await self.fetch_with_retry(self.finmind_url, params)
        
        if data and data.get("status") == 200 and data.get("data"):
            df = pd.DataFrame(data["data"])
            cache_manager.set(cache_key, df.to_dict("records"), "daily")
            return df
        
        # Fallback to TWSE if FinMind fails
        return await self._fetch_twse_daily(trade_date)
    
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
        
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": symbol,
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
                    except:
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
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
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

