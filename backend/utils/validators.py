"""
Validators - Input validation utilities
"""
from datetime import datetime, date
from typing import Optional, Tuple
import re


def validate_symbol(symbol: str) -> Tuple[bool, Optional[str]]:
    """
    Validate stock symbol format
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not symbol:
        return False, "股票代號不可為空"
    
    # Taiwan stock symbols are typically 4-6 digits
    if not re.match(r"^\d{4,6}$", symbol):
        return False, f"無效的股票代號格式: {symbol}"
    
    return True, None


def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate date string format
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not date_str:
        return True, None  # Optional field
    
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Check reasonable range (2000 to today + 1 day)
        if parsed.year < 2000:
            return False, "日期不可早於 2000 年"
        
        if parsed.date() > date.today():
            return False, "日期不可為未來日期"
        
        return True, None
    except ValueError:
        return False, f"無效的日期格式: {date_str}，請使用 YYYY-MM-DD 格式"


def validate_date_range(
    start_date: str, 
    end_date: str, 
    max_days: int = 365
) -> Tuple[bool, Optional[str]]:
    """
    Validate date range
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Validate individual dates
    valid, error = validate_date(start_date)
    if not valid:
        return False, error
    
    valid, error = validate_date(end_date)
    if not valid:
        return False, error
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    if start > end:
        return False, "開始日期不可晚於結束日期"
    
    days_diff = (end - start).days
    if days_diff > max_days:
        return False, f"日期範圍不可超過 {max_days} 天"
    
    return True, None


def validate_percentage_range(
    min_val: Optional[float],
    max_val: Optional[float],
    field_name: str = "值"
) -> Tuple[bool, Optional[str]]:
    """Validate percentage range"""
    if min_val is not None and max_val is not None:
        if min_val > max_val:
            return False, f"{field_name}下限不可大於上限"
    
    if min_val is not None and (min_val < -100 or min_val > 1000):
        return False, f"{field_name}下限超出合理範圍 (-100% ~ 1000%)"
    
    if max_val is not None and (max_val < -100 or max_val > 1000):
        return False, f"{field_name}上限超出合理範圍 (-100% ~ 1000%)"
    
    return True, None


def validate_volume(volume: Optional[int]) -> Tuple[bool, Optional[str]]:
    """Validate volume value"""
    if volume is not None and volume < 0:
        return False, "成交量不可為負數"
    return True, None


def validate_price(
    min_price: Optional[float],
    max_price: Optional[float]
) -> Tuple[bool, Optional[str]]:
    """Validate price range"""
    if min_price is not None and min_price <= 0:
        return False, "價格下限必須大於 0"
    
    if max_price is not None and max_price <= 0:
        return False, "價格上限必須大於 0"
    
    if min_price is not None and max_price is not None:
        if min_price > max_price:
            return False, "價格下限不可大於上限"
    
    return True, None


def sanitize_string(value: str, max_length: int = 100) -> str:
    """Sanitize string input"""
    if not value:
        return ""
    
    # Remove leading/trailing whitespace
    value = value.strip()
    
    # Truncate if too long
    if len(value) > max_length:
        value = value[:max_length]
    
    return value
