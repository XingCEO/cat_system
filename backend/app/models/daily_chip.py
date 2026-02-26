"""
DailyChip Model — 每日籌碼資料
"""
from sqlalchemy import Column, String, Integer, Date, DateTime, UniqueConstraint, Index
from datetime import datetime, timezone
from database import Base


class DailyChip(Base):
    """每日籌碼資料"""
    __tablename__ = "daily_chips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, comment="交易日期")
    ticker_id = Column(String(10), nullable=False, index=True, comment="股票代號")

    # 法人買賣超
    foreign_buy = Column(Integer, nullable=True, comment="外資買賣超 (股)")
    trust_buy = Column(Integer, nullable=True, comment="投信買賣超 (股)")

    # 融資
    margin_balance = Column(Integer, nullable=True, comment="融資餘額 (張)")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("date", "ticker_id", name="uq_chip_date_ticker"),
        Index("idx_daily_chips_ticker_date", "ticker_id", "date"),
    )

    def __repr__(self):
        return f"<DailyChip {self.ticker_id} @ {self.date}>"
