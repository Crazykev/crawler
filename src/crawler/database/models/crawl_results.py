"""SQLAlchemy models for crawl results and related data."""

from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy import (
    String, Integer, Boolean, Text, JSON, Index, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class CrawlResult(Base):
    """Model for storing crawl/scrape results."""
    
    __tablename__ = "crawl_results"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Job and URL information
    job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    
    # Page metadata
    title: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Content in different formats
    content_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True) 
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Structured extracted data
    extracted_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Metadata (load time, size, etc.)
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Error information if scraping failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    links = relationship("CrawlLink", back_populates="crawl_result", cascade="all, delete-orphan")
    media = relationship("CrawlMedia", back_populates="crawl_result", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_crawl_results_job_url", "job_id", "url"),
        Index("idx_crawl_results_success", "success"),
        Index("idx_crawl_results_status", "status_code"),
        Index("idx_crawl_results_created", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"CrawlResult(id={self.id}, url={self.url!r}, success={self.success})"


class CrawlLink(Base):
    """Model for storing links found during crawling."""
    
    __tablename__ = "crawl_links"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to crawl result
    crawl_result_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("crawl_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Link information
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    text: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    link_type: Mapped[str] = mapped_column(String(50), nullable=False, default="external")
    
    # Additional metadata
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationship
    crawl_result = relationship("CrawlResult", back_populates="links")
    
    # Indexes
    __table_args__ = (
        Index("idx_crawl_links_url", "url"),
        Index("idx_crawl_links_type", "link_type"),
    )
    
    def __repr__(self) -> str:
        return f"CrawlLink(id={self.id}, url={self.url!r}, type={self.link_type})"


class CrawlMedia(Base):
    """Model for storing media (images, videos, etc.) found during crawling."""
    
    __tablename__ = "crawl_media"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to crawl result
    crawl_result_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("crawl_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Media information
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    alt_text: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    
    # Dimensions and file info
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Additional metadata
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationship
    crawl_result = relationship("CrawlResult", back_populates="media")
    
    # Indexes
    __table_args__ = (
        Index("idx_crawl_media_url", "url"),
        Index("idx_crawl_media_type", "media_type"),
    )
    
    def __repr__(self) -> str:
        return f"CrawlMedia(id={self.id}, url={self.url!r}, type={self.media_type})"