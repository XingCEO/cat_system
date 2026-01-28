"""
Stock and DailyData Models
"""
from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Index, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, date
from database import Base


class Stock(Base):
    """Stock basic information"""
    __tablename__ = "stocks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    industry = Column(String(50), nullable=True)
    is_etf = Column(Boolean, default=False)
    listed_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    daily_data = relationship("DailyData", back_populates="stock", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Stock {self.symbol} - {self.name}>"


class DailyData(Base):
    """Daily trading data"""
    __tablename__ = "daily_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    
    # Price data
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    prev_close = Column(Float, nullable=True)
    
    # Volume (in shares, will be converted to lots/張 in display)
    volume = Column(Integer, nullable=True)
    
    # Calculated fields (cached for performance)
    change_percent = Column(Float, nullable=True)  # 漲幅 %
    amplitude = Column(Float, nullable=True)  # 振幅 %
    volume_ratio = Column(Float, nullable=True)  # 量比
    
    # Streak data
    consecutive_up_days = Column(Integer, default=0)  # 連續上漲天數
    
    # 52-week position
    high_52w = Column(Float, nullable=True)
    low_52w = Column(Float, nullable=True)
    distance_from_high = Column(Float, nullable=True)  # 距離52週高點 %
    distance_from_low = Column(Float, nullable=True)  # 距離52週低點 %
    
    # Average change
    avg_change_5d = Column(Float, nullable=True)  # 近5日平均漲幅 %
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    stock = relationship("Stock", back_populates="daily_data")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_symbol_date', 'symbol', 'trade_date'),
        Index('idx_date_change', 'trade_date', 'change_percent'),
    )
    
    def __repr__(self):
        return f"<DailyData {self.symbol} @ {self.trade_date}>"
