# Core Components Design

## Overview

This document details the design of the core components that form the foundation of the Crawler system. These components provide the essential services and abstractions needed to support all three interface layers while maintaining clean separation of concerns.

## Groundtruth References

This design is based on the following groundtruth specifications:
- **Crawl4AI Context**: `groundtruth/crawl4ai_context.md` (Generated: 2025-06-16T09:14:43.423Z, Version: 0.6.3)
- **Firecrawl API Specification**: `groundtruth/firecrawl-openapi.json` (OpenAPI 3.0, Version: v1)

*Note: When groundtruth files are updated, this design and implementation must be reviewed and adjusted accordingly.*

## Component Architecture

### Component Hierarchy

```
┌──────────────────────────────────────────────────────────────┐
│                     Service Layer                           │
├──────────────────┬──────────────────┬─────────────────────────┤
│   ScrapeService  │   CrawlService   │   SessionService        │
│                  │                  │                         │
│ • Single page    │ • Multi-page     │ • Browser sessions      │
│ • Batch ops      │ • Link discovery │ • State management      │
│ • Format conv    │ • Site crawling  │ • Resource cleanup      │
└──────────────────┴──────────────────┴─────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                     Core Layer                              │
├──────────────────┬──────────────────┬─────────────────────────┤
│   CrawlEngine    │   JobManager     │   StorageManager        │
│                  │                  │                         │
│ • Crawl4ai wrap  │ • Job queue      │ • Result storage        │
│ • Config mgmt    │ • Status track   │ • Cache management      │
│ • Strategy exec  │ • Error handling │ • Session persistence   │
└──────────────────┴──────────────────┴─────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                   Foundation Layer                          │
├──────────────────┬──────────────────┬─────────────────────────┤
│   ConfigManager  │   ErrorHandler   │   MetricsCollector      │
│                  │                  │                         │
│ • Config loading │ • Error types    │ • Performance metrics   │
│ • Validation     │ • Retry logic    │ • Business metrics      │
│ • Env resolution │ • Error reporting│ • System metrics        │
└──────────────────┴──────────────────┴─────────────────────────┘
```

## Service Layer Components

### 1. ScrapeService

#### Purpose
Handles single-page scraping operations with support for various extraction strategies and output formats.

#### Key Responsibilities
- Execute single-page scraping operations
- Handle batch scraping of multiple independent URLs
- Apply content extraction strategies
- Format conversion and output processing
- Input validation and sanitization

#### Interface Design

```python
class ScrapeService:
    """Service for handling single-page scraping operations."""
    
    async def scrape_single(
        self, 
        request: ScrapeRequest, 
        context: Optional[RequestContext] = None
    ) -> ScrapeResult:
        """Scrape a single URL with specified configuration."""
        pass
    
    async def scrape_batch(
        self, 
        request: BatchScrapeRequest, 
        context: Optional[RequestContext] = None
    ) -> BatchScrapeResult:
        """Scrape multiple URLs in parallel."""
        pass
    
    async def extract_content(
        self, 
        result: RawScrapeResult, 
        strategy: ExtractionStrategy
    ) -> ExtractedContent:
        """Apply extraction strategy to raw scrape result."""
        pass
    
    async def convert_format(
        self, 
        content: ExtractedContent, 
        target_format: OutputFormat
    ) -> ConvertedContent:
        """Convert content to target format."""
        pass
```

#### Data Models

```python
@dataclass
class ScrapeRequest:
    """Request model for single-page scraping."""
    url: str
    options: ScrapeOptions
    extraction_strategy: Optional[ExtractionStrategy] = None
    output_format: OutputFormat = OutputFormat.MARKDOWN
    session_id: Optional[str] = None
    
@dataclass
class ScrapeOptions:
    """Configuration options for scraping."""
    # Browser options
    headless: bool = True
    timeout: int = 30
    user_agent: Optional[str] = None
    proxy: Optional[ProxyConfig] = None
    
    # Content options
    wait_for: Optional[str] = None
    js_code: Optional[List[str]] = None
    screenshot: bool = False
    pdf: bool = False
    
    # Processing options
    cache_enabled: bool = True
    retry_count: int = 3
    
@dataclass
class ScrapeResult:
    """Result of a scraping operation."""
    success: bool
    url: str
    content: Optional[ExtractedContent] = None
    metadata: ScrapeMetadata = None
    error: Optional[ErrorInfo] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

### 2. CrawlService

#### Purpose
Handles multi-page crawling operations with intelligent link discovery and navigation.

#### Key Responsibilities
- Execute multi-page crawling operations
- Discover and follow links based on crawl rules
- Manage crawl scope and depth
- Handle site-specific crawling strategies
- Coordinate with session management

#### Interface Design

```python
class CrawlService:
    """Service for handling multi-page crawling operations."""
    
    async def start_crawl(
        self, 
        request: CrawlRequest, 
        context: Optional[RequestContext] = None
    ) -> CrawlJob:
        """Start a new crawling job."""
        pass
    
    async def get_crawl_status(
        self, 
        job_id: str
    ) -> CrawlStatus:
        """Get current status of a crawling job."""
        pass
    
    async def cancel_crawl(
        self, 
        job_id: str
    ) -> bool:
        """Cancel a running crawl job."""
        pass
    
    async def discover_links(
        self, 
        page_result: ScrapeResult, 
        crawl_rules: CrawlRules
    ) -> List[str]:
        """Discover crawlable links from a page."""
        pass
    
    async def process_crawl_page(
        self, 
        url: str, 
        crawl_context: CrawlContext
    ) -> ScrapeResult:
        """Process a single page within a crawl job."""
        pass
