"""
Cache Manager - In-memory caching with TTL
"""
from cachetools import TTLCache
from typing import Optional, Any, Callable
from functools import wraps
import asyncio
from datetime import datetime
from config import get_settings

settings = get_settings()


class CacheManager:
    """Simple in-memory cache manager with TTL support"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_caches()
        return cls._instance
    
    def _init_caches(self):
        """Initialize cache containers"""
        # Different caches for different data types
        self.daily_cache = TTLCache(maxsize=1000, ttl=settings.cache_daily_data)
        self.historical_cache = TTLCache(maxsize=500, ttl=settings.cache_historical_data)
        self.indicator_cache = TTLCache(maxsize=500, ttl=settings.cache_indicators)
        self.industry_cache = TTLCache(maxsize=100, ttl=settings.cache_industries)
        self.general_cache = TTLCache(maxsize=1000, ttl=300)
        self.realtime_cache = TTLCache(maxsize=200, ttl=10)  # 即時報價 10 秒
    
    def get(self, key: str, cache_type: str = "general") -> Optional[Any]:
        """Get value from cache"""
        cache = self._get_cache(cache_type)
        return cache.get(key)
    
    def set(self, key: str, value: Any, cache_type: str = "general"):
        """Set value in cache"""
        cache = self._get_cache(cache_type)
        cache[key] = value
    
    def delete(self, key: str, cache_type: str = "general"):
        """Delete value from cache"""
        cache = self._get_cache(cache_type)
        if key in cache:
            del cache[key]
    
    def clear(self, cache_type: str = None):
        """Clear cache(s)"""
        if cache_type:
            cache = self._get_cache(cache_type)
            cache.clear()
        else:
            self.daily_cache.clear()
            self.historical_cache.clear()
            self.indicator_cache.clear()
            self.industry_cache.clear()
            self.general_cache.clear()
            self.realtime_cache.clear()
    
    def _get_cache(self, cache_type: str) -> TTLCache:
        """Get the appropriate cache by type"""
        caches = {
            "daily": self.daily_cache,
            "historical": self.historical_cache,
            "indicator": self.indicator_cache,
            "industry": self.industry_cache,
            "general": self.general_cache,
            "realtime": self.realtime_cache
        }
        return caches.get(cache_type, self.general_cache)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "daily": {"size": len(self.daily_cache), "maxsize": self.daily_cache.maxsize},
            "historical": {"size": len(self.historical_cache), "maxsize": self.historical_cache.maxsize},
            "indicator": {"size": len(self.indicator_cache), "maxsize": self.indicator_cache.maxsize},
            "industry": {"size": len(self.industry_cache), "maxsize": self.industry_cache.maxsize},
            "general": {"size": len(self.general_cache), "maxsize": self.general_cache.maxsize},
            "realtime": {"size": len(self.realtime_cache), "maxsize": self.realtime_cache.maxsize},
        }


def cached(cache_type: str = "general", key_prefix: str = ""):
    """Decorator for caching async function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = CacheManager()
            
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args[1:])  # Skip self
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = cache.get(cache_key, cache_type)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, cache_type)
            
            return result
        return wrapper
    return decorator


# Global cache instance
cache_manager = CacheManager()
