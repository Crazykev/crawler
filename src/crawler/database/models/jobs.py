"""SQLAlchemy models for job queue management."""

from typing import Any, Dict, Optional
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    String, Integer, DateTime, JSON, Index, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobStatus(str, Enum):
    """Enumeration of job statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Enumeration of job types."""
    SCRAPE_SINGLE = "scrape_single"
    SCRAPE_BATCH = "scrape_batch"
    CRAWL_SITE = "crawl_site"
    SESSION_OPERATION = "session_operation"


class JobPriority(int, Enum):
    """Enumeration of job priorities."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class JobQueue(Base):
    """Model for storing job queue entries."""
    
    __tablename__ = "job_queue"
    
    # Primary key (job ID)
    job_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    
    # Job classification
    job_type: Mapped[JobType] = mapped_column(
        SQLEnum(JobType),
        nullable=False,
        index=True
    )
    
    # Job status
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Job priority (higher number = higher priority)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    
    # Timing information
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Job data and results
    job_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Error information
    error_message: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    
    # Retry information
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    
    # Indexes for job management
    __table_args__ = (
        Index("idx_job_queue_status_priority", "status", "priority"),
        Index("idx_job_queue_type", "job_type"),
        Index("idx_job_queue_created", "created_at"),
        Index("idx_job_queue_started", "started_at"),
        Index("idx_job_queue_completed", "completed_at"),
    )
    
    def can_retry(self) -> bool:
        """Check if the job can be retried."""
        return (
            self.status == JobStatus.FAILED and 
            self.retry_count < self.max_retries
        )
    
    def mark_started(self) -> None:
        """Mark the job as started."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def mark_completed(self, result_data: Optional[Dict[str, Any]] = None) -> None:
        """Mark the job as completed."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if result_data:
            self.result_data = result_data
    
    def mark_failed(self, error_message: str) -> None:
        """Mark the job as failed."""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.retry_count += 1
    
    def mark_cancelled(self) -> None:
        """Mark the job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def __repr__(self) -> str:
        return (
            f"JobQueue("
            f"job_id={self.job_id!r}, "
            f"job_type={self.job_type.value}, "
            f"status={self.status.value}, "
            f"priority={self.priority}"
            f")"
        )