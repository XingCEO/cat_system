"""
Watchlist Models
"""
from sqlalchemy import Column, String, Integer, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Watchlist(Base):
    """User's watchlist"""
    __tablename__ = "watchlists"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, default="我的監控清單")
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Watchlist {self.id}: {self.name}>"


class WatchlistItem(Base):
    """Individual item in watchlist with alert conditions"""
    __tablename__ = "watchlist_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(100), nullable=True)
    
    # Alert conditions (JSON for flexibility)
    conditions = Column(JSON, nullable=True)
    # Example conditions:
    # {
    #     "change_percent_min": 2.0,
    #     "change_percent_max": 3.0,
    #     "volume_min": 500,
    #     "price_min": None,
    #     "price_max": 100
    # }
    
    # Alert status
    is_active = Column(Boolean, default=True)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    
    # Notes
    notes = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    watchlist = relationship("Watchlist", back_populates="items")
    
    def __repr__(self):
        return f"<WatchlistItem {self.symbol}>"
