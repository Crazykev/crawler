"""SQLAlchemy models for cache management."""

from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy import (
    String, Integer, DateTime, JSON, Index
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CacheEntry(Base):
    """Model for storing cache entries."""
    
    __tablename__ = "cache_entries"
    
    # Primary key (cache key)
    cache_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    
    # Cached data value
    data_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Data type for proper deserialization
    data_type: Mapped[str] = mapped_column(String(100), nullable=False, default="json")
    
    # Cache expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Cache statistics
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    # Indexes for cache management
    __table_args__ = (
        Index("idx_cache_entries_expires", "expires_at"),
        Index("idx_cache_entries_access_count", "access_count"),
        Index("idx_cache_entries_last_accessed", "last_accessed"),
    )
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def increment_access_count(self) -> None:
        """Increment access count and update last accessed time."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
    
    def __repr__(self) -> str:
        return (
            f"CacheEntry("
            f"cache_key={self.cache_key!r}, "
            f"data_type={self.data_type}, "
            f"access_count={self.access_count}"
            f")"
        )