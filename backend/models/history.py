"""
Query History Model
"""
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from datetime import datetime, timezone
from database import Base


class QueryHistory(Base):
    """History of user queries"""
    __tablename__ = "query_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Query parameters (stored as JSON)
    query_params = Column(JSON, nullable=False)
    # Example:
    # {
    #     "date": "2024-01-15",
    #     "change_min": 2.0,
    #     "change_max": 3.0,
    #     "volume_min": 500,
    #     "exclude_etf": true,
    #     "industries": ["電子", "半導體"]
    # }
    
    # Results summary
    result_count = Column(Integer, default=0)
    
    # Optional: store result symbols for quick reference
    result_symbols = Column(Text, nullable=True)  # Comma-separated
    
    # Query type
    query_type = Column(String(50), default="filter")  # filter, batch_compare, backtest
    
    # Timestamps
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def __repr__(self):
        return f"<QueryHistory {self.id} @ {self.executed_at}>"
