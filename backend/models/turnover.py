"""
Turnover Models - Database models for turnover rate analysis
"""
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class TurnoverRanking(Base):
    """周轉率排名記錄"""
    __tablename__ = "turnover_rankings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(50))
    industry: Mapped[Optional[str]] = mapped_column(String(50))
    
    # 排名與周轉率
    turnover_rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 周轉率排名 1-50
    turnover_rate: Mapped[float] = mapped_column(Float, nullable=False)  # 周轉率 %
    
    # 價格資料
    close_price: Mapped[Optional[float]] = mapped_column(Float)
    prev_close: Mapped[Optional[float]] = mapped_column(Float)
    change_percent: Mapped[Optional[float]] = mapped_column(Float)  # 漲幅 %
    amplitude: Mapped[Optional[float]] = mapped_column(Float)  # 振幅 %
    
    # 成交資料
    volume: Mapped[Optional[int]] = mapped_column(Integer)  # 成交量(張)
    float_shares: Mapped[Optional[float]] = mapped_column(Float)  # 流通股數(萬股)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float)  # 量比
    
    # 漲停相關
    is_limit_up: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否漲停
    limit_up_type: Mapped[Optional[str]] = mapped_column(String(20))  # 漲停類型: 一字板/秒板/盤中/尾盤
    seal_volume: Mapped[Optional[int]] = mapped_column(Integer)  # 封單量(張)
    seal_amount: Mapped[Optional[float]] = mapped_column(Float)  # 封單金額(萬元)
    open_count: Mapped[Optional[int]] = mapped_column(Integer)  # 開板次數
    first_limit_time: Mapped[Optional[str]] = mapped_column(String(10))  # 首次漲停時間
    
    # 其他指標
    consecutive_up_days: Mapped[Optional[int]] = mapped_column(Integer)  # 連續上漲天數
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('ix_turnover_date_rank', 'date', 'turnover_rank'),
        Index('ix_turnover_date_symbol', 'date', 'symbol'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": str(self.date),
            "symbol": self.symbol,
            "name": self.name,
            "industry": self.industry,
            "turnover_rank": self.turnover_rank,
            "turnover_rate": self.turnover_rate,
            "close_price": self.close_price,
            "prev_close": self.prev_close,
            "change_percent": self.change_percent,
            "amplitude": self.amplitude,
            "volume": self.volume,
            "float_shares": self.float_shares,
            "volume_ratio": self.volume_ratio,
            "is_limit_up": self.is_limit_up,
            "limit_up_type": self.limit_up_type,
            "seal_volume": self.seal_volume,
            "seal_amount": self.seal_amount,
            "open_count": self.open_count,
            "first_limit_time": self.first_limit_time,
            "consecutive_up_days": self.consecutive_up_days,
        }


class FloatShares(Base):
    """流通股數資料"""
    __tablename__ = "float_shares"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(50))
    
    # 股本資料 (單位: 萬股)
    total_shares: Mapped[Optional[float]] = mapped_column(Float)  # 總股數
    float_shares: Mapped[Optional[float]] = mapped_column(Float)  # 流通股數
    
    # 更新時間
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            "symbol": self.symbol,
            "name": self.name,
            "total_shares": self.total_shares,
            "float_shares": self.float_shares,
            "updated_at": str(self.updated_at),
        }


class TurnoverTrack(Base):
    """高周轉漲停股追蹤任務"""
    __tablename__ = "turnover_tracks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    trigger_date: Mapped[date] = mapped_column(Date, nullable=False)  # 觸發日期
    turnover_rank: Mapped[int] = mapped_column(Integer)  # 觸發時的周轉率排名
    trigger_price: Mapped[float] = mapped_column(Float)  # 觸發價格
    
    # 追蹤結果
    day1_change: Mapped[Optional[float]] = mapped_column(Float)  # 隔日漲跌幅
    day1_limit_up: Mapped[Optional[bool]] = mapped_column(Boolean)  # 隔日是否繼續漲停
    day3_change: Mapped[Optional[float]] = mapped_column(Float)  # 3日後漲跌幅
    day5_change: Mapped[Optional[float]] = mapped_column(Float)  # 5日後漲跌幅
    day7_change: Mapped[Optional[float]] = mapped_column(Float)  # 7日後漲跌幅
    
    # 狀態
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "trigger_date": str(self.trigger_date),
            "turnover_rank": self.turnover_rank,
            "trigger_price": self.trigger_price,
            "day1_change": self.day1_change,
            "day1_limit_up": self.day1_limit_up,
            "day3_change": self.day3_change,
            "day5_change": self.day5_change,
            "day7_change": self.day7_change,
            "is_complete": self.is_complete,
        }
