"""SQLAlchemy models for browser session management."""

from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy import (
    String, Integer, Boolean, DateTime, JSON, Index
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BrowserSession(Base):
    """Model for storing browser session information."""
    
    __tablename__ = "browser_sessions"
    
    # Primary key (session ID)
    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    
    # Session configuration
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Session state data
    state_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Session statistics
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Timestamps
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_browser_sessions_active", "is_active"),
        Index("idx_browser_sessions_expires", "expires_at"),
        Index("idx_browser_sessions_last_accessed", "last_accessed"),
    )
    
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def increment_page_count(self) -> None:
        """Increment the page count and update last accessed time."""
        self.page_count += 1
        self.last_accessed = datetime.utcnow()
    
    def __repr__(self) -> str:
        return (
            f"BrowserSession("
            f"session_id={self.session_id!r}, "
            f"is_active={self.is_active}, "
            f"page_count={self.page_count}"
            f")"
        )