```

#### Data Models

```python
@dataclass
class CrawlRequest:
    """Request model for multi-page crawling."""
    start_url: str
    crawl_rules: CrawlRules
    scrape_options: ScrapeOptions
    limits: CrawlLimits
    output_options: OutputOptions
    
@dataclass
class CrawlRules:
    """Rules defining crawling behavior."""
    # URL filtering
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    
    # Domain restrictions
    allow_external_links: bool = False
    allow_subdomains: bool = True
    
    # Depth and scope
    max_depth: int = 3
    max_pages: int = 100
    
    # Timing
    delay_between_requests: float = 1.0
    respect_robots_txt: bool = True
    
@dataclass
class CrawlLimits:
    """Limits for crawling operations."""
    max_pages: int = 100
    max_depth: int = 3
    max_duration: int = 3600  # seconds
    max_concurrent_requests: int = 5
    
@dataclass
class CrawlJob:
    """Represents a crawling job."""
    job_id: str
    start_url: str
    status: CrawlStatus
    created_at: datetime
    updated_at: datetime
    results: List[ScrapeResult] = field(default_factory=list)
    errors: List[ErrorInfo] = field(default_factory=list)
    metrics: CrawlMetrics = field(default_factory=CrawlMetrics)
```

### 3. SessionService

#### Purpose
Manages browser sessions and maintains state across multiple operations.

#### Key Responsibilities
- Create and manage browser sessions
- Maintain session state for complex interactions
- Handle session pooling and resource management
- Provide session cleanup and lifecycle management
- Support session persistence across service restarts

#### Interface Design

```python
class SessionService:
    """Service for managing browser sessions."""
    
    async def create_session(
        self, 
        session_config: SessionConfig
    ) -> Session:
        """Create a new browser session."""
        pass
    
    async def get_session(
        self, 
        session_id: str
    ) -> Optional[Session]:
        """Retrieve an existing session."""
        pass
    
    async def close_session(
        self, 
        session_id: str
    ) -> bool:
        """Close a browser session."""
        pass
    
    async def execute_in_session(
        self, 
        session_id: str, 
        operation: SessionOperation
    ) -> OperationResult:
        """Execute an operation within a session."""
        pass
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        pass
```

#### Data Models

```python
@dataclass
class SessionConfig:
    """Configuration for browser sessions."""
    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    timeout: int = 30
    user_agent: Optional[str] = None
    proxy: Optional[ProxyConfig] = None
    viewport: Optional[ViewportConfig] = None
    
@dataclass
class Session:
    """Represents a browser session."""
    session_id: str
    config: SessionConfig
    created_at: datetime
    last_accessed: datetime
    page_count: int = 0
    is_active: bool = True
    
@dataclass
class SessionOperation:
    """Operation to be executed in a session."""
    operation_type: OperationType
    parameters: Dict[str, Any]
    timeout: Optional[int] = None
```

## Core Layer Components

### 1. CrawlEngine

#### Purpose
Provides the core crawling functionality by wrapping and orchestrating crawl4ai operations.

#### Key Responsibilities
- Direct integration with crawl4ai's AsyncWebCrawler
- Configuration translation between our API and crawl4ai
- Strategy execution and result processing
- Error handling and retry logic
- Resource management and cleanup

#### Interface Design

```python
class CrawlEngine:
    """Core engine for crawling operations."""
    
    async def execute_scrape(
        self, 
        request: ScrapeRequest, 
        session: Optional[Session] = None
    ) -> RawScrapeResult:
        """Execute a single scraping operation."""
        pass
    
    async def execute_batch_scrape(
        self, 
        urls: List[str], 
        options: ScrapeOptions
    ) -> List[RawScrapeResult]:
        """Execute batch scraping operations."""
        pass
    
    async def apply_extraction_strategy(
        self, 
        result: RawScrapeResult, 
        strategy: ExtractionStrategy
    ) -> ExtractedContent:
        """Apply extraction strategy to raw results."""
        pass
    
    def translate_config(
        self, 
        options: ScrapeOptions
    ) -> CrawlerRunConfig:
        """Translate our config to crawl4ai config."""
        pass
