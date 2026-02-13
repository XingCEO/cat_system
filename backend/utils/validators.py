"""
Validators - 輸入資料驗證工具
"""
import re
import calendar
from typing import Tuple, Optional
from datetime import datetime, timedelta


def _format_iso_date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _normalize_ymd(year: int, month: int, day: int) -> Optional[str]:
    if month < 1 or month > 12:
        return None
    if year < 1:
        return None

    last_day = calendar.monthrange(year, month)[1]
    clamped_day = min(max(day, 1), last_day)
    return _format_iso_date(year, month, clamped_day)


def normalize_date_input(date_str: Optional[str]) -> Optional[str]:
    """
    正規化日期輸入，支援:
    - YYYY-MM-DD
    - YYYY/MM/DD
    - YYYYMMDD
    - 民國年 (如 114/11/01)
    - 民國年緊湊格式 (如 1141101)
    - MM/DD (以今年補年)
    - MMDD (以今年補年)
    - 今天/昨天/前天 (today/yesterday)

    回傳標準格式 YYYY-MM-DD；若無法解析則回傳原字串（交由 validate_date 回報錯誤）
    """
    if date_str is None:
        return None
    if not isinstance(date_str, str):
        return date_str

    cleaned = date_str.strip()
    if not cleaned:
        return cleaned

    lowered = cleaned.lower()
    from utils.date_utils import get_taiwan_today

    today = get_taiwan_today()
    if lowered in {"今天", "今日", "today", "now"}:
        return today.strftime("%Y-%m-%d")
    if lowered in {"昨天", "昨日", "yesterday"}:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    if lowered in {"前天"}:
        return (today - timedelta(days=2)).strftime("%Y-%m-%d")

    cleaned = cleaned.replace("/", "-")

    ymd = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", cleaned)
    if ymd:
        normalized = _normalize_ymd(int(ymd.group(1)), int(ymd.group(2)), int(ymd.group(3)))
        return normalized or cleaned

    roc = re.match(r"^(\d{2,3})-(\d{1,2})-(\d{1,2})$", cleaned)
    if roc:
        normalized = _normalize_ymd(int(roc.group(1)) + 1911, int(roc.group(2)), int(roc.group(3)))
        return normalized or cleaned

    yyyymmdd = re.match(r"^(\d{4})(\d{2})(\d{2})$", cleaned)
    if yyyymmdd:
        normalized = _normalize_ymd(int(yyyymmdd.group(1)), int(yyyymmdd.group(2)), int(yyyymmdd.group(3)))
        return normalized or cleaned

    roc_compact = re.match(r"^(\d{3})(\d{2})(\d{2})$", cleaned)
    if roc_compact:
        normalized = _normalize_ymd(
            int(roc_compact.group(1)) + 1911,
            int(roc_compact.group(2)),
            int(roc_compact.group(3)),
        )
        return normalized or cleaned

    short = re.match(r"^(\d{1,2})-(\d{1,2})$", cleaned)
    if short:
        normalized = _normalize_ymd(today.year, int(short.group(1)), int(short.group(2)))
        return normalized or cleaned

    compact = re.match(r"^(\d{3,4})$", cleaned)
    if compact:
        text = compact.group(1)
        if len(text) == 3:
            month = int(text[:1])
            day = int(text[1:])
        else:
            month = int(text[:2])
            day = int(text[2:])
        normalized = _normalize_ymd(today.year, month, day)
        return normalized or cleaned

    return cleaned


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
    end_date: Optional[str],
    max_days: Optional[int] = None
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

        if max_days is not None and max_days > 0:
            span_days = (end_dt - start_dt).days + 1
            if span_days > max_days:
                return False, f"日期區間不可超過 {max_days} 天"
    
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


def validate_percentage_range(
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    驗證百分比範圍

    Returns:
        (is_valid, error_message)
    """
    if min_val is not None and (min_val < -100 or min_val > 100):
        return False, "百分比超出有效範圍 (-100% ~ 100%)"

    if max_val is not None and (max_val < -100 or max_val > 100):
        return False, "百分比超出有效範圍 (-100% ~ 100%)"

    if min_val is not None and max_val is not None and min_val > max_val:
        return False, "最小值不可大於最大值"

    return True, None


def validate_volume(volume: Optional[int]) -> Tuple[bool, Optional[str]]:
    """
    驗證成交量

    Returns:
        (is_valid, error_message)
    """
    if volume is None:
        return True, None

    if volume < 0:
        return False, "成交量不可為負數"

    return True, None


def validate_price(
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    驗證價格範圍

    Returns:
        (is_valid, error_message)
    """
    if min_price is not None and min_price <= 0:
        return False, "價格必須大於 0"

    if max_price is not None and max_price <= 0:
        return False, "價格必須大於 0"

    if min_price is not None and max_price is not None and min_price > max_price:
        return False, "最低價不可大於最高價"

    return True, None


def sanitize_string(s: str, max_length: int = 255) -> str:
    """
    清理字串：去除空白、限制長度

    Returns:
        sanitized string
    """
    if not s:
        return ""

    result = s.strip()
    if len(result) > max_length:
        result = result[:max_length]

    return result
