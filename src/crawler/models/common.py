"""Common Pydantic models and types used across the crawler system."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class JobType(str, Enum):
    """Types of jobs that can be processed."""
    SCRAPE_PAGE = "scrape_page"
    CRAWL_SITE = "crawl_site"
    BATCH_SCRAPE = "batch_scrape"
    BATCH_CRAWL = "batch_crawl"
    CLEANUP = "cleanup"
    EXPORT = "export"


class JobStatus(str, Enum):
    """Status of job processing."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class Priority(int, Enum):
    """Job priority levels."""
    LOWEST = -10
    LOW = -5
    NORMAL = 0
    HIGH = 5
    HIGHEST = 10


class ErrorType(str, Enum):
    """Types of errors that can occur."""
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    PARSING_ERROR = "parsing_error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_ERROR = "permission_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    RESOURCE_ERROR = "resource_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN_ERROR = "unknown_error"


class BaseResponse(BaseModel):
    """Base response model."""
    
    success: bool
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    """Error response model."""
    
    success: bool = False
    error_type: ErrorType
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None


class SuccessResponse(BaseResponse):
    """Success response model."""
    
    success: bool = True
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    """Paginated response model."""
    
    items: List[Any]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=1000)
    pages: int
    has_next: bool
    has_prev: bool


class HealthCheck(BaseModel):
    """Health check response."""
    
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[str] = None
    
    # Component health
    components: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    # System metrics
    uptime: Optional[float] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None


class SystemInfo(BaseModel):
    """System information."""
    
    version: str
    build_date: Optional[str] = None
    git_commit: Optional[str] = None
    
    # Runtime info
    python_version: str
    platform: str
    architecture: str
    
    # Dependencies
    dependencies: Dict[str, str] = Field(default_factory=dict)


class MetricPoint(BaseModel):
    """Single metric data point."""
    
    name: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = Field(default_factory=dict)
    unit: Optional[str] = None


class MetricSummary(BaseModel):
    """Summary of metrics over a time period."""
    
    name: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    sum_value: float
    
    # Time range
    start_time: datetime
    end_time: datetime
    
    # Additional stats
    percentiles: Dict[str, float] = Field(default_factory=dict)


class FileInfo(BaseModel):
    """Information about generated files."""
    
    filename: str
    filepath: str
    size: int
    mime_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    checksum: Optional[str] = None


class URLInfo(BaseModel):
    """Information about a URL."""
    
    url: HttpUrl
    domain: str
    path: str
    query_params: Dict[str, str] = Field(default_factory=dict)
    fragment: Optional[str] = None
    
    # Metadata
    title: Optional[str] = None
    description: Optional[str] = None
    canonical_url: Optional[HttpUrl] = None
    
    # Technical info
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    last_modified: Optional[datetime] = None


class RateLimitInfo(BaseModel):
    """Rate limiting information."""
    
    limit: int
    remaining: int
    reset_at: datetime
    window_seconds: int


class ValidationError(BaseModel):
    """Validation error information."""
    
    field: str
    message: str
    code: Optional[str] = None
    value: Optional[Any] = None


class BatchOperation(BaseModel):
    """Batch operation tracking."""
    
    batch_id: str
    operation_type: str
    total_items: int
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Progress tracking
    current_item: Optional[str] = None
    progress_percentage: float = 0.0
    estimated_completion: Optional[datetime] = None
    
    # Results
    errors: List[ErrorResponse] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    """Request for data export."""
    
    export_type: str  # "results", "sessions", "logs", "metrics"
    format: str = "json"  # "json", "csv", "xlsx", "xml"
    
    # Filters
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # Options
    include_metadata: bool = True
    compress: bool = False


class ExportResult(BaseModel):
    """Result of data export."""
    
    export_id: str
    status: str  # "processing", "completed", "failed"
    
    # File info
    file_info: Optional[FileInfo] = None
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    # Statistics
    total_records: int = 0
    file_size: int = 0
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = None


class SearchRequest(BaseModel):
    """Request for searching data."""
    
    query: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # Pagination
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=1000)
    
    # Sorting
    sort_by: Optional[str] = None
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    
    # Options
    include_highlights: bool = False
    facets: List[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Result of search operation."""
    
    query: str
    total_hits: int
    search_time: float
    
    # Results
    hits: List[Dict[str, Any]]
    
    # Facets
    facets: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    
    # Suggestions
    suggestions: List[str] = Field(default_factory=list)


class NotificationConfig(BaseModel):
    """Configuration for notifications."""
    
    enabled: bool = True
    channels: List[str] = Field(default_factory=list)  # "email", "webhook", "slack"
    
    # Event filters
    events: List[str] = Field(default_factory=list)
    min_severity: str = "warning"
    
    # Delivery settings
    batch_notifications: bool = False
    batch_interval: int = Field(default=300, ge=60)


class WebhookConfig(BaseModel):
    """Webhook configuration."""
    
    url: HttpUrl
    method: str = Field(default="POST", pattern="^(GET|POST|PUT|PATCH)$")
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=1, le=300)
    retry_attempts: int = Field(default=1, ge=0, le=10)
    
    # Security
    secret: Optional[str] = None
    verify_ssl: bool = True


class ScheduleConfig(BaseModel):
    """Schedule configuration for automated tasks."""
    
    enabled: bool = True
    cron_expression: str
    timezone: str = "UTC"
    
    # Execution limits
    max_instances: int = Field(default=1, ge=1)
    timeout: int = Field(default=3600, ge=60)
    
    # Error handling
    on_failure: str = Field(default="log", pattern="^(log|retry|stop)$")
    max_failures: int = Field(default=3, ge=0)