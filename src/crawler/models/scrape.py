"""Pydantic models for scraping operations."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, validator, HttpUrl
from pydantic.types import StrictStr


class ExtractionStrategy(str, Enum):
    """Content extraction strategies."""
    AUTO = "auto"
    CSS = "css"
    LLM = "llm"


class OutputFormat(str, Enum):
    """Output formats for scraped content."""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    TEXT = "text"


class ScrapeOptions(BaseModel):
    """Configuration options for scraping operations."""
    
    # Browser options
    headless: bool = True
    timeout: int = Field(default=30, ge=1, le=300)
    user_agent: Optional[str] = None
    viewport_width: int = Field(default=1920, ge=100, le=4000)
    viewport_height: int = Field(default=1080, ge=100, le=4000)
    
    # Page interaction
    wait_for: Optional[str] = None  # CSS selector to wait for
    js_code: Optional[str] = None  # JavaScript to execute
    screenshot: bool = False
    pdf: bool = False
    
    # Caching
    cache_enabled: bool = True
    cache_ttl: Optional[int] = Field(default=None, ge=0)
    
    # Network
    proxy_url: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    # Session
    session_id: Optional[str] = None
    
    class Config:
        use_enum_values = True


class CSSExtractionConfig(BaseModel):
    """Configuration for CSS-based content extraction."""
    
    selectors: Union[str, Dict[str, str]] = Field(
        ..., 
        description="CSS selector(s) for content extraction"
    )
    remove_selectors: Optional[List[str]] = Field(
        default=None,
        description="CSS selectors for elements to remove"
    )
    extract_attributes: Optional[List[str]] = Field(
        default=None,
        description="HTML attributes to extract"
    )


class LLMExtractionConfig(BaseModel):
    """Configuration for LLM-based content extraction."""
    
    model: str = Field(default="openai/gpt-4", description="LLM model to use")
    prompt: Optional[str] = Field(default=None, description="Custom extraction prompt")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    
    @validator('model')
    def validate_model_format(cls, v):
        if '/' not in v:
            raise ValueError('Model must be in format "provider/model"')
        return v


class ExtractionStrategyConfig(BaseModel):
    """Configuration for content extraction strategy."""
    
    type: ExtractionStrategy
    css: Optional[CSSExtractionConfig] = None
    llm: Optional[LLMExtractionConfig] = None
    
    @validator('css')
    def validate_css_config(cls, v, values):
        if values.get('type') == ExtractionStrategy.CSS and v is None:
            raise ValueError('CSS configuration required when using CSS strategy')
        return v


class LinkInfo(BaseModel):
    """Information about discovered links."""
    
    url: HttpUrl
    text: Optional[str] = None
    title: Optional[str] = None
    rel: Optional[str] = None
    type: Optional[str] = None


class ImageInfo(BaseModel):
    """Information about discovered images."""
    
    url: HttpUrl
    alt: Optional[str] = None
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class ScrapingMetadata(BaseModel):
    """Metadata about the scraping operation."""
    
    url: HttpUrl
    final_url: Optional[HttpUrl] = None  # After redirects
    status_code: int
    load_time: float = Field(ge=0.0)
    size: int = Field(ge=0, description="Content size in bytes")
    timestamp: datetime
    user_agent: Optional[str] = None
    extraction_strategy: Optional[str] = None
    output_format: OutputFormat
    
    # Technical details
    response_headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    local_storage: Optional[Dict[str, str]] = None
    session_storage: Optional[Dict[str, str]] = None


class ScrapeRequest(BaseModel):
    """Request model for scraping operations."""
    
    url: HttpUrl
    options: Optional[ScrapeOptions] = None
    extraction_strategy: Optional[ExtractionStrategyConfig] = None
    output_format: OutputFormat = OutputFormat.MARKDOWN
    store_result: bool = True


class ScrapeResult(BaseModel):
    """Result of a scraping operation."""
    
    success: bool
    url: HttpUrl
    title: Optional[str] = None
    content: Optional[str] = None
    error: Optional[str] = None
    
    # Extracted data
    links: List[LinkInfo] = Field(default_factory=list)
    images: List[ImageInfo] = Field(default_factory=list)
    
    # Metadata
    metadata: Optional[ScrapingMetadata] = None
    
    # Files generated
    screenshot_path: Optional[str] = None
    pdf_path: Optional[str] = None
    
    # Processing info
    job_id: Optional[str] = None
    crawl_id: Optional[str] = None


class BatchScrapeRequest(BaseModel):
    """Request model for batch scraping operations."""
    
    urls: List[HttpUrl]
    options: Optional[ScrapeOptions] = None
    extraction_strategy: Optional[ExtractionStrategyConfig] = None
    output_format: OutputFormat = OutputFormat.MARKDOWN
    concurrent_requests: int = Field(default=5, ge=1, le=20)
    delay: float = Field(default=1.0, ge=0.0)
    continue_on_error: bool = True
    store_results: bool = True


class BatchScrapeResult(BaseModel):
    """Result of a batch scraping operation."""
    
    total_urls: int
    successful: int
    failed: int
    results: List[ScrapeResult]
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    processing_time: float
    job_id: Optional[str] = None


class AsyncJobRequest(BaseModel):
    """Request for async job submission."""
    
    operation_type: str  # "scrape" or "crawl"
    parameters: Dict[str, Any]
    priority: int = Field(default=0, ge=-10, le=10)
    callback_url: Optional[HttpUrl] = None


class AsyncJobResponse(BaseModel):
    """Response for async job submission."""
    
    job_id: str
    status: str
    message: Optional[str] = None
    estimated_completion: Optional[datetime] = None