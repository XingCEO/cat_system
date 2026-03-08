"""
DailyPrice Model — 日 K 線 + 技術指標 + 延伸指標
"""
from sqlalchemy import Column, String, Float, Integer, Boolean, Date, DateTime, UniqueConstraint, Index
from datetime import datetime, timezone
from database import Base


class DailyPrice(Base):
    """日K線 + 技術指標 + 延伸指標"""
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

    # ===== 延伸指標 (選股條件所需) =====

    # 成交值 = close * volume
    turnover = Column(Float, nullable=True, comment="成交值 (元)")

    # 量能均值
    avg_volume_20 = Column(Float, nullable=True, comment="20日平均成交量")
    avg_turnover_20 = Column(Float, nullable=True, comment="20日平均成交值 (元)")

    # 下引價 = low - min(open, close)  (影線長度，非負)
    lower_shadow = Column(Float, nullable=True, comment="下引價 (低點距實體下緣)")

    # Ref(Lowest(下引價, 20), 1) — 前一日為基準的近20日下引價最低值
    lowest_lower_shadow_20 = Column(Float, nullable=True, comment="近20日下引價最低值(前日基準)")

    # 週線移動平均 (基於週收盤價)
    wma10 = Column(Float, nullable=True, comment="10週均線")
    wma20 = Column(Float, nullable=True, comment="20週均線")
    wma60 = Column(Float, nullable=True, comment="60週均線")

    # 大盤條件是否滿足 (當日 TAIEX 是否符合多頭排列 + 週線條件)
    market_ok = Column(Boolean, nullable=True, comment="大盤條件滿足 (多頭排列)")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("date", "ticker_id", name="uq_date_ticker"),
        Index("idx_daily_prices_date", "date"),
        Index("idx_daily_prices_ticker_date", "ticker_id", "date"),
    )

    def __repr__(self):
        return f"<DailyPrice {self.ticker_id} @ {self.date}>"