```

### 2. JobManager

#### Purpose
Manages asynchronous job execution, status tracking, and queue management.

#### Key Responsibilities
- Job queue management and prioritization
- Status tracking and progress reporting
- Error handling and retry logic
- Resource allocation and concurrency control
- Job persistence and recovery

#### Interface Design

```python
class JobManager:
    """Manager for asynchronous job execution."""
    
    async def submit_job(
        self, 
        job: Job, 
        priority: JobPriority = JobPriority.NORMAL
    ) -> str:
        """Submit a job for execution."""
        pass
    
    async def get_job_status(
        self, 
        job_id: str
    ) -> JobStatus:
        """Get current status of a job."""
        pass
    
    async def cancel_job(
        self, 
        job_id: str
    ) -> bool:
        """Cancel a running job."""
        pass
    
    async def get_job_result(
        self, 
        job_id: str
    ) -> Optional[JobResult]:
        """Get result of a completed job."""
        pass
    
    async def cleanup_completed_jobs(
        self, 
        older_than: datetime
    ) -> int:
        """Clean up old completed jobs."""
        pass
```

### 3. StorageManager

#### Purpose
Handles all data persistence, caching, and storage operations using SQLite as the unified backend.

#### Key Responsibilities
- SQLite-based result storage and retrieval
- SQLite-based cache management and invalidation
- SQLite-based session persistence
- Configuration storage in SQLite
- SQLite data cleanup and archival with automatic cleanup procedures

#### Interface Design

```python
class StorageManager:
    """Manager for SQLite-based data storage and caching."""
    
    def __init__(self, db_path: str = "crawler.db"):
        """Initialize SQLite storage manager."""
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        """Set up SQLite database schema."""
        pass
    
    async def store_result(
        self, 
        result: ScrapeResult,
        job_id: Optional[str] = None
    ) -> str:
        """Store a scraping result in SQLite."""
        pass
    
    async def get_cached_result(
        self, 
        cache_key: str
    ) -> Optional[ScrapeResult]:
        """Retrieve cached result from SQLite cache table."""
        pass
    
    async def store_session_state(
        self, 
        session: Session
    ) -> bool:
        """Store session state in SQLite for persistence."""
        pass
    
    async def get_session_state(
        self,
        session_id: str
    ) -> Optional[Session]:
        """Retrieve session state from SQLite."""
        pass
    
    async def cleanup_old_data(
        self, 
        retention_policy: RetentionPolicy
    ) -> int:
        """Clean up old data from SQLite based on retention policy."""
        pass
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries from SQLite."""
        pass
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions from SQLite."""
        pass
```

#### SQLite Schema Design

```sql
-- Core tables for unified SQLite storage
CREATE TABLE crawl_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    url TEXT NOT NULL,
    title TEXT,
    success BOOLEAN DEFAULT FALSE,
    status_code INTEGER,
    content_markdown TEXT,
    content_html TEXT,
    content_text TEXT,
    extracted_data JSON,
    metadata JSON,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX(job_id),
    INDEX(url),
    INDEX(created_at)
);

CREATE TABLE browser_sessions (
    session_id TEXT PRIMARY KEY,
    config JSON,
    state_data JSON,
    page_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    INDEX(expires_at),
    INDEX(last_accessed)
);

CREATE TABLE cache_entries (
    cache_key TEXT PRIMARY KEY,
    data_value JSON,
    data_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    access_count INTEGER DEFAULT 0,
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX(expires_at),
    INDEX(access_count)
);

CREATE TABLE job_queue (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    job_data JSON,
    result_data JSON,
    error_message TEXT,
    INDEX(status),
    INDEX(priority),
    INDEX(created_at)
);
```

## Foundation Layer Components

### 1. ConfigManager

#### Purpose
Centralized configuration management with validation and environment resolution.

#### Key Responsibilities
- Load configuration from multiple sources
- Validate configuration values
- Resolve environment variables
- Provide configuration hot-reloading
- Handle configuration inheritance

#### Interface Design

```python
class ConfigManager:
    """Centralized configuration management."""
    
    def load_config(
        self, 
        config_path: Optional[str] = None
    ) -> AppConfig:
        """Load configuration from file and environment."""
        pass
    
    def validate_config(
        self, 
        config: AppConfig
    ) -> ValidationResult:
        """Validate configuration values."""
        pass
    
    def get_setting(
        self, 
        key: str, 
        default: Any = None
    ) -> Any:
        """Get a configuration setting."""
        pass
    
    def update_setting(
        self, 
        key: str, 
        value: Any
    ) -> bool:
        """Update a configuration setting."""
        pass
