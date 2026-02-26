"""
Favorite Conditions Model
"""
from sqlalchemy import Column, String, Integer, DateTime, JSON
from datetime import datetime, timezone
from database import Base


class Favorite(Base):
    """Saved favorite filter conditions"""
    __tablename__ = "favorites"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Favorite metadata
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=True)  # e.g., "短線", "波段", "存股"
    description = Column(String(500), nullable=True)
    
    # Filter conditions (stored as JSON)
    conditions = Column(JSON, nullable=False)
    # Example:
    # {
    #     "change_min": 2.0,
    #     "change_max": 3.0,
    #     "volume_min": 500,
    #     "exclude_etf": true,
    #     "consecutive_up_days_min": 2,
    #     "price_min": 50,
    #     "price_max": 150
    # }
    
    # Usage tracking
    use_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<Favorite {self.id}: {self.name}>"
