"""
Backtest Result Model
"""
from sqlalchemy import Column, String, Integer, DateTime, JSON, Float, Text
from datetime import datetime
from database import Base


class BacktestResult(Base):
    """Stored backtest results"""
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Backtest parameters
    filter_conditions = Column(JSON, nullable=False)
    start_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=False)
    lookback_days = Column(Integer, default=30)
    
    # Statistics
    total_signals = Column(Integer, default=0)  # 符合條件的信號總數
    unique_stocks = Column(Integer, default=0)  # 不重複股票數
    
    # Performance metrics
    win_rate = Column(Float, nullable=True)  # 勝率 (隔日上漲機率)
    avg_return_1d = Column(Float, nullable=True)  # 1日平均報酬
    avg_return_3d = Column(Float, nullable=True)  # 3日平均報酬
    avg_return_5d = Column(Float, nullable=True)  # 5日平均報酬
    avg_return_10d = Column(Float, nullable=True)  # 10日平均報酬
    
    max_gain = Column(Float, nullable=True)  # 最大漲幅
    max_loss = Column(Float, nullable=True)  # 最大跌幅
    
    expected_value = Column(Float, nullable=True)  # 期望值
    
    # Detailed results (JSON array of individual stock performances)
    detailed_results = Column(Text, nullable=True)  # JSON string for large data
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<BacktestResult {self.id} ({self.start_date} ~ {self.end_date})>"
