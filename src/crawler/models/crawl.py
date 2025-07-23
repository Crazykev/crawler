"""Pydantic models for crawling operations."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from enum import Enum

from pydantic import BaseModel, Field, field_validator, HttpUrl, ConfigDict
from .scrape import ScrapeOptions, ExtractionStrategyConfig, OutputFormat, ScrapeResult


class CrawlStatus(str, Enum):
    """Status of crawling operations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class LinkClassification(str, Enum):
    """Classification of discovered links."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    SUBDOMAIN = "subdomain"
    EXCLUDED = "excluded"


class CrawlRules(BaseModel):
    """Rules and constraints for crawling operations."""
    
    # Depth and scope limits
    max_depth: int = Field(default=3, ge=0, le=10)
    max_pages: int = Field(default=100, ge=1, le=10000)
    max_duration: int = Field(default=3600, ge=60, le=86400, description="Max duration in seconds")
    
    # Rate limiting
    delay: float = Field(default=1.0, ge=0.0, le=60.0, description="Delay between requests in seconds")
    concurrent_requests: int = Field(default=5, ge=1, le=20)
    
    # Politeness
    respect_robots: bool = True
    obey_nofollow: bool = True
    
    # Domain restrictions
    allow_external_links: bool = False
    allow_subdomains: bool = True
    allowed_domains: Optional[List[str]] = None
    blocked_domains: Optional[List[str]] = None
    
    # URL filtering
    include_patterns: List[str] = Field(default_factory=list, description="Regex patterns for URLs to include")
    exclude_patterns: List[str] = Field(default_factory=list, description="Regex patterns for URLs to exclude")
    
    # Content filtering
    allowed_file_types: Optional[List[str]] = Field(default=None, description="Allowed file extensions")
    max_file_size: int = Field(default=10*1024*1024, ge=0, description="Max file size in bytes")
    
    # Advanced options
    follow_redirects: bool = True
    max_redirects: int = Field(default=5, ge=0, le=20)
    extract_robots_sitemap: bool = True
    
    model_config = ConfigDict(use_enum_values=True)


class CrawlSeed(BaseModel):
    """Starting point for a crawl operation."""
    
    url: HttpUrl
    priority: int = Field(default=0, ge=-10, le=10)
    depth: int = Field(default=0, ge=0)
    metadata: Optional[Dict[str, Any]] = None


class DiscoveredLink(BaseModel):
    """A link discovered during crawling."""
    
    url: HttpUrl
    source_url: HttpUrl
    text: Optional[str] = None
    classification: LinkClassification
    depth: int
    discovered_at: datetime
    priority: int = 0
    
    # Link attributes
    rel: Optional[str] = None
    title: Optional[str] = None
    
    # Processing status
    processed: bool = False
    processing_failed: bool = False
    error_message: Optional[str] = None


class CrawlQueue(BaseModel):
    """Queue of URLs to be processed."""
    
    pending: List[DiscoveredLink] = Field(default_factory=list)
    processing: List[DiscoveredLink] = Field(default_factory=list)
    completed: List[DiscoveredLink] = Field(default_factory=list)
    failed: List[DiscoveredLink] = Field(default_factory=list)
    
    def total_pending(self) -> int:
        return len(self.pending)
    
    def total_processing(self) -> int:
        return len(self.processing)
    
    def total_completed(self) -> int:
        return len(self.completed)
    
    def total_failed(self) -> int:
        return len(self.failed)


class CrawlStatistics(BaseModel):
    """Statistics for a crawling operation."""
    
    # Counts
    pages_discovered: int = 0
    pages_crawled: int = 0
    pages_successful: int = 0
    pages_failed: int = 0
    
    # Depth tracking
    current_depth: int = 0
    max_depth_reached: int = 0
    
    # Queue status
    urls_pending: int = 0
    urls_processing: int = 0
    
    # Performance metrics
    average_response_time: float = 0.0
    total_bytes_downloaded: int = 0
    requests_per_second: float = 0.0
    
    # Error tracking
    error_rate: float = 0.0
    common_errors: Dict[str, int] = Field(default_factory=dict)
    
    # Time tracking
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    elapsed_time: float = 0.0
    estimated_completion: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.pages_crawled == 0:
            return 0.0
        return (self.pages_successful / self.pages_crawled) * 100
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage based on discovered pages."""
        total = self.pages_discovered
        if total == 0:
            return 0.0
        return (self.pages_crawled / total) * 100


