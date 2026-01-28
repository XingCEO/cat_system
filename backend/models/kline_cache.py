"""
K-Line Cache Model - 儲存 K 線歷史資料與技術指標
支援 5 年資料快取，24 小時自動更新
"""
from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Index, Text
from datetime import datetime, timedelta
from database import Base


class KLineCache(Base):
    """K線資料快取 - 按日儲存"""
    __tablename__ = "kline_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # OHLCV 基本資料
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    
    # 移動平均線
    ma5 = Column(Float, nullable=True)
    ma10 = Column(Float, nullable=True)
    ma20 = Column(Float, nullable=True)
    ma60 = Column(Float, nullable=True)
    ma120 = Column(Float, nullable=True)
    
    # 成交量均線
    volume_ma5 = Column(Float, nullable=True)
    
    # MACD 指標
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    macd_hist = Column(Float, nullable=True)
    
    # KD 指標
    k = Column(Float, nullable=True)
    d = Column(Float, nullable=True)
    
    # RSI
    rsi = Column(Float, nullable=True)
    
    # 布林通道
    bb_upper = Column(Float, nullable=True)
    bb_middle = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    
    # 快取時間戳記
    cached_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 資料有效性標記
    is_valid = Column(Integer, default=1)  # 1=有效, 0=無效/缺失
    
    # 複合索引
    __table_args__ = (
        Index('idx_kline_symbol_date', 'symbol', 'date', unique=True),
        Index('idx_kline_cached_at', 'cached_at'),
    )
    
    def __repr__(self):
        return f"<KLineCache {self.symbol} @ {self.date}>"
    
    def is_stale(self, hours: int = 24) -> bool:
        """檢查快取是否過期"""
        if not self.cached_at:
            return True
        return datetime.utcnow() - self.cached_at > timedelta(hours=hours)
    
    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "ma5": self.ma5,
            "ma10": self.ma10,
            "ma20": self.ma20,
            "ma60": self.ma60,
            "ma120": self.ma120,
            "volume_ma5": self.volume_ma5,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "macd_hist": self.macd_hist,
            "k": self.k,
            "d": self.d,
            "rsi": self.rsi,
            "bb_upper": self.bb_upper,
            "bb_middle": self.bb_middle,
            "bb_lower": self.bb_lower,
        }


class KLineFetchProgress(Base):
    """K線資料抓取進度追蹤"""
    __tablename__ = "kline_fetch_progress"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    
    # 進度資訊
    total_months = Column(Integer, default=60)  # 總共需要抓取的月份數
    completed_months = Column(Integer, default=0)  # 已完成的月份數
    current_month = Column(String(7), nullable=True)  # 當前正在處理的月份 YYYY-MM
    
    # 狀態
    status = Column(String(20), default="pending")  # pending, in_progress, completed, error
    error_message = Column(Text, nullable=True)
    
    # 時間戳記
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_fetch_symbol', 'symbol', unique=True),
    )
    
    def __repr__(self):
        return f"<KLineFetchProgress {self.symbol}: {self.completed_months}/{self.total_months}>"
    
    @property
    def progress_percent(self) -> float:
        """取得進度百分比"""
        if self.total_months == 0:
            return 0.0
        return round(self.completed_months / self.total_months * 100, 1)
    
    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "symbol": self.symbol,
            "total_months": self.total_months,
            "completed_months": self.completed_months,
            "current_month": self.current_month,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
