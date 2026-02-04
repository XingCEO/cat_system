"""
Validators - 輸入資料驗證工具
"""
import re
from typing import Tuple, Optional
from datetime import datetime


def validate_date(date_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    驗證日期格式 YYYY-MM-DD
    
    Returns:
        (is_valid, error_message)
    """
    if date_str is None:
        return True, None
    
    if not isinstance(date_str, str):
        return False, "日期必須為字串格式"
    
    # Check format
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(pattern, date_str):
        return False, "日期格式錯誤，請使用 YYYY-MM-DD"
    
    # Validate actual date
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False, f"無效的日期: {date_str}"
    
    return True, None


def validate_symbol(symbol: str) -> Tuple[bool, Optional[str]]:
    """
    驗證股票代號格式
    
    Returns:
        (is_valid, error_message)
    """
    if not symbol:
        return False, "股票代號不能為空"
    
    if not isinstance(symbol, str):
        return False, "股票代號必須為字串"
    
    # Taiwan stock symbols: 4-6 digits, may have suffix
    pattern = r"^\d{4,6}[A-Z]?$"
    if not re.match(pattern, symbol.upper()):
        return False, f"無效的股票代號格式: {symbol}"
    
    return True, None


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    驗證日期範圍
    
    Returns:
        (is_valid, error_message)
    """
    if start_date:
        valid, error = validate_date(start_date)
        if not valid:
            return False, f"起始日期錯誤: {error}"
    
    if end_date:
        valid, error = validate_date(end_date)
        if not valid:
            return False, f"結束日期錯誤: {error}"
    
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt > end_dt:
            return False, "起始日期不能晚於結束日期"
    
    return True, None


def validate_pagination(
    page: int = 1,
    page_size: int = 50
) -> Tuple[bool, Optional[str]]:
    """
    驗證分頁參數
    
    Returns:
        (is_valid, error_message)
    """
    if page < 1:
        return False, "頁碼必須 >= 1"
    
    if page_size < 1 or page_size > 500:
        return False, "每頁數量必須在 1-500 之間"
    
    return True, None
