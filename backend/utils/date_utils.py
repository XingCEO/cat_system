"""
Date Utilities - Trading day utilities for Taiwan Stock Exchange

所有日期計算固定使用台灣時區 (UTC+8)，避免部署在 UTC 伺服器時日期不正確。
"""
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional
import asyncio

# 台灣時區 (UTC+8) — 固定偏移，不受伺服器 TZ 設定影響
TW_TZ = timezone(timedelta(hours=8))


def taiwan_today() -> date:
    """取得台灣時區的今天日期（不受伺服器 TZ 影響）"""
    return datetime.now(TW_TZ).date()


def taiwan_now() -> datetime:
    """取得台灣時區的當前時間"""
    return datetime.now(TW_TZ)


# Taiwan holidays (approximate - should be updated yearly)
TW_HOLIDAYS_2024 = [
    "2024-01-01",  # New Year
    "2024-02-08", "2024-02-09", "2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13", "2024-02-14",  # CNY
    "2024-02-28",  # Peace Memorial Day
    "2024-04-04", "2024-04-05",  # Tomb Sweeping Day
    "2024-05-01",  # Labor Day
    "2024-06-10",  # Dragon Boat Festival
    "2024-09-17",  # Mid-Autumn Festival
    "2024-10-10",  # National Day
]

TW_HOLIDAYS_2025 = [
    "2025-01-01",  # New Year
    "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31",  # CNY 2025 (Mon-Fri)
    "2025-02-28",  # Peace Memorial Day
    "2025-04-03", "2025-04-04",  # Tomb Sweeping Day  
    "2025-05-01",  # Labor Day
    "2025-05-30",  # Dragon Boat Festival (May 31 is Saturday, observed Friday)
    "2025-10-06",  # Mid-Autumn Festival
    "2025-10-10",  # National Day
]

TW_HOLIDAYS_2026 = [
    "2026-01-01",  # New Year
    "2026-01-02",  # New Year (observed)
    "2026-02-14", "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",  # CNY 2026
    "2026-02-27",  # Peace Memorial Day (Feb 28 is Saturday, observed Friday)
    "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06",  # Tomb Sweeping Day
    "2026-05-01",  # Labor Day
    "2026-06-19",  # Dragon Boat Festival
    "2026-09-25",  # Mid-Autumn Festival
    "2026-10-09", "2026-10-10",  # National Day (Oct 10 is Saturday, observed Friday)
]

TW_HOLIDAYS = set(TW_HOLIDAYS_2024 + TW_HOLIDAYS_2025 + TW_HOLIDAYS_2026)


def is_weekend(check_date: date) -> bool:
    """Check if date is weekend (Saturday=5, Sunday=6)"""
    return check_date.weekday() >= 5


def is_holiday(check_date: date) -> bool:
    """Check if date is a Taiwan holiday"""
    return check_date.strftime("%Y-%m-%d") in TW_HOLIDAYS


def is_trading_day(check_date: date) -> bool:
    """
    Check if a date is a trading day
    (Not weekend and not holiday)
    """
    if isinstance(check_date, str):
        check_date = datetime.strptime(check_date, "%Y-%m-%d").date()
    return not is_weekend(check_date) and not is_holiday(check_date)


def get_previous_trading_day(from_date: date = None) -> date:
    """Get the most recent trading day before or on the given date (台灣時區)"""
    if from_date is None:
        from_date = taiwan_today()
    
    if isinstance(from_date, str):
        from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
    
    check_date = from_date
    max_checks = 10
    
    for _ in range(max_checks):
        if is_trading_day(check_date):
            return check_date
        check_date -= timedelta(days=1)
    
    return from_date


def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """Get list of trading days between two dates"""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    trading_days = []
    current = start_date
    
    while current <= end_date:
        if is_trading_day(current):
            trading_days.append(current)
        current += timedelta(days=1)
    
    return trading_days


def get_n_trading_days_ago(n: int, from_date: date = None) -> date:
    """Get the date that is N trading days ago (台灣時區)"""
    if from_date is None:
        from_date = taiwan_today()
    
    count = 0
    current = from_date
    
    while count < n:
        current -= timedelta(days=1)
        if is_trading_day(current):
            count += 1
    
    return current


def format_date(d: date) -> str:
    """Format date to YYYY-MM-DD string"""
    if isinstance(d, str):
        return d
    return d.strftime("%Y-%m-%d")


def parse_date(date_str: str) -> Optional[date]:
    """Parse date string to date object"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def get_date_range_description(start_date: str, end_date: str) -> str:
    """Generate human-readable date range description"""
    start = parse_date(start_date)
    end = parse_date(end_date)
    
    if not start or not end:
        return ""
    
    days = (end - start).days
    trading_days = len(get_trading_days(start, end))
    
    return f"{start_date} ~ {end_date} ({days}天, {trading_days}個交易日)"


def get_latest_trading_day() -> str:
    """Get the most recent trading day as YYYY-MM-DD string"""
    return format_date(get_previous_trading_day())


def get_past_trading_days(n: int) -> List[str]:
    """
    Get list of past N trading days (most recent first)
    
    Args:
        n: Number of trading days to retrieve
        
    Returns:
        List of date strings in YYYY-MM-DD format, ordered from most recent to oldest
    """
    result = []
    current = taiwan_today()
    
    while len(result) < n:
        if is_trading_day(current):
            result.append(format_date(current))
        current -= timedelta(days=1)
    
    return result