```

### 2. ErrorHandler

#### Purpose
Centralized error handling with categorization, retry logic, and reporting.

#### Key Responsibilities
- Error categorization and classification
- Retry logic with exponential backoff
- Error reporting and logging
- Error recovery strategies
- Error metrics collection

#### Interface Design

```python
class ErrorHandler:
    """Centralized error handling."""
    
    def handle_error(
        self, 
        error: Exception, 
        context: ErrorContext
    ) -> ErrorResult:
        """Handle and categorize an error."""
        pass
    
    def should_retry(
        self, 
        error: Exception, 
        attempt: int
    ) -> bool:
        """Determine if operation should be retried."""
        pass
    
    def get_retry_delay(
        self, 
        attempt: int
    ) -> float:
        """Calculate retry delay."""
        pass
    
    def report_error(
        self, 
        error: ErrorInfo
    ) -> bool:
        """Report error to monitoring system."""
        pass
```

### 3. MetricsCollector

#### Purpose
Collect and aggregate system metrics for monitoring and observability.

#### Key Responsibilities
- Performance metrics collection
- Business metrics tracking
- System health metrics
- Metrics aggregation and reporting
- Integration with monitoring systems

#### Interface Design

```python
class MetricsCollector:
    """Metrics collection and aggregation."""
    
    def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric value."""
        pass
    
    def increment_counter(
        self, 
        counter_name: str, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        pass
    
    def record_timing(
        self, 
        operation_name: str, 
        duration: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record operation timing."""
        pass
    
    def get_metrics_summary(self) -> MetricsSummary:
        """Get summary of collected metrics."""
        pass
```

## Component Interactions

### Request Processing Flow

1. **Interface Layer** receives request
2. **Service Layer** validates and processes request
3. **Core Layer** executes operations
4. **Foundation Layer** provides support services
5. **Results** flow back through layers

### Error Handling Flow

1. **Error occurs** in any layer
2. **ErrorHandler** categorizes and processes error
3. **Retry logic** determines if retry is needed
4. **Metrics** are recorded for monitoring
5. **Error response** is formatted and returned

### Configuration Flow

1. **ConfigManager** loads configuration at startup
2. **Validation** ensures configuration is valid
3. **Components** access configuration through manager
4. **Runtime updates** are propagated to components

## Testing Strategy

### Unit Testing
- Individual component testing
- Mock external dependencies
- Test error conditions
- Validate configuration handling

### Integration Testing
- Component interaction testing
- End-to-end workflow testing
- Database integration testing
- External service integration

### Performance Testing
- Load testing with concurrent requests
- Memory usage profiling
- Resource cleanup verification
- Scalability testing

## Deployment Considerations

### Resource Requirements
- Memory: 2GB minimum, 4GB recommended
- CPU: 2 cores minimum, 4 cores recommended
- Storage: 10GB minimum for cache and results
- Network: Stable internet connection

### Scaling Considerations
- **Phase 1**: Single-instance SQLite deployment for rapid development
- **Phase 2**: Multiple instances with shared SQLite database (NFS/network storage)
- **Phase 3**: Migration to PostgreSQL when scale requirements grow
- **SQLite Optimization**: WAL mode, connection pooling, and query optimization

### Monitoring Requirements
- Health check endpoints
- Metrics collection
- Log aggregation
- Alert configuration

## Security Considerations

### Input Validation
- URL validation and sanitization
- Parameter validation
- File upload restrictions
- Content filtering

### Access Control
- API key authentication
- Role-based authorization
- Rate limiting
- IP whitelisting

### Data Protection
- Sensitive data handling
- Encryption at rest
- Secure communication
- Data retention policies

## Future Enhancements

### Planned Features
- Machine learning for intelligent crawling (based on `groundtruth/crawl4ai_context.md` capabilities)
- Advanced content extraction strategies from crawl4ai 0.6.3+
- Real-time crawling capabilities
- Advanced analytics and reporting
- **Database Migration**: Seamless migration from SQLite to PostgreSQL when scale requirements grow

### Extensibility Points
- Plugin architecture for custom extractors
- **Storage Backend Migration**: Easy migration path from SQLite to distributed storage
- Custom authentication providers
- Custom monitoring integrations
- **Crawl4AI Integration**: Leverage new crawl4ai features as they become available

### SQLite to Distributed Storage Migration
- **Data Compatibility**: Maintain compatible data formats for easy migration
- **Migration Tools**: Automated migration scripts from SQLite to PostgreSQL
- **Hybrid Mode**: Support for running both SQLite and distributed storage during migration
- **Zero-Downtime Migration**: Strategies for migrating without service interruption