class CrawlRequest(BaseModel):
    """Request model for crawling operations."""
    
    start_urls: List[HttpUrl] = Field(..., min_length=1)
    crawl_rules: Optional[CrawlRules] = None
    scrape_options: Optional[ScrapeOptions] = None
    extraction_strategy: Optional[ExtractionStrategyConfig] = None
    output_format: OutputFormat = OutputFormat.MARKDOWN
    
    # Session and storage
    session_id: Optional[str] = None
    store_results: bool = True
    
    # Metadata
    crawl_name: Optional[str] = None
    crawl_description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class CrawlResponse(BaseModel):
    """Response model for crawl initiation."""
    
    crawl_id: str
    status: CrawlStatus
    message: Optional[str] = None
    start_urls: List[HttpUrl]
    estimated_pages: Optional[int] = None
    estimated_duration: Optional[int] = None


class CrawlProgress(BaseModel):
    """Progress information for an ongoing crawl."""
    
    crawl_id: str
    status: CrawlStatus
    statistics: CrawlStatistics
    
    # Current state
    current_url: Optional[HttpUrl] = None
    current_depth: int = 0
    
    # Queue information
    queue_summary: Dict[str, int] = Field(default_factory=dict)
    
    # Recent activity
    recent_successes: List[str] = Field(default_factory=list)
    recent_failures: List[Dict[str, str]] = Field(default_factory=list)
    
    # Error information
    error_message: Optional[str] = None
    last_error: Optional[str] = None
    
    # Timestamps
    started_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class CrawlResult(BaseModel):
    """Complete result of a crawling operation."""
    
    crawl_id: str
    status: CrawlStatus
    
    # Configuration used
    start_urls: List[HttpUrl]
    crawl_rules: CrawlRules
    
    # Results
    results: List[ScrapeResult] = Field(default_factory=list)
    discovered_links: List[DiscoveredLink] = Field(default_factory=list)
    
    # Statistics
    statistics: CrawlStatistics
    
    # Metadata
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration: Optional[float] = None
    
    # Error information
    error_message: Optional[str] = None
    partial_results: bool = False


class SitemapInfo(BaseModel):
    """Information extracted from robots.txt and sitemaps."""
    
    robots_url: Optional[HttpUrl] = None
    robots_content: Optional[str] = None
    
    sitemap_urls: List[HttpUrl] = Field(default_factory=list)
    sitemap_entries: List[Dict[str, Any]] = Field(default_factory=list)
    
    crawl_delay: Optional[float] = None
    user_agent_rules: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class CrawlConfiguration(BaseModel):
    """Complete configuration for a crawl operation."""
    
    # Basic settings
    name: Optional[str] = None
    description: Optional[str] = None
    
    # URLs and rules
    start_urls: List[HttpUrl]
    crawl_rules: CrawlRules
    
    # Processing options
    scrape_options: ScrapeOptions
    extraction_strategy: Optional[ExtractionStrategyConfig] = None
    output_format: OutputFormat = OutputFormat.MARKDOWN
    
    # Session and storage
    session_id: Optional[str] = None
    store_results: bool = True
    
    # Scheduling
    schedule: Optional[str] = None  # Cron expression
    
    # Callbacks and notifications
    webhook_url: Optional[HttpUrl] = None
    notification_emails: List[str] = Field(default_factory=list)
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None


class CrawlTemplate(BaseModel):
    """Template for common crawl configurations."""
    
    name: str
    description: Optional[str] = None
    
    # Default configuration
    default_rules: CrawlRules
    default_scrape_options: ScrapeOptions
    default_extraction_strategy: Optional[ExtractionStrategyConfig] = None
    
    # Template metadata
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    use_count: int = 0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)