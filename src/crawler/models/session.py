"""Pydantic models for session management."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator, HttpUrl, ConfigDict


class BrowserType(str, Enum):
    """Supported browser types."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class SessionStatus(str, Enum):
    """Status of browser sessions."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    ERROR = "error"


class ProxyConfig(BaseModel):
    """Proxy configuration for browser sessions."""
    
    url: str = Field(..., description="Proxy URL (http/https/socks5)")
    username: Optional[str] = None
    password: Optional[str] = None
    bypass_list: List[str] = Field(default_factory=list, description="Domains to bypass proxy")
    
    @field_validator('url')
    @classmethod
    def validate_proxy_url(cls, v):
        if not any(v.startswith(proto) for proto in ['http://', 'https://', 'socks5://']):
            raise ValueError('Proxy URL must start with http://, https://, or socks5://')
        return v


class ViewportConfig(BaseModel):
    """Browser viewport configuration."""
    
    width: int = Field(default=1920, ge=320, le=7680)
    height: int = Field(default=1080, ge=240, le=4320)
    device_scale_factor: float = Field(default=1.0, ge=0.1, le=5.0)
    is_mobile: bool = False
    has_touch: bool = False


class BrowserOptions(BaseModel):
    """Advanced browser configuration options."""
    
    # Performance
    disable_images: bool = False
    disable_javascript: bool = False
    disable_css: bool = False
    disable_plugins: bool = True
    
    # Security
    ignore_https_errors: bool = False
    ignore_certificate_errors: bool = False
    
    # Features
    enable_request_interception: bool = False
    enable_response_compression: bool = True
    
    # Downloads
    download_directory: Optional[str] = None
    auto_download: bool = False
    
    # Additional options
    extra_args: List[str] = Field(default_factory=list)
    env_vars: Dict[str, str] = Field(default_factory=dict)


class SessionConfiguration(BaseModel):
    """Complete configuration for a browser session."""
    
    # Basic settings
    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    
    # Timeouts
    timeout: int = Field(default=30, ge=1, le=300, description="Page load timeout in seconds")
    idle_timeout: int = Field(default=1800, ge=60, le=86400, description="Session idle timeout in seconds")
    
    # Browser identity
    user_agent: Optional[str] = None
    locale: str = "en-US"
    timezone: str = "UTC"
    
    # Network
    proxy: Optional[ProxyConfig] = None
    
    # Display
    viewport: ViewportConfig = Field(default_factory=ViewportConfig)
    
    # Advanced options
    browser_options: BrowserOptions = Field(default_factory=BrowserOptions)
    
    # Persistence
    user_data_dir: Optional[str] = None
    persist_context: bool = False
    
    model_config = ConfigDict(use_enum_values=True)


class SessionState(BaseModel):
    """Runtime state of a browser session."""
    
    # Cookies and storage
    cookies: Dict[str, Any] = Field(default_factory=dict)
    local_storage: Dict[str, str] = Field(default_factory=dict)
    session_storage: Dict[str, str] = Field(default_factory=dict)
    
    # Authentication
    auth_tokens: Dict[str, str] = Field(default_factory=dict)
    
    # Navigation state
    current_url: Optional[HttpUrl] = None
    page_title: Optional[str] = None
    
    # Performance data
    page_load_times: List[float] = Field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    
    # Custom data
    custom_data: Dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    """Information about a browser session."""
    
    session_id: str
    status: SessionStatus
    configuration: SessionConfiguration
    state: SessionState
    
    # Timestamps
    created_at: datetime
    last_accessed: datetime
    expires_at: Optional[datetime] = None
    
    # Usage statistics
    page_count: int = 0
    total_requests: int = 0
    total_errors: int = 0
    
    # Resource usage
    memory_usage: Optional[int] = None  # in MB
    cpu_usage: Optional[float] = None  # percentage
    
    @property
    def age_seconds(self) -> float:
        """Age of the session in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    @property
    def idle_seconds(self) -> float:
        """Idle time in seconds."""
        return (datetime.utcnow() - self.last_accessed).total_seconds()
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.total_requests
        if total == 0:
            return 0.0
        return ((total - self.total_errors) / total) * 100


