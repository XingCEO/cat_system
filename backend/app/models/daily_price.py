"""
DailyPrice Model — 日 K 線 + 技術指標
"""
from sqlalchemy import Column, String, Float, Integer, Date, DateTime, UniqueConstraint, Index
from datetime import datetime
from database import Base


class DailyPrice(Base):
    """日K線 + 技術指標"""
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, comment="交易日期")
    ticker_id = Column(String(10), nullable=False, index=True, comment="股票代號")

    # OHLCV
    open = Column(Float, nullable=True, comment="開盤價")
    high = Column(Float, nullable=True, comment="最高價")
    low = Column(Float, nullable=True, comment="最低價")
    close = Column(Float, nullable=True, comment="收盤價")
    volume = Column(Integer, nullable=True, comment="成交量 (股)")

    # 移動平均線
    ma5 = Column(Float, nullable=True, comment="5日均線")
    ma10 = Column(Float, nullable=True, comment="10日均線")
    ma20 = Column(Float, nullable=True, comment="20日均線")
    ma60 = Column(Float, nullable=True, comment="60日均線")

    # 技術指標
    rsi14 = Column(Float, nullable=True, comment="RSI(14)")

    # 基本面
    pe_ratio = Column(Float, nullable=True, comment="本益比")
    eps = Column(Float, nullable=True, comment="每股盈餘")

    # 漲跌
    change_percent = Column(Float, nullable=True, comment="漲跌幅 %")

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("date", "ticker_id", name="uq_date_ticker"),
        Index("idx_daily_prices_date", "date"),
        Index("idx_daily_prices_ticker_date", "ticker_id", "date"),
    )

    def __repr__(self):
        return f"<DailyPrice {self.ticker_id} @ {self.date}>"
