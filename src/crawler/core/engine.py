"""Core crawling engine that integrates with crawl4ai."""

import asyncio
import os
import ssl
import socket
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta

try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import ExtractionStrategy as Crawl4aiStrategy
    from crawl4ai.chunking_strategy import RegexChunking
    from crawl4ai.models import CrawlResult as Crawl4aiResult
except ImportError:
    # Fallback for development/testing
    AsyncWebCrawler = None
    Crawl4aiStrategy = None
    RegexChunking = None
    Crawl4aiResult = None

from ..foundation.config import get_config_manager
from ..foundation.logging import get_logger
from ..foundation.errors import (
    handle_error, NetworkError, TimeoutError, ExtractionError, 
    ConfigurationError, ValidationError, ErrorContext
)
from ..foundation.metrics import get_metrics_collector, timer
from .storage import get_storage_manager


class CrawlerPool:
    """Pool of crawler instances for better performance."""
    
    def __init__(self, max_size: int = 5):
        self.max_size = max_size
        self._available = asyncio.Queue(maxsize=max_size)
        self._in_use = set()
        self._lock = asyncio.Lock()
        self._total_created = 0
    
    @property
    def pool_size(self) -> int:
        """Get current pool size."""
        return self._available.qsize() + len(self._in_use)
    
    @property
    def available_count(self) -> int:
        """Get number of available connections."""
        return self._available.qsize()
    
    @property
    def in_use_count(self) -> int:
        """Get number of connections in use."""
        return len(self._in_use)
    
    async def get_crawler(self, config: Dict[str, Any]) -> AsyncWebCrawler:
        """Get a crawler from the pool."""
        async with self._lock:
            if not self._available.empty():
                crawler = await self._available.get()
                self._in_use.add(crawler)
                return crawler
            
            # Create new crawler if pool not full
            if len(self._in_use) < self.max_size:
                crawler = AsyncWebCrawler(**config)
                self._in_use.add(crawler)
                return crawler
            
            # Wait for available crawler
            crawler = await self._available.get()
            self._in_use.add(crawler)
            return crawler
    
    async def return_crawler(self, crawler: AsyncWebCrawler):
        """Return a crawler to the pool."""
        async with self._lock:
            if crawler in self._in_use:
                self._in_use.remove(crawler)
                try:
                    await self._available.put(crawler)
                except asyncio.QueueFull:
                    # Close excess crawlers
                    if hasattr(crawler, 'close'):
                        await crawler.close()
    
    async def close_all(self):
        """Close all crawlers in the pool."""
        async with self._lock:
            # Close all available crawlers
            while not self._available.empty():
                crawler = await self._available.get()
                if hasattr(crawler, 'close'):
                    await crawler.close()
            
            # Close all in-use crawlers
            for crawler in self._in_use:
                if hasattr(crawler, 'close'):
                    await crawler.close()
            
            self._in_use.clear()


class ConfigBuilder:
    """Builder for crawler configurations."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def build_basic_config(self) -> Dict[str, Any]:
        """Build basic configuration."""
        return {
            "headless": True,
            "user_agent": "Crawler/1.0",
            "viewport_width": 1920,
            "viewport_height": 1080,
        }
    
    def build_advanced_config(self, **kwargs) -> Dict[str, Any]:
        """Build advanced configuration with custom options."""
        config = self.build_basic_config()
        config.update(kwargs)
        return config


class ErrorHandler:
    """Centralized error handling for the engine."""
    
    def __init__(self, logger):
        self.logger = logger
    
    def _create_error_result(self, error: Exception, url: str) -> Dict[str, Any]:
        """Create consistent error result format."""
        return {
            "success": False,
            "url": url,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "code": getattr(error, 'code', None)
            },
            "timestamp": datetime.utcnow().isoformat(),
            "content": None,
            "metadata": {"error_handled": True}
        }
    
    def _handle_network_error(self, error: NetworkError, url: str) -> Dict[str, Any]:
        """Handle network errors consistently."""
        self.logger.error(f"Network error for {url}: {error}")
        return self._create_error_result(error, url)
    
    def _handle_timeout_error(self, error: TimeoutError, url: str) -> Dict[str, Any]:
        """Handle timeout errors consistently."""
        self.logger.error(f"Timeout error for {url}: {error}")
        return self._create_error_result(error, url)
    
    def _handle_extraction_error(self, error: ExtractionError, url: str) -> Dict[str, Any]:
        """Handle extraction errors consistently."""
        self.logger.error(f"Extraction error for {url}: {error}")
        return self._create_error_result(error, url)


class ResourceManager:
    """Manages engine resources and cleanup."""
    
    def __init__(self):
        self.active_resources = {}
        self._resource_counter = 0
    
    async def acquire_resource(self, resource_type: str) -> str:
        """Acquire a resource and return its ID."""
        self._resource_counter += 1
        resource_id = f"{resource_type}_{self._resource_counter}"
        self.active_resources[resource_id] = {
            "type": resource_type,
            "acquired_at": datetime.utcnow()
        }
        return resource_id
    
    async def release_resource(self, resource_id: str):
        """Release a resource."""
        if resource_id in self.active_resources:
            del self.active_resources[resource_id]
    
    async def cleanup_expired(self, max_age_seconds: int = 3600):
        """Clean up expired resources."""
        cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)
        expired_resources = [
            resource_id for resource_id, resource in self.active_resources.items()
            if resource["acquired_at"] < cutoff_time
        ]
        
        for resource_id in expired_resources:
            await self.release_resource(resource_id)


class PerformanceMonitor:
    """Monitors engine performance metrics."""
    
    def __init__(self):
        self.metrics = {}
    
    async def record_timing(self, operation: str, duration: float, tags: Dict[str, Any] = None):
        """Record timing metric."""
        if operation not in self.metrics:
            self.metrics[operation] = []
        
        self.metrics[operation].append({
            "duration": duration,
            "timestamp": datetime.utcnow(),
            "tags": tags or {}
        })
    
    async def record_counter(self, counter: str, value: int = 1, tags: Dict[str, Any] = None):
        """Record counter metric."""
        if counter not in self.metrics:
            self.metrics[counter] = 0
        
        self.metrics[counter] += value
    
    async def get_metrics(self, metric_name: str) -> List[Dict[str, Any]]:
        """Get metrics for a specific metric name."""
        return self.metrics.get(metric_name, [])


class BatchProcessor:
    """Processes batches of requests efficiently."""
    
    def __init__(self, engine):
        self.engine = engine
    
    async def process_batch(self, urls: List[str], options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process a batch of URLs efficiently."""
        tasks = []
        
        for url in urls:
            task = self.engine.scrape_single(url, options)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "url": urls[i],
                    "error": str(result),
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                processed_results.append(result)
        
        return processed_results


