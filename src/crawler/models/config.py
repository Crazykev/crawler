"""Pydantic models for configuration management."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseType(str, Enum):
    """Supported database types."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"


class ScrapeConfig(BaseModel):
    """Configuration for scraping operations."""
    
    # Timeouts
    timeout: int = Field(default=30, ge=1, le=300)
    retry_attempts: int = Field(default=1, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.0, le=60.0)
    
    # Browser settings
    headless: bool = True
    user_agent: str = "Crawler/1.0"
    
    # Caching
    cache_enabled: bool = True
    cache_ttl: int = Field(default=3600, ge=0)
    cache_size_limit: int = Field(default=1000, ge=0, description="Max number of cached items")
    
    # Rate limiting
    default_delay: float = Field(default=1.0, ge=0.0)
    max_concurrent: int = Field(default=5, ge=1, le=50)
    
    model_config = ConfigDict(use_enum_values=True)


class CrawlConfig(BaseModel):
    """Configuration for crawling operations."""
    
    # Default limits
    max_depth: int = Field(default=3, ge=0, le=10)
    max_pages: int = Field(default=100, ge=1, le=10000)
    max_duration: int = Field(default=3600, ge=60, le=86400)
    
    # Default behavior
    delay: float = Field(default=1.0, ge=0.0, le=60.0)
    concurrent_requests: int = Field(default=5, ge=1, le=20)
    respect_robots: bool = True
    allow_external_links: bool = False
    allow_subdomains: bool = True
    
    # URL filtering
    default_include_patterns: List[str] = Field(default_factory=list)
    default_exclude_patterns: List[str] = Field(default_factory=list)
    
    model_config = ConfigDict(use_enum_values=True)


class BrowserConfig(BaseModel):
    """Configuration for browser instances."""
    
    # Default browser settings
    default_browser: str = "chromium"
    headless: bool = True
    timeout: int = Field(default=30, ge=1, le=300)
    
    # Viewport
    viewport_width: int = Field(default=1920, ge=100, le=7680)
    viewport_height: int = Field(default=1080, ge=100, le=4320)
    
    # Network
    user_agent: str = "Crawler/1.0"
    proxy_url: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    # Performance
    disable_images: bool = False
    disable_javascript: bool = False
    disable_css: bool = False
    
    model_config = ConfigDict(use_enum_values=True)


class StorageConfig(BaseModel):
    """Configuration for storage systems."""
    
    # Database
    database_type: DatabaseType = DatabaseType.SQLITE
    database_url: str = "sqlite:///crawler.db"
    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_timeout: int = Field(default=30, ge=1, le=300)
    
    # Sessions
    session_timeout: int = Field(default=1800, ge=60, le=86400)
    session_cleanup_interval: int = Field(default=300, ge=60)
    
    # Cache
    cache_size: int = Field(default=1000, ge=0)
    cache_ttl: int = Field(default=3600, ge=0)
    
    # File storage
    storage_directory: str = "./storage"
    max_file_size: int = Field(default=100*1024*1024, ge=0, description="Max file size in bytes")
    
    model_config = ConfigDict(use_enum_values=True)


class LoggingConfig(BaseModel):
    """Configuration for logging."""
    
    # Log levels
    level: LogLevel = LogLevel.WARNING
    file_level: Optional[LogLevel] = None
    console_level: Optional[LogLevel] = None
    
    # Log files
    file: Optional[str] = "crawler.log"
    max_file_size: int = Field(default=10*1024*1024, ge=0, description="Max log file size in bytes")
    backup_count: int = Field(default=5, ge=0)
    
    # Format
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    
    # Features
    enable_structured_logging: bool = False
    log_requests: bool = True
    log_responses: bool = False
    
    model_config = ConfigDict(use_enum_values=True)


class MetricsConfig(BaseModel):
    """Configuration for metrics collection."""
    
    # Collection
    enabled: bool = True
    collection_interval: int = Field(default=60, ge=1, le=3600)
    
    # Storage
    retention_days: int = Field(default=30, ge=1, le=365)
    aggregation_interval: int = Field(default=300, ge=60)
    
    # Export
    export_enabled: bool = False
    export_endpoint: Optional[str] = None
    export_format: str = "prometheus"
    
    # Monitoring
    alert_thresholds: Dict[str, float] = Field(default_factory=dict)
    
    model_config = ConfigDict(use_enum_values=True)


