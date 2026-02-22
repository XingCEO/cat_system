"""
UserStrategy Model — 使用者儲存的篩選策略
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, JSON
from datetime import datetime
from database import Base


class UserStrategy(Base):
    """使用者篩選策略"""
    __tablename__ = "user_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="策略名稱")
    rules_json = Column(JSON, nullable=False, comment="篩選條件 JSON")
    alert_enabled = Column(Boolean, default=False, comment="是否開啟推播")
    line_notify_token = Column(Text, nullable=True, comment="Line Notify Token")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserStrategy {self.id} - {self.name}>"