class ParallelExecutor:
    """Executes tasks in parallel with concurrency control."""
    
    def __init__(self, semaphore: asyncio.Semaphore):
        self.semaphore = semaphore
    
    async def execute_parallel(self, tasks: List[Any]) -> List[Any]:
        """Execute tasks in parallel with semaphore control."""
        async def controlled_task(task):
            async with self.semaphore:
                return await task
        
        controlled_tasks = [controlled_task(task) for task in tasks]
        return await asyncio.gather(*controlled_tasks, return_exceptions=True)


class ValidationLayer:
    """Validates requests and options."""
    
    def validate(self, url: str, options: Dict[str, Any]) -> bool:
        """Validate URL and options."""
        if not url or not isinstance(url, str):
            raise ValidationError("URL must be a non-empty string")
        
        # Check for basic URL format
        if not url.startswith(('http://', 'https://')):
            raise ValidationError("URL must start with http:// or https://")
        
        # Validate URL structure using urlparse
        try:
            parsed = urlparse(url)
            
            # Check for empty components that should have content
            if not parsed.netloc:
                raise ValidationError("URL must have a valid hostname")
            
            # Check for invalid characters
            if '\x00' in url:
                raise ValidationError("URL contains null characters")
            
            # Check for malformed hostname patterns
            if parsed.netloc.startswith('['):
                # IPv6 address - extract from brackets
                if ']:' in parsed.netloc:
                    hostname = parsed.netloc.split(']:')[0] + ']'
                else:
                    hostname = parsed.netloc
            else:
                # Regular hostname
                hostname = parsed.netloc.split(':')[0]  # Remove port if present
            
            # Only check hostname patterns for regular hostnames, not IPv6
            if not hostname.startswith('[') and hostname:
                if hostname.startswith('.') or hostname.endswith('.') or '..' in hostname:
                    raise ValidationError("URL contains malformed hostname")
            
            # Check for invalid port (handle IPv6 addresses)
            if ':' in parsed.netloc and not parsed.netloc.startswith('['):
                # Not an IPv6 address, check for port
                try:
                    port_part = parsed.netloc.split(':')[-1]
                    port = int(port_part)
                    if port < 1 or port > 65535:
                        raise ValidationError("URL contains invalid port number")
                except (ValueError, IndexError):
                    raise ValidationError("URL contains malformed port")
            elif parsed.netloc.startswith('[') and ']:' in parsed.netloc:
                # IPv6 address with port
                try:
                    port_part = parsed.netloc.split(']:')[1]
                    port = int(port_part)
                    if port < 1 or port > 65535:
                        raise ValidationError("URL contains invalid port number")
                except (ValueError, IndexError):
                    raise ValidationError("URL contains malformed port")
            
            # Check for spaces in URL (not properly encoded)
            if ' ' in url:
                raise ValidationError("URL contains unencoded spaces")
                
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"URL validation failed: {str(e)}")
        
        return True


class ExecutionLayer:
    """Executes crawling operations."""
    
    def __init__(self, crawler_pool):
        self.crawler_pool = crawler_pool
    
    async def execute(self, url: str, config: Dict[str, Any]) -> Any:
        """Execute crawling operation."""
        crawler = await self.crawler_pool.get_crawler(config)
        try:
            result = await crawler.arun(url)
            return result
        finally:
            await self.crawler_pool.return_crawler(crawler)