class SessionRequest(BaseModel):
    """Request to create a new session."""
    
    session_id: Optional[str] = None
    configuration: Optional[SessionConfiguration] = None
    initial_url: Optional[HttpUrl] = None
    timeout: Optional[int] = Field(default=None, ge=60, le=86400)
    
    # Metadata
    name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    """Response after creating a session."""
    
    session_id: str
    status: SessionStatus
    message: Optional[str] = None
    configuration: SessionConfiguration
    expires_at: Optional[datetime] = None


class SessionUpdate(BaseModel):
    """Update request for session state."""
    
    state_updates: Optional[Dict[str, Any]] = None
    configuration_updates: Optional[Dict[str, Any]] = None
    extend_timeout: Optional[int] = None


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    
    sessions: List[SessionInfo]
    total_count: int
    active_count: int
    expired_count: int


class SessionStatistics(BaseModel):
    """Statistics about session usage."""
    
    # Counts
    total_sessions: int = 0
    active_sessions: int = 0
    expired_sessions: int = 0
    
    # Usage patterns
    average_session_duration: float = 0.0
    average_pages_per_session: float = 0.0
    peak_concurrent_sessions: int = 0
    
    # Resource usage
    total_memory_usage: int = 0  # MB
    average_memory_per_session: float = 0.0
    
    # Time ranges
    oldest_session_age: Optional[float] = None
    newest_session_age: Optional[float] = None
    
    # Browser distribution
    browser_distribution: Dict[str, int] = Field(default_factory=dict)
    
    # Error tracking
    total_errors: int = 0
    error_rate: float = 0.0
    common_errors: Dict[str, int] = Field(default_factory=dict)


class SessionEvent(BaseModel):
    """Event that occurred in a session."""
    
    session_id: str
    event_type: str  # "page_load", "error", "timeout", etc.
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Event data
    url: Optional[HttpUrl] = None
    message: Optional[str] = None
    error_code: Optional[str] = None
    duration: Optional[float] = None
    
    # Context
    page_title: Optional[str] = None
    response_status: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class SessionCleanupConfig(BaseModel):
    """Configuration for session cleanup operations."""
    
    # Cleanup triggers
    max_idle_time: int = Field(default=1800, ge=60)  # seconds
    max_session_age: int = Field(default=86400, ge=3600)  # seconds
    max_concurrent_sessions: int = Field(default=100, ge=1)
    
    # Cleanup behavior
    cleanup_interval: int = Field(default=300, ge=60)  # seconds
    grace_period: int = Field(default=60, ge=0)  # seconds before force cleanup
    
    # Retention
    keep_session_history: bool = True
    history_retention_days: int = Field(default=7, ge=1)


class SessionPool(BaseModel):
    """Pool of browser sessions for efficient reuse."""
    
    pool_id: str
    configuration: SessionConfiguration
    
    # Pool settings
    min_sessions: int = Field(default=1, ge=0)
    max_sessions: int = Field(default=10, ge=1)
    session_ttl: int = Field(default=3600, ge=60)  # seconds
    
    # Current state
    active_sessions: int = 0
    idle_sessions: int = 0
    
    # Usage statistics
    total_requests_served: int = 0
    average_wait_time: float = 0.0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SessionMetrics(BaseModel):
    """Detailed metrics for session monitoring."""
    
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Performance metrics
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Network metrics
    requests_per_minute: float = 0.0
    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    
    # Page metrics
    pages_loaded: int = 0
    average_load_time: float = 0.0
    errors_encountered: int = 0
    
    # Browser metrics
    dom_nodes: Optional[int] = None
    javascript_heap_size: Optional[int] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)