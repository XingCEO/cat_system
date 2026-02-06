"""
Constants - Centralized configuration values
Avoids magic numbers scattered throughout the codebase
"""
from typing import Dict, List

# ===== Stock Analysis Constants =====
TOP_N_TURNOVER = 200  # 取周轉率前N名
TOP_20_TURNOVER = 20  # 精選前20名

# Limit up/down thresholds
LIMIT_UP_THRESHOLD = 9.9  # 漲停判定門檻 (%) - 台股使用9.9%
LIMIT_DOWN_THRESHOLD = -9.9  # 跌停判定門檻 (%)

# Price tick rules for Taiwan stocks
PRICE_TICK_RULES = [
    (10, 0.01),
    (50, 0.05),
    (100, 0.1),
    (500, 0.5),
    (1000, 1.0),
    (float('inf'), 5.0),
]

# ===== Volume Constants =====
MIN_VOLUME_THRESHOLD = 500  # 最小成交量門檻 (張)
MIN_VOLUME_FILTER = 1000  # 成交量過濾 (張)
SEAL_VOLUME_THRESHOLD = 5000  # 封單門檻 (張)

# ===== Price Constants =====
LOW_PRICE_THRESHOLD = 30.0  # 低價股門檻
MAX_PRICE_SANITY = 10000  # 價格合理上限

# ===== MA (Moving Average) Constants =====
MA_PERIODS = {
    "MA5": 5,
    "MA10": 10,
    "MA20": 20,
    "MA60": 60,
    "MA120": 120,
}
MA_TANGLE_THRESHOLD = 0.03  # 均線糾結判定 (3%)
TRADING_DAYS_PER_YEAR = 252  # 年交易日數

# ===== Date Constants =====
DEFAULT_START_DATE = "2021-01-01"
MAX_HISTORY_DAYS = 365  # 最大查詢天數
DEFAULT_HISTORY_DAYS = 60

# ===== API Rate Limiting =====
BATCH_SIZE = 80  # 每批請求股票數
BATCH_DELAY = 1.5  # 批次間隔 (秒)
REQUEST_TIMEOUT = 10  # 請求超時 (秒)
MAX_RETRIES = 3  # 最大重試次數
MIN_REQUEST_INTERVAL = 1.0  # 最小請求間隔 (秒)

# ===== Cache Constants =====
CACHE_MAX_SIZE = 500  # 最大快取數量
CACHE_TTL_REALTIME = 15  # 即時報價快取 (秒)
CACHE_TTL_DAILY = 300  # 日線快取 (秒)
CACHE_TTL_HISTORICAL = 86400  # 歷史資料快取 (秒)

# ===== Calculation Constants =====
AMOUNT_TO_BILLION = 100000000  # 成交金額轉億元
SHARES_PER_LOT = 1000  # 每張股數

# ===== Percentage Validation =====
PERCENT_MIN = -100
PERCENT_MAX = 1000

# ===== Server Constants =====
DEFAULT_PORT = 8000
MAX_PORT_ATTEMPTS = 10

# ===== Preset Filters =====
PRESETS: Dict[str, Dict] = {
    "strong_retail": {  # 超強游資股
        "min_turnover_rate": 20.0,
        "max_open_count": 1
    },
    "demon": {  # 妖股候選
        "max_rank": 20,
        "min_consecutive_limit_up": 2
    },
    "big_player": {  # 大戶進場
        "min_turnover_rate": 15.0,
        "min_seal_volume": SEAL_VOLUME_THRESHOLD
    },
    "low_price": {  # 低價飆股
        "price_max": LOW_PRICE_THRESHOLD
    }
}

# ===== HTTP Status Codes =====
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500