class ProcessingLayer:
    """Processes crawl results."""
    
    def _extract_links_from_result(self, raw_result) -> List[Dict[str, Any]]:
        """Extract links from raw crawl result and handle crawl4ai's dictionary structure."""
        links = []
        
        try:
            if hasattr(raw_result, 'links') and raw_result.links:
                # Handle crawl4ai's dictionary structure: {'internal': [...], 'external': [...]}
                if isinstance(raw_result.links, dict):
                    # Process internal links
                    internal_links = raw_result.links.get('internal', [])
                    for link in internal_links:
                        if isinstance(link, dict):
                            links.append({
                                "url": link.get("href", ""),
                                "text": link.get("text", ""),
                                "type": "internal"
                            })
                    
                    # Process external links
                    external_links = raw_result.links.get('external', [])
                    for link in external_links:
                        if isinstance(link, dict):
                            links.append({
                                "url": link.get("href", ""),
                                "text": link.get("text", ""),
                                "type": "external"
                            })
                
                # Handle older format where links might be a list
                elif isinstance(raw_result.links, list):
                    for link in raw_result.links:
                        if isinstance(link, dict):
                            links.append({
                                "url": link.get("href", ""),
                                "text": link.get("text", ""),
                                "type": "unknown"
                            })
        except Exception:
            # If link extraction fails, return empty list
            pass
        
        return links
    
    def _safe_decode_content(self, content: str) -> str:
        """Safely decode content handling various encodings."""
        if not content:
            return content
        
        # Handle different string types
        if isinstance(content, bytes):
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            # If all fail, use utf-8 with error handling
            return content.decode('utf-8', errors='replace')
        
        # If already a string, ensure it's properly handled
        if isinstance(content, str):
            # Normalize unicode characters
            import unicodedata
            try:
                # Normalize to NFC form (canonical composition)
                return unicodedata.normalize('NFC', content)
            except Exception:
                # If normalization fails, return as-is
                return content
        
        return str(content)
    
    def process(self, raw_result: Any, url: str) -> Dict[str, Any]:
        """Process raw crawl result."""
        print(f"DEBUG ProcessingLayer.process called for URL: {url}")
        if not raw_result or not hasattr(raw_result, 'success'):
            return {
                "success": False,
                "url": url,
                "error": "Invalid crawl result",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        if not raw_result.success:
            return {
                "success": False,
                "url": url,
                "error": getattr(raw_result, 'error_message', 'Unknown error'),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Process content with proper encoding handling
        html_content = self._safe_decode_content(getattr(raw_result, 'html', ''))
        text_content = self._safe_decode_content(getattr(raw_result, 'cleaned_html', ''))
        markdown_content = self._safe_decode_content(getattr(raw_result, 'markdown', ''))
        extracted_content = self._safe_decode_content(getattr(raw_result, 'extracted_content', ''))
        
        return {
            "success": True,
            "url": url,
            "content": {
                "html": html_content,
                "text": text_content,
                "markdown": markdown_content,
                "extracted": extracted_content
            },
            "metadata": {
                "status_code": getattr(raw_result, 'status_code', 200),
                "response_headers": getattr(raw_result, 'response_headers', {}),
                "links": self._extract_links_from_result(raw_result),
                "media": getattr(raw_result, 'media', []),
                "extracted_metadata": getattr(raw_result, 'metadata', {})
            },
            "timestamp": datetime.utcnow().isoformat()
        }


class StorageLayer:
    """Handles storage operations."""
    
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
    
    async def store(self, result: Dict[str, Any]) -> str:
        """Store crawl result."""
        return await self.storage_manager.store_scrape_result(result)


class CrawlEngine:
    """Core engine for crawling operations using crawl4ai."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        self.storage_manager = get_storage_manager()
        self._session_service = None
        self._crawler: Optional[AsyncWebCrawler] = None
        
        # Refactored components
        self._crawler_pool = None
        self._config_builder = None
        self._error_handler = None
        self._resource_manager = None
        self._performance_monitor = None
        self._async_semaphore = None
        self._batch_processor = None
        
        # Initialize layers immediately for better maintainability
        self._validation_layer = ValidationLayer()
        self._execution_layer = ExecutionLayer(None)  # Will be updated in _initialize_engine_components
        self._processing_layer = ProcessingLayer()
        self._storage_layer = StorageLayer(self.storage_manager)
        
        # Check if crawl4ai is available
        if AsyncWebCrawler is None:
            self.logger.warning("crawl4ai not available - some functionality will be limited")
    
    @property
    def session_service(self):
        """Lazy import of session service to avoid circular imports."""
        if self._session_service is None:
            from ..services.session import get_session_service
            self._session_service = get_session_service()
        return self._session_service
    
    async def initialize(self) -> None:
        """Initialize the crawl engine."""
        try:
            if AsyncWebCrawler is None:
                raise ConfigurationError("crawl4ai library not available")
            
            # Initialize storage manager
            await self.storage_manager.initialize()
            
            # Initialize session service
            await self.session_service.initialize()
            
            # Initialize engine components and layers
            await self._initialize_engine_components()
            
            self.logger.info("Crawl engine initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize crawl engine: {e}"
            self.logger.error(error_msg)
            handle_error(ConfigurationError(error_msg))
            raise
    
    async def _initialize_engine_components(self):
        """Initialize the engine components and layers."""
        # Initialize crawler pool
        max_pool_size = self.config_manager.get_setting("engine.crawler_pool_size", 5)
        self._crawler_pool = CrawlerPool(max_pool_size)
        
        # Initialize configuration builder
        self._config_builder = ConfigBuilder(self.config_manager)
        
        # Initialize error handler
        self._error_handler = ErrorHandler(self.logger)
        
        # Add error handler methods to engine for direct access
        self._handle_network_error = self._error_handler._handle_network_error
        self._handle_timeout_error = self._error_handler._handle_timeout_error
        self._handle_extraction_error = self._error_handler._handle_extraction_error
        
        # Initialize resource manager
        self._resource_manager = ResourceManager()
        
        # Initialize performance monitor
        self._performance_monitor = PerformanceMonitor()
        
        # Initialize async semaphore for concurrency control
        max_concurrent = self.config_manager.get_setting("engine.max_concurrent_requests", 10)
        self._async_semaphore = asyncio.Semaphore(max_concurrent)
        
        # Initialize batch processor
        self._batch_processor = BatchProcessor(self)
        
        # Initialize parallel executor
        self._parallel_executor = ParallelExecutor(self._async_semaphore)
        
        # Initialize execution layer (others already initialized in __init__)
        self._execution_layer = ExecutionLayer(self._crawler_pool)
    
    # Refactored helper methods
    async def _check_cache(self, url: str, options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check cache for existing result."""
        if options.get("cache_enabled", True):
            cached_result = await self.storage_manager.get_cached_result(url, options)
            if cached_result:
                self.metrics.increment_counter("crawl_engine.cache_hits")
                self.logger.debug(f"Cache hit for URL: {url}")
                return cached_result
        
        self.metrics.increment_counter("crawl_engine.cache_misses")
        return None
    
    async def _prepare_scrape_request(self, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare scrape request with validation and configuration."""
        # Validate input
        self._validation_layer.validate(url, options)
        
        # Build configuration
        config = self._config_builder.build_advanced_config(**options)
        
        return {"url": url, "config": config, "options": options}
    
    async def _execute_scrape(self, request_data: Dict[str, Any], extraction_strategy: Optional[Dict[str, Any]], session_id: Optional[str]) -> Any:
        """Execute scraping operation - alias for _execute_scrape_with_retry for backward compatibility."""
        return await self._execute_scrape_with_retry(request_data, extraction_strategy, session_id)
    
    async def _execute_scrape_with_retry(self, request_data: Dict[str, Any], extraction_strategy: Optional[Dict[str, Any]], session_id: Optional[str]) -> Any:
        """Execute scraping with retry logic."""
        url = request_data["url"]
        options = request_data["options"]
        
        # Prepare browser config
        browser_config = {
            "headless": options.get("headless", True),
            "timeout": options.get("timeout", 30),
            "user_agent": options.get("user_agent"),
        }
        
        # Apply session configuration if provided
        if session_id:
            browser_config = await self._apply_session_config(browser_config, session_id)
        
        # Get crawler instance
        crawler = await self._get_crawler(browser_config)
        
        # Prepare extraction strategy
        strategy = None
        if extraction_strategy:
            strategy = self._translate_extraction_strategy(extraction_strategy)
        
        # Prepare crawl parameters
        crawl_params = {
            "url": url,
            "extraction_strategy": strategy,
            "bypass_cache": not options.get("cache_enabled", True),
            "page_timeout": options.get("timeout", 30) * 1000,
        }
        
        # Add optional parameters
        if "js_code" in options:
            crawl_params["js_code"] = options["js_code"]
        if "wait_for" in options:
            crawl_params["wait_for"] = options["wait_for"]
        
        # Execute with retry logic
        return await self._execute_with_retry(crawler, crawl_params, url, options)
    
    async def _apply_session_config(self, browser_config: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Apply session configuration to browser config."""
        session_obj = await self.get_session(session_id)
        if session_obj:
            session_config = session_obj.config
            if session_config.user_agent is not None:
                browser_config["user_agent"] = session_config.user_agent
            if session_config.timeout is not None:
                browser_config["timeout"] = session_config.timeout
            browser_config["headless"] = session_config.headless
            if session_config.proxy_url is not None:
                browser_config["proxy_url"] = session_config.proxy_url
            if session_config.proxy_username is not None:
                browser_config["proxy_username"] = session_config.proxy_username
            if session_config.proxy_password is not None:
                browser_config["proxy_password"] = session_config.proxy_password
            if session_config.viewport_width is not None:
                browser_config["viewport_width"] = session_config.viewport_width
            if session_config.viewport_height is not None:
                browser_config["viewport_height"] = session_config.viewport_height
            if session_config.extra_options:
                browser_config.update(session_config.extra_options)
        else:
            raise ConfigurationError(f"Session {session_id} not found or has been closed")
        return browser_config
    
    async def _execute_with_retry(self, crawler: AsyncWebCrawler, crawl_params: Dict[str, Any], url: str, options: Dict[str, Any]) -> Any:
        """Execute crawling with retry logic."""
        retry_count = options.get("retry_count", 1)
        retry_delay = options.get("retry_delay", 1.0)
        
        for attempt in range(retry_count):
            try:
                async with crawler:
                    timeout_seconds = options.get("timeout", 30)
                    return await asyncio.wait_for(
                        crawler.arun(**crawl_params),
                        timeout=timeout_seconds
                    )
                    
            except asyncio.TimeoutError as e:
                if attempt < retry_count - 1:
                    backoff_delay = retry_delay * (2 ** attempt)
                    self.logger.warning(f"Retrying {url} after {backoff_delay:.2f}s (attempt {attempt + 1}/{retry_count})")
                    await asyncio.sleep(backoff_delay)
                else:
                    error_msg = f"Timeout scraping {url}: {e}"
                    self.metrics.increment_counter("crawl_engine.scrapes.timeout")
                    self.logger.error(error_msg)
                    raise TimeoutError(error_msg, timeout_duration=options.get("timeout", 30))
                    
            except Exception as e:
                if attempt < retry_count - 1 and self._should_retry_error(e):
                    backoff_delay = retry_delay * (2 ** attempt)
                    self.logger.warning(f"Retrying {url} after {backoff_delay:.2f}s (attempt {attempt + 1}/{retry_count})")
                    await asyncio.sleep(backoff_delay)
                else:
                    raise self._classify_and_raise_error(e, url)
    
    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if an error should be retried."""
        # Never retry ValidationError
        if isinstance(error, ValidationError):
            return False
        
        if isinstance(error, (NetworkError, ssl.SSLError, socket.error, ConnectionError)):
            return True
        
        # Check for browser crashes (should not retry)
        error_str = str(error).lower()
        browser_crash_patterns = [
            "browser process crashed", "browser crashed", "browser process",
            "browser not responding", "browser died", "browser terminated",
            "chrome crashed", "chromium crashed", "browser connection lost"
        ]
        
        if any(pattern in error_str for pattern in browser_crash_patterns):
            return False
        
        # Check for network-related errors
        network_patterns = [
            "connection", "ssl", "tls", "certificate", "dns", "resolution",
            "timeout", "unreachable", "refused", "reset", "socket", "host",
            "name", "protocol", "verify failed", "handshake", "network",
            "http", "response", "status", "service unavailable", "bad gateway",
            "gateway", "server", "unavailable", "invalid", "malformed",
            "permanent", "always fail", "circuit breaker"
        ]
        
        return any(pattern in error_str for pattern in network_patterns)
    
    def _classify_and_raise_error(self, error: Exception, url: str) -> None:
        """Classify error and raise appropriate exception."""
        # If it's already a foundation error, raise it as-is
        if isinstance(error, (NetworkError, TimeoutError, ExtractionError, ValidationError)):
            raise error
        
        # Handle asyncio.TimeoutError specifically
        if isinstance(error, asyncio.TimeoutError):
            error_msg = f"Timeout scraping {url}: {error}"
            self.metrics.increment_counter("crawl_engine.scrapes.timeout")
            self.logger.error(error_msg)
            raise TimeoutError(error_msg, timeout_duration=30)
        
        error_str = str(error).lower()
        
        # Check for browser crashes
        browser_crash_patterns = [
            "browser process crashed", "browser crashed", "browser process",
            "browser not responding", "browser died", "browser terminated",
            "chrome crashed", "chromium crashed", "browser connection lost"
        ]
        
        if any(pattern in error_str for pattern in browser_crash_patterns):
            raise error  # Propagate browser crashes as-is
        
        # Check for network errors
        network_patterns = [
            "connection", "ssl", "tls", "certificate", "dns", "resolution",
            "timeout", "unreachable", "refused", "reset", "socket", "host",
            "name", "protocol", "verify failed", "handshake", "network",
            "http", "response", "status", "service unavailable", "bad gateway",
            "gateway", "server", "unavailable", "invalid", "malformed",
            "permanent", "always fail", "circuit breaker"
        ]
        
        if any(pattern in error_str for pattern in network_patterns):
            self.metrics.increment_counter("crawl_engine.scrapes.error")
            raise NetworkError(f"Network error scraping {url}: {error}")
        
        self.metrics.increment_counter("crawl_engine.scrapes.error")
        raise ExtractionError(f"Failed to scrape {url}: {error}")
    
    async def _process_scrape_result(self, raw_result: Any, url: str, options: Dict[str, Any], extraction_strategy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process the raw scrape result."""
        start_time = datetime.utcnow()
        
        # Check if result is valid
        if raw_result is None:
            raise NetworkError(f"Crawl failed for {url}: No result returned")
        
        # Handle failed crawl results
        if not raw_result.success:
            error_msg = f"Crawl failed for {url}: {raw_result.error_message}"
            
            # Check for redirect errors (return failed result instead of exception)
            if self._is_redirect_error(raw_result.error_message):
                return self._create_failed_result(url, error_msg, start_time, extraction_strategy, options)
            else:
                raise NetworkError(error_msg, status_code=getattr(raw_result, 'status_code', 500))
        
        # Process successful result
        end_time = datetime.utcnow()
        load_time = (end_time - start_time).total_seconds()
        
        result_data = {
            "url": url,
            "title": raw_result.metadata.get("title", "") if raw_result.metadata else "",
            "success": True,
            "status_code": getattr(raw_result, 'status_code', 200),
            "content": {
                "markdown": getattr(raw_result, 'markdown', ""),
                "html": getattr(raw_result, 'html', ""),
                "text": getattr(raw_result, 'cleaned_html', ""),
                "extracted_data": getattr(raw_result, 'extracted_content', None) if hasattr(raw_result, 'extracted_content') else None
            },
            "links": self._extract_links(raw_result),
            "images": self._extract_images(raw_result),
            "metadata": {
                "load_time": load_time,
                "timestamp": end_time.isoformat(),
                "size": len(getattr(raw_result, 'html', "") or ""),
                "extraction_strategy": extraction_strategy.get("type") if extraction_strategy else "auto"
            }
        }
        
        # Add crawl4ai metadata
        if raw_result.metadata:
            result_data["metadata"].update(raw_result.metadata)
        
        # Record metrics
        self.metrics.increment_counter("crawl_engine.scrapes.success")
        self.metrics.record_timing("crawl_engine.scrape", load_time)
        
        self.logger.info(f"Successfully scraped {url} in {load_time:.2f}s")
        return result_data
    
    def _is_redirect_error(self, error_message: str) -> bool:
        """Check if error is a redirect error."""
        if not error_message:
            return False
        
        error_msg_lower = str(error_message).lower()
        
        redirect_patterns = [
            "redirect", "loop", "circular", "maximum number of redirects",
            "too many redirects", "redirect chain", "redirect limit"
        ]
        
        network_patterns = [
            "connection", "ssl", "tls", "certificate", "dns", "resolution",
            "timeout", "unreachable", "refused", "reset", "socket", "host",
            "net::", "err_", "network", "handshake", "verify failed"
        ]
        
        return (
            any(pattern in error_msg_lower for pattern in redirect_patterns) and
            not any(pattern in error_msg_lower for pattern in network_patterns)
        )
    
    def _create_failed_result(self, url: str, error_msg: str, start_time: datetime, extraction_strategy: Optional[Dict[str, Any]], options: Dict[str, Any]) -> Dict[str, Any]:
        """Create a failed result data structure."""
        end_time = datetime.utcnow()
        load_time = (end_time - start_time).total_seconds()
        
        result_data = {
            "url": url,
            "title": "",
            "success": False,
            "error": error_msg,
            "content": {
                "text": "",
                "html": "",
                "markdown": "",
                "extracted_data": None
            },
            "links": [],
            "images": [],
            "metadata": {
                "load_time": load_time,
                "size": 0,
                "extraction_strategy": extraction_strategy.get("type", "auto") if extraction_strategy else "auto",
                "output_format": options.get("output_format", "json"),
                "url": url
            }
        }
        
        self.metrics.increment_counter("crawl_engine.scrapes.failed")
        self.logger.warning(f"Redirect error for {url}: {error_msg}")
        return result_data
    
    async def _cache_and_store_result(self, url: str, result_data: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Cache and store the result."""
        if options.get("cache_enabled", True):
            cache_ttl = options.get("cache_ttl", self.config_manager.get_setting("scrape.cache_ttl", 3600))
            await self.storage_manager.store_cached_result(url, result_data, options, cache_ttl)
    
    async def _handle_scrape_error(self, error: Exception, url: str) -> Dict[str, Any]:
        """Handle scraping errors consistently."""
        error_msg = f"Unexpected error scraping {url}: {error}"
        self.metrics.increment_counter("crawl_engine.scrapes.error")
        self.logger.error(error_msg)
        
        extraction_error = ExtractionError(error_msg)
        context = ErrorContext(operation="scrape_single", url=url)
        handle_error(extraction_error, context)
        raise extraction_error
    
    async def _validate_scrape_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize scrape options."""
        # Set defaults
        validated_options = {
            "timeout": options.get("timeout", 30),
            "headless": options.get("headless", True),
            "cache_enabled": options.get("cache_enabled", True),
            "retry_count": options.get("retry_count", 1),
        }
        
        # Validate ranges
        if validated_options["timeout"] < 1 or validated_options["timeout"] > 300:
            raise ValidationError("Timeout must be between 1 and 300 seconds")
        
        if validated_options["retry_count"] < 0 or validated_options["retry_count"] > 10:
            raise ValidationError("Retry count must be between 0 and 10")
        
        return validated_options
    
    async def _record_performance_metric(self, metric_name: str, value: float, tags: Dict[str, Any] = None):
        """Record a performance metric."""
        await self._performance_monitor.record_timing(metric_name, value, tags)
    
    async def _get_performance_metrics(self, metric_name: str) -> List[Dict[str, Any]]:
        """Get performance metrics."""
        return await self._performance_monitor.get_metrics(metric_name)
    
    async def _acquire_resource(self, resource_type: str) -> str:
        """Acquire a resource."""
        return await self._resource_manager.acquire_resource(resource_type)
    
    async def _release_resource(self, resource_id: str):
        """Release a resource."""
        await self._resource_manager.release_resource(resource_id)
    
    async def _cleanup_resources(self):
        """Clean up expired resources."""
        await self._resource_manager.cleanup_expired()
    
    async def _build_crawler_config(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Build crawler configuration."""
        return self._config_builder.build_advanced_config(**options)
    
    async def _get_crawler(
        self,
        browser_config: Optional[Dict[str, Any]] = None
    ) -> AsyncWebCrawler:
        """Get or create an AsyncWebCrawler instance.
        
        Args:
            browser_config: Browser configuration options
            
        Returns:
            AsyncWebCrawler instance
        """
        if AsyncWebCrawler is None:
            raise ConfigurationError("crawl4ai library not available")
        
        if browser_config is None:
            browser_config = {}
        
        # Get default browser settings from config
        default_config = {
            "headless": self.config_manager.get_setting("browser.headless", True),
            "user_agent": self.config_manager.get_setting("browser.user_agent", "Crawler/1.0"),
            "viewport_width": self.config_manager.get_setting("browser.viewport_width", 1920),
            "viewport_height": self.config_manager.get_setting("browser.viewport_height", 1080),
        }
        
        # Merge with provided config
        config = {**default_config, **browser_config}

        # Create new crawler instance (crawl4ai manages browser lifecycle)
        user_agent = config.get("user_agent")
        if user_agent is None:
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/116.0.0.0 Safari/537.36"
        self.logger.debug(f"Creating crawler with user_agent: {user_agent}")

        from crawl4ai.async_configs import BrowserConfig

        proxy_config = self._resolve_proxy_config(config)
        extra_args = self._resolve_extra_browser_args(config)

        browser_type = config.get(
            "browser_type",
            self.config_manager.get_setting("browser.browser_type", "chromium"),
        )
        if not browser_type:
            browser_type = "chromium"

        browser_config = BrowserConfig(
            headless=config.get("headless", True),
            browser_type=browser_type,
            user_agent=user_agent,
            viewport_width=config.get("viewport_width"),
            viewport_height=config.get("viewport_height"),
            proxy_config=proxy_config,
            extra_args=extra_args,
            verbose=self.logger.level <= 10  # DEBUG level
        )
        
        crawler = AsyncWebCrawler(
            config=browser_config
        )
        
        return crawler

    def _resolve_proxy_config(self, config: Dict[str, Any]):
        """Resolve proxy configuration for crawl4ai/Playwright.

        Priority:
        1) Explicit browser config overrides (e.g. session / options)
        2) Crawler config settings (browser.proxy_*)
        3) Standard environment variables (HTTPS_PROXY/HTTP_PROXY/ALL_PROXY)
        """
        try:
            from crawl4ai.async_configs import ProxyConfig
        except Exception:
            return None

        proxy_url = (
            config.get("proxy_url")
            or config.get("proxy")
            or self.config_manager.get_setting("browser.proxy_url")
        )

        if not proxy_url:
            proxy_url = (
                os.environ.get("HTTPS_PROXY")
                or os.environ.get("https_proxy")
                or os.environ.get("HTTP_PROXY")
                or os.environ.get("http_proxy")
                or os.environ.get("ALL_PROXY")
                or os.environ.get("all_proxy")
            )

        if not proxy_url:
            return None

        proxy_username = config.get("proxy_username") or self.config_manager.get_setting("browser.proxy_username")
        proxy_password = config.get("proxy_password") or self.config_manager.get_setting("browser.proxy_password")

        # If proxy_url contains credentials, split them out for ProxyConfig.
        try:
            parsed = urlparse(proxy_url)
            if parsed.username is not None:
                proxy_username = parsed.username
            if parsed.password is not None:
                proxy_password = parsed.password

            if parsed.scheme and parsed.hostname:
                # Rebuild proxy server URL without credentials.
                netloc = parsed.hostname
                if parsed.port:
                    netloc = f"{netloc}:{parsed.port}"
                proxy_server = f"{parsed.scheme}://{netloc}"
            else:
                proxy_server = proxy_url
        except Exception:
            proxy_server = proxy_url

        return ProxyConfig(server=proxy_server, username=proxy_username, password=proxy_password)

    def _resolve_extra_browser_args(self, config: Dict[str, Any]) -> Optional[List[str]]:
        """Resolve extra browser args (Chromium flags) from config."""
        extra_args = config.get("extra_args") or self.config_manager.get_setting("browser.extra_args")
        if extra_args is None:
            return None
        if isinstance(extra_args, list):
            return [str(arg) for arg in extra_args if str(arg).strip()]
        if isinstance(extra_args, str):
            # Keep it simple; allow users to pass a space-separated string.
            parts = [p.strip() for p in extra_args.split(" ") if p.strip()]
            return parts or None
        return None
    
    def _translate_extraction_strategy(
        self,
        strategy_config: Dict[str, Any]
    ) -> Optional[Crawl4aiStrategy]:
        """Translate our extraction strategy config to crawl4ai strategy.
        
        Args:
            strategy_config: Strategy configuration
            
        Returns:
            crawl4ai ExtractionStrategy or None
        """
        strategy_type = strategy_config.get("type", "auto")
        
        try:
            if strategy_type == "css":
                # CSS selector based extraction
                selectors = strategy_config.get("selectors", {})
                if isinstance(selectors, str):
                    # Simple selector - convert to dict format
                    selectors_dict = {"content": selectors}
                    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
                    return JsonCssExtractionStrategy(selectors_dict)
                elif isinstance(selectors, dict):
                    # Multiple selectors
                    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
                    return JsonCssExtractionStrategy(selectors)
            
            elif strategy_type == "llm":
                # LLM-based extraction
                model = strategy_config.get("model", "openai/gpt-4o-mini")
                prompt = strategy_config.get("prompt", "Extract the main content from this page")
                
                # Get API key based on provider
                provider = model.split("/")[0] if "/" in model else "openai"
                api_key = None
                
                if provider == "openai":
                    api_key = self.config_manager.get_setting("llm.openai_api_key")
                elif provider == "anthropic":
                    api_key = self.config_manager.get_setting("llm.anthropic_api_key")
                elif provider == "gemini":
                    api_key = self.config_manager.get_setting("llm.gemini_api_key")
                
                if not api_key:
                    self.logger.warning(f"No API key configured for {provider}")
                    return None
                
                from crawl4ai.extraction_strategy import LLMExtractionStrategy
                return LLMExtractionStrategy(
                    provider=provider,
                    api_token=api_key,
                    instruction=prompt
                )
            
            elif strategy_type == "json":
                # JSON schema-based extraction
                schema = strategy_config.get("schema")
                if schema:
                    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
                    return JsonCssExtractionStrategy(schema)
            
            # For "auto" or unknown strategies, return None (use default)
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to create extraction strategy: {e}")
            return None
    
    async def scrape_single(
        self,
        url: str,
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Scrape a single URL with validation, caching, and error handling."""
        if options is None:
            options = {}
        
        if self._execution_layer is None or self._config_builder is None:
            await self._initialize_engine_components()
        
        with timer("crawl_engine.scrape_single"):
            try:
                cached_result = await self._check_cache(url, options)
                if cached_result:
                    return cached_result
                
                request_data = await self._prepare_scrape_request(url, options)
                raw_result = await self._execute_scrape_with_retry(
                    request_data, extraction_strategy, session_id
                )
                result_data = await self._process_scrape_result(raw_result, url, options, extraction_strategy)
                await self._cache_and_store_result(url, result_data, options)
                return result_data
                
            except (TimeoutError, NetworkError, ExtractionError, ValidationError):
                raise
            except Exception as e:
                return await self._handle_scrape_error(e, url)
    
    def _extract_links(self, crawl_result) -> List[Dict[str, Any]]:
        """Extract links from crawl result.
        
        Args:
            crawl_result: crawl4ai CrawlResult
            
        Returns:
            List of link dictionaries
        """
        links = []
        
        try:
            if hasattr(crawl_result, 'links') and crawl_result.links:
                # Handle crawl4ai's dictionary structure: {'internal': [...], 'external': [...]}
                if isinstance(crawl_result.links, dict):
                    # Process internal links
                    internal_links = crawl_result.links.get('internal', [])
                    for link in internal_links:
                        if isinstance(link, dict):
                            links.append({
                                "url": link.get("href", ""),
                                "text": link.get("text", ""),
                                "type": "internal"
                            })
                        elif isinstance(link, str):
                            links.append({
                                "url": link,
                                "text": "",
                                "type": "internal"
                            })
                    
                    # Process external links
                    external_links = crawl_result.links.get('external', [])
                    for link in external_links:
                        if isinstance(link, dict):
                            links.append({
                                "url": link.get("href", ""),
                                "text": link.get("text", ""),
                                "type": "external"
                            })
                        elif isinstance(link, str):
                            links.append({
                                "url": link,
                                "text": "",
                                "type": "external"
                            })
                
                # Handle older format where links might be a list
                elif isinstance(crawl_result.links, list):
                    for link in crawl_result.links:
                        if isinstance(link, dict):
                            links.append({
                                "url": link.get("href", ""),
                                "text": link.get("text", ""),
                                "type": self._classify_link_type(link.get("href", ""), getattr(crawl_result, 'url', ""))
                            })
                        elif isinstance(link, str):
                            links.append({
                                "url": link,
                                "text": "",
                                "type": self._classify_link_type(link, getattr(crawl_result, 'url', ""))
                            })
            
        except Exception as e:
            self.logger.warning(f"Failed to extract links: {e}")
        
        return links
    
    def _extract_images(self, crawl_result) -> List[Dict[str, Any]]:
        """Extract images from crawl result.
        
        Args:
            crawl_result: crawl4ai CrawlResult
            
        Returns:
            List of image dictionaries
        """
        images = []
        
        try:
            if hasattr(crawl_result, 'media') and crawl_result.media:
                for media in crawl_result.media:
                    if isinstance(media, dict) and media.get("type") == "image":
                        images.append({
                            "src": media.get("src", ""),
                            "alt": media.get("alt", ""),
                            "width": media.get("width"),
                            "height": media.get("height"),
                            "type": "image"
                        })
            
        except Exception as e:
            self.logger.warning(f"Failed to extract images: {e}")
        
        return images
    
    def _classify_link_type(self, link_url: str, base_url: str) -> str:
        """Classify a link as internal, external, etc.
        
        Args:
            link_url: The link URL
            base_url: The base page URL
            
        Returns:
            Link type string
        """
        try:
            if not link_url or not isinstance(link_url, str):
                return "unknown"
            
            if not base_url or not isinstance(base_url, str):
                return "unknown"
            
            # Parse URLs
            link_parsed = urlparse(link_url)
            base_parsed = urlparse(base_url)
            
            # Check if base URL is valid (has scheme and netloc)
            if not base_parsed.scheme or not base_parsed.netloc:
                return "unknown"
            
            # Handle relative URLs
            if not link_parsed.netloc:
                return "internal"
            
            # Compare domains (ensure netloc attributes are strings)
            if (link_parsed.netloc and base_parsed.netloc and 
                isinstance(link_parsed.netloc, str) and isinstance(base_parsed.netloc, str)):
                if link_parsed.netloc == base_parsed.netloc:
                    return "internal"
                elif link_parsed.netloc.endswith(f".{base_parsed.netloc}"):
                    return "subdomain"
                else:
                    return "external"
            
            return "unknown"
                
        except Exception:
            return "unknown"
    
    async def scrape_batch(
        self,
        urls: List[str],
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently.
        
        Args:
            urls: List of URLs to scrape
            options: Scraping options
            extraction_strategy: Content extraction strategy
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of scraping results
        """
        if options is None:
            options = {}
        
        # Limit concurrency to prevent overwhelming the system
        max_concurrent = min(max_concurrent, self.config_manager.get_setting("crawl.concurrent_requests", 5))
        
        with timer("crawl_engine.scrape_batch"):
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def scrape_with_semaphore(url: str) -> Dict[str, Any]:
                async with semaphore:
                    try:
                        return await self.scrape_single(url, options, extraction_strategy)
                    except Exception as e:
                        # Return error result instead of raising
                        return {
                            "url": url,
                            "success": False,
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat()
                        }
            
            # Execute all scrapes concurrently
            tasks = [scrape_with_semaphore(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=False)
            
            # Calculate statistics
            successful = len([r for r in results if r.get("success", False)])
            failed = len(results) - successful
            
            self.metrics.record_metric("crawl_engine.batch.total", len(results))
            self.metrics.record_metric("crawl_engine.batch.successful", successful)
            self.metrics.record_metric("crawl_engine.batch.failed", failed)
            
            self.logger.info(f"Batch scrape completed: {successful}/{len(results)} successful")
            
            return results
    
    async def extract_links_from_page(
        self,
        url: str,
        options: Optional[Dict[str, Any]] = None,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> List[str]:
        """Extract links from a page for crawling.
        
        Args:
            url: URL to extract links from
            options: Scraping options
            include_patterns: Regex patterns for URLs to include
            exclude_patterns: Regex patterns for URLs to exclude
            
        Returns:
            List of discovered URLs
        """
        import re
        
        try:
            # Scrape the page
            result = await self.scrape_single(url, options)
            
            if not result.get("success"):
                return []
            
            # Extract links
            links = result.get("links", [])
            discovered_urls = []
            
            for link in links:
                link_url = link.get("url", "")
                if not link_url:
                    continue
                
                # Convert relative URLs to absolute
                if not link_url.startswith(("http://", "https://")):
                    link_url = urljoin(url, link_url)
                
                # Apply include patterns
                if include_patterns:
                    if not any(re.search(pattern, link_url) for pattern in include_patterns):
                        continue
                
                # Apply exclude patterns
                if exclude_patterns:
                    if any(re.search(pattern, link_url) for pattern in exclude_patterns):
                        continue
                
                discovered_urls.append(link_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in discovered_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            self.metrics.record_metric("crawl_engine.links_discovered", len(unique_urls))
            self.logger.debug(f"Discovered {len(unique_urls)} unique links from {url}")
            
            return unique_urls
            
        except Exception as e:
            self.logger.error(f"Failed to extract links from {url}: {e}")
            return []
    
    async def create_session(
        self,
        session_config: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ) -> str:
        """Create a new browser session.
        
        Args:
            session_config: Session configuration dict
            session_id: Optional custom session ID
            timeout_seconds: Session timeout in seconds
            
        Returns:
            Session ID
        """
        from ..services.session import SessionConfig
        
        # Convert dict to SessionConfig if needed
        config = None
        if session_config is not None:
            if isinstance(session_config, dict):
                config = SessionConfig.from_dict(session_config)
            else:
                config = session_config
        
        return await self.session_service.create_session(
            session_config=config,
            session_id=session_id,
            timeout_seconds=timeout_seconds
        )
    
    async def close_session(self, session_id: str) -> bool:
        """Close a browser session.
        
        Args:
            session_id: Session ID to close
            
        Returns:
            True if session was closed successfully
        """
        return await self.session_service.close_session(session_id)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session info or None if not found
        """
        return await self.session_service.get_session(session_id)
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions.
        
        Returns:
            List of session info dictionaries
        """
        return await self.session_service.list_sessions()
    
    async def close(self) -> None:
        """Clean up resources."""
        try:
            if self._crawler:
                await self._crawler.close()
                self._crawler = None
            self.logger.info("Crawl engine closed")
        except Exception as e:
            self.logger.error(f"Error closing crawl engine: {e}")


# Global crawl engine instance
_crawl_engine: Optional[CrawlEngine] = None


def get_crawl_engine() -> CrawlEngine:
    """Get the global crawl engine instance."""
    global _crawl_engine
    if _crawl_engine is None:
        _crawl_engine = CrawlEngine()
    return _crawl_engine


def reset_crawl_engine() -> None:
    """Reset the global crawl engine instance."""
    global _crawl_engine
    _crawl_engine = None
