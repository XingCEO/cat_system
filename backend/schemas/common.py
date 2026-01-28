"""
Common Schemas
"""
from pydantic import BaseModel
from typing import Optional, Generic, TypeVar, List, Any
from datetime import datetime

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = 1
    page_size: int = 50
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int):
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size
        )


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper"""
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
    
    @classmethod
    def ok(cls, data: T = None, message: str = None):
        return cls(success=True, data=data, message=message)
    
    @classmethod
    def fail(cls, error: str):
        return cls(success=False, error=error)


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