class LLMConfig(BaseModel):
    """Configuration for LLM integrations."""
    
    # API Keys (stored separately in environment/secrets)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    azure_api_key: Optional[str] = None
    
    # Default models
    default_model: str = "openai/gpt-4"
    fallback_model: Optional[str] = None
    
    # Request settings
    default_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    default_max_tokens: Optional[int] = Field(default=None, ge=1)
    request_timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    
    # Rate limiting
    requests_per_minute: int = Field(default=60, ge=1)
    
    model_config = ConfigDict(use_enum_values=True)


class JobsConfig(BaseModel):
    """Configuration for job processing."""
    
    # Queue settings
    max_concurrent: int = Field(default=10, ge=1, le=100)
    max_queue_size: int = Field(default=1000, ge=1, le=10000)
    
    # Job processing
    retry_attempts: int = Field(default=1, ge=0, le=10)
    retry_delay: int = Field(default=5, ge=1, le=300)
    job_timeout: int = Field(default=3600, ge=60, le=86400)
    
    # Cleanup
    cleanup_interval: int = Field(default=3600, ge=300)
    retention_days: int = Field(default=7, ge=1, le=365)
    
    model_config = ConfigDict(use_enum_values=True)


class SecurityConfig(BaseModel):
    """Configuration for security settings."""
    
    # Authentication
    enable_auth: bool = False
    auth_secret_key: Optional[str] = None
    token_expiry: int = Field(default=3600, ge=300, le=86400)
    
    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: int = Field(default=60, ge=1)
    
    # CORS
    enable_cors: bool = True
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    
    # Input validation
    max_request_size: int = Field(default=10*1024*1024, ge=0)
    sanitize_inputs: bool = True
    
    model_config = ConfigDict(use_enum_values=True)


class APIConfig(BaseModel):
    """Configuration for API servers."""
    
    # Server settings
    host: str = "localhost"
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1, le=20)
    
    # Features
    enable_docs: bool = True
    enable_metrics: bool = True
    enable_health_check: bool = True
    
    # Timeouts
    request_timeout: int = Field(default=30, ge=1, le=300)
    
    model_config = ConfigDict(use_enum_values=True)


class CrawlerConfiguration(BaseModel):
    """Complete crawler configuration."""
    
    # Component configurations
    scrape: ScrapeConfig = Field(default_factory=ScrapeConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    jobs: JobsConfig = Field(default_factory=JobsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    
    # Metadata
    config_version: str = "1.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Environment
    environment: str = "development"
    debug: bool = False


class ConfigSource(BaseModel):
    """Information about configuration source."""
    
    source_type: str  # "file", "environment", "default", "override"
    source_path: Optional[str] = None
    loaded_at: datetime = Field(default_factory=datetime.utcnow)
    checksum: Optional[str] = None


class ConfigValidationResult(BaseModel):
    """Result of configuration validation."""
    
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.utcnow)


class ConfigUpdate(BaseModel):
    """Request to update configuration."""
    
    section: str
    key: str
    value: Any
    source: str = "api"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConfigExport(BaseModel):
    """Export configuration data."""
    
    configuration: CrawlerConfiguration
    sources: List[ConfigSource]
    exported_at: datetime = Field(default_factory=datetime.utcnow)
    export_format: str = "yaml"  # "yaml", "json", "toml"


class ConfigTemplate(BaseModel):
    """Configuration template for different use cases."""
    
    name: str
    description: Optional[str] = None
    category: str  # "web-scraping", "api-crawling", "data-mining", etc.
    
    configuration: CrawlerConfiguration
    
    # Template metadata
    tags: List[str] = Field(default_factory=list)
    use_count: int = 0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Template usage
    prerequisites: List[str] = Field(default_factory=list)
    setup_instructions: Optional[str] = None