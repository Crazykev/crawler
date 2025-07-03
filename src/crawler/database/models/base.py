"""Base SQLAlchemy model with common functionality."""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    
    # Common columns that most tables should have
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when the record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Timestamp when the record was last updated"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model instance from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self) -> str:
        """String representation of the model."""
        class_name = self.__class__.__name__
        attrs = []
        
        # Show primary key if available
        if hasattr(self, 'id'):
            attrs.append(f"id={getattr(self, 'id')}")
        
        # Show other identifying attributes
        for attr in ['url', 'session_id', 'job_id', 'cache_key']:
            if hasattr(self, attr):
                value = getattr(self, attr)
                if value:
                    attrs.append(f"{attr}={value!r}")
                break
        
        attrs_str = ', '.join(attrs)
        return f"{class_name}({attrs_str})"