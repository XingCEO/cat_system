"""
Ticker Model — 股票基本資料
"""
from sqlalchemy import Column, String, DateTime
from datetime import datetime
from database import Base


class Ticker(Base):
    """股票基本資料"""
    __tablename__ = "tickers"

    ticker_id = Column(String(10), primary_key=True, comment="股票代號 (如 2330)")
    name = Column(String(50), nullable=False, comment="股票名稱 (如 台積電)")
    market_type = Column(String(10), nullable=True, comment="TSE (上市) / OTC (上櫃)")
    industry = Column(String(50), nullable=True, comment="產業分類")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Ticker {self.ticker_id} - {self.name}>"
