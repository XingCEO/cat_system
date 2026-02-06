"""
Date Utils - 日期相關工具函數
"""
from datetime import datetime, date, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Taiwan Stock Exchange holidays (major ones - add more as needed)
# Format: (month, day)
TW_HOLIDAYS_2024 = [
    (1, 1),   # New Year's Day
    (2, 8), (2, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14),  # Chinese New Year
    (2, 28),  # Peace Memorial Day
    (4, 4), (4, 5),  # Children's Day, Tomb Sweeping Day
    (5, 1),   # Labor Day
    (6, 10),  # Dragon Boat Festival
    (9, 17),  # Mid-Autumn Festival
    (10, 10), (10, 11),  # National Day
]

TW_HOLIDAYS_2025 = [
    (1, 1),   # New Year's Day
    (1, 27), (1, 28), (1, 29), (1, 30), (1, 31),  # Chinese New Year
    (2, 28),  # Peace Memorial Day
    (4, 3), (4, 4),  # Children's Day, Tomb Sweeping Day
    (5, 1),   # Labor Day
    (5, 31),  # Dragon Boat Festival
    (10, 6),  # Mid-Autumn Festival
    (10, 10),  # National Day
]

TW_HOLIDAYS_2026 = [
    (1, 1),   # New Year's Day
    (2, 16), (2, 17), (2, 18), (2, 19), (2, 20),  # Chinese New Year
    (2, 27), (2, 28),  # Peace Memorial Day (weekend included)
    (4, 3), (4, 4), (4, 5), (4, 6),  # Children's Day, Tomb Sweeping Day
    (5, 1),   # Labor Day
    (5, 19),  # Dragon Boat Festival
    (9, 25),  # Mid-Autumn Festival
    (10, 9), (10, 10),  # National Day
]


def _get_holidays_for_year(year: int) -> List[tuple]:
    """取得指定年份的假日"""
    if year == 2024:
        return TW_HOLIDAYS_2024
    elif year == 2025:
        return TW_HOLIDAYS_2025
    elif year == 2026:
        return TW_HOLIDAYS_2026
    return []


def is_trading_day(check_date: date) -> bool:
    """
    判斷是否為交易日
    - 週六日不交易
    - 國定假日不交易
    """
    # Weekend check
    if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Holiday check
    holidays = _get_holidays_for_year(check_date.year)
    if (check_date.month, check_date.day) in holidays:
        return False
    
    return True


def get_previous_trading_day(from_date: Optional[date] = None) -> date:
    """
    取得最近的交易日（包含今天，如果今天是交易日）
    若今天非交易日，則往前找最近的交易日
    """
    if from_date is None:
        from_date = date.today()
    
    current = from_date
    max_lookback = 10  # Avoid infinite loop
    
    for _ in range(max_lookback):
        if is_trading_day(current):
            return current
        current -= timedelta(days=1)
    
    # Fallback: return input date
    return from_date


def get_latest_trading_day() -> str:
    """
    取得最近交易日的字串格式
    
    Returns:
        日期字串 YYYY-MM-DD
    """
    trading_day = get_previous_trading_day()
    return format_date(trading_day)


def get_past_trading_days(days: int = 5, from_date: Optional[date] = None) -> List[str]:
    """
    取得過去 N 個交易日
    
    Args:
        days: 要取得的交易日數量
        from_date: 起始日期（預設今天）
    
    Returns:
        交易日列表 ['YYYY-MM-DD', ...]
    """
    if from_date is None:
        from_date = date.today()
    
    result = []
    current = from_date
    max_lookback = days * 3  # Account for weekends and holidays
    
    for _ in range(max_lookback):
        if len(result) >= days:
            break
        if is_trading_day(current):
            result.append(format_date(current))
        current -= timedelta(days=1)
    
    return result


def get_trading_days(start_date, end_date) -> List[str]:
    """
    取得兩個日期之間的所有交易日
    
    Args:
        start_date: 起始日期 (date 物件或 YYYY-MM-DD 字串)
        end_date: 結束日期 (date 物件或 YYYY-MM-DD 字串)
    
    Returns:
        交易日列表 ['YYYY-MM-DD', ...]
    """
    # 支援 date 或 str 類型
    if isinstance(start_date, str):
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        start = start_date
        
    if isinstance(end_date, str):
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        end = end_date
    
    result = []
    current = start
    
    while current <= end:
        if is_trading_day(current):
            result.append(format_date(current))
        current += timedelta(days=1)
    
    return result


def format_date(dt: date) -> str:
    """
    格式化日期為字串
    
    Args:
        dt: date 物件
    
    Returns:
        日期字串 YYYY-MM-DD
    """
    return dt.strftime("%Y-%m-%d")


def parse_date(date_str: str) -> Optional[date]:
    """
    解析日期字串

    Args:
        date_str: YYYY-MM-DD 格式字串

    Returns:
        date 物件或 None
    """
    if date_str is None:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def validate_date_str(date_str: str) -> bool:
    """
    驗證日期字串格式是否正確

    Args:
        date_str: YYYY-MM-DD 格式字串

    Returns:
        True 如果格式正確，否則 False
    """
    return parse_date(date_str) is not None


def get_trading_days_between(start_date, end_date) -> List[date]:
    """
    取得兩個日期之間的所有交易日 (回傳 date 物件列表)

    Args:
        start_date: 起始日期 (date 物件或 YYYY-MM-DD 字串)
        end_date: 結束日期 (date 物件或 YYYY-MM-DD 字串)

    Returns:
        交易日列表 [date, ...]
    """
    if isinstance(start_date, str):
        start = parse_date(start_date)
    else:
        start = start_date

    if isinstance(end_date, str):
        end = parse_date(end_date)
    else:
        end = end_date

    if start is None or end is None:
        return []

    result = []
    current = start

    while current <= end:
        if is_trading_day(current):
            result.append(current)
        current += timedelta(days=1)

    return result


def days_between(date1: str, date2: str) -> int:
    """
    計算兩個日期之間的天數差
    
    Args:
        date1, date2: YYYY-MM-DD 格式字串
    
    Returns:
        天數差（絕對值）
    """
    d1 = parse_date(date1)
    d2 = parse_date(date2)
    
    if d1 is None or d2 is None:
        return 0
    
    return abs((d2 - d1).days)
