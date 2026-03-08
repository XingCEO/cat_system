"""
MarketIndex Model — 大盤 (TAIEX) 每日指標
用於判斷大盤多頭排列條件
"""
from sqlalchemy import Column, Float, Boolean, Date, DateTime, Index
from datetime import datetime, timezone
from database import Base


class MarketIndex(Base):
    """TAIEX (加權指數) 每日資料與多頭條件"""
    __tablename__ = "market_index"

    date = Column(Date, primary_key=True, comment="交易日期")

    # 日線
    close = Column(Float, nullable=True, comment="收盤指數")
    ma20 = Column(Float, nullable=True, comment="日MA20")
    ma60 = Column(Float, nullable=True, comment="日MA60")

    # 週線 (最新週)
    weekly_close = Column(Float, nullable=True, comment="週收盤 (當週最後交易日收盤)")
    wma20 = Column(Float, nullable=True, comment="週MA20")

    # 多頭條件旗標:
    # 大盤收盤 >= 大盤MA20
    # AND 大盤MA20 >= 大盤MA60
    # AND 大盤週收盤 >= 大盤週MA20
    ok = Column(Boolean, nullable=True, default=False, comment="大盤多頭條件全部滿足")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_market_index_date", "date"),
    )

    def __repr__(self):
        return f"<MarketIndex {self.date} ok={self.ok}>"
