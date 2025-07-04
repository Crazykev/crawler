"""Core crawling engine that integrates with crawl4ai."""

import asyncio
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse
from datetime import datetime

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
    ConfigurationError, ErrorContext
)
from ..foundation.metrics import get_metrics_collector, timer
from .storage import get_storage_manager


class CrawlEngine:
    """Core engine for crawling operations using crawl4ai."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        self.storage_manager = get_storage_manager()
        self._crawler: Optional[AsyncWebCrawler] = None
        
        # Check if crawl4ai is available
        if AsyncWebCrawler is None:
            self.logger.warning("crawl4ai not available - some functionality will be limited")
    
    async def initialize(self) -> None:
        """Initialize the crawl engine."""
        try:
            if AsyncWebCrawler is None:
                raise ConfigurationError("crawl4ai library not available")
            
            # Initialize storage manager
            await self.storage_manager.initialize()
            
            self.logger.info("Crawl engine initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize crawl engine: {e}"
            self.logger.error(error_msg)
            handle_error(ConfigurationError(error_msg))
            raise
    
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
        crawler = AsyncWebCrawler(
            headless=config.get("headless", True),
            browser_type="chromium",  # Default to Chromium
            user_agent=config.get("user_agent"),
            viewport_width=config.get("viewport_width"),
            viewport_height=config.get("viewport_height"),
            verbose=self.logger.level <= 10  # DEBUG level
        )
        
        return crawler
    
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
        """Scrape a single URL.
        
        Args:
            url: URL to scrape
            options: Scraping options
            extraction_strategy: Content extraction strategy
            session_id: Optional session ID for persistence
            
        Returns:
            Scraping result data
        """
        if options is None:
            options = {}
        
        context = ErrorContext(
            operation="scrape_single",
            url=url,
            session_id=session_id
        )
        
        with timer("crawl_engine.scrape_single"):
            start_time = datetime.utcnow()
            crawl_result = None
            
            try:
                # Check cache first if enabled
                if options.get("cache_enabled", True):
                    cached_result = await self.storage_manager.get_cached_result(url, options)
                    if cached_result:
                        self.metrics.increment_counter("crawl_engine.cache_hits")
                        self.logger.debug(f"Cache hit for URL: {url}")
                        return cached_result
                
                self.metrics.increment_counter("crawl_engine.cache_misses")
                
                # Prepare browser config
                browser_config = {
                    "headless": options.get("headless", True),
                    "timeout": options.get("timeout", 30),
                    "user_agent": options.get("user_agent"),
                }
                
                # Get crawler instance
                crawler = await self._get_crawler(browser_config)
                
                # Prepare extraction strategy
                strategy = None
                if extraction_strategy:
                    strategy = self._translate_extraction_strategy(extraction_strategy)
                
                # Prepare crawl4ai parameters
                crawl_params = {
                    "url": url,
                    "extraction_strategy": strategy,
                    "bypass_cache": not options.get("cache_enabled", True),
                    "page_timeout": options.get("timeout", 30) * 1000,  # Convert to ms
                }
                
                # Add JavaScript execution if specified
                if "js_code" in options:
                    crawl_params["js_code"] = options["js_code"]
                
                # Add wait conditions
                if "wait_for" in options:
                    crawl_params["wait_for"] = options["wait_for"]
                
                # Execute the crawl
                self.logger.debug(f"Starting crawl for URL: {url}")
                
                try:
                    async with crawler:
                        crawl_result = await crawler.arun(**crawl_params)
                except asyncio.TimeoutError as e:
                    error_msg = f"Timeout scraping {url}: {e}"
                    self.metrics.increment_counter("crawl_engine.scrapes.timeout")
                    self.logger.error(error_msg)
                    timeout_error = TimeoutError(error_msg, timeout_duration=options.get("timeout", 30))
                    handle_error(timeout_error, context)
                    raise timeout_error
                except Exception as e:
                    error_msg = f"Failed to scrape {url}: {e}"
                    self.metrics.increment_counter("crawl_engine.scrapes.error")
                    self.logger.error(error_msg)
                    
                    if "connection" in str(e).lower():
                        network_error = NetworkError(error_msg)
                        handle_error(network_error, context)
                        raise network_error
                    else:
                        extraction_error = ExtractionError(error_msg)
                        handle_error(extraction_error, context)
                        raise extraction_error
                
                # Process the result
                if crawl_result is None:
                    error_msg = f"Crawl failed for {url}: No result returned"
                    raise NetworkError(error_msg)
                
                if not crawl_result.success:
                    error_msg = f"Crawl failed for {url}: {crawl_result.error_message}"
                    raise NetworkError(error_msg, status_code=crawl_result.status_code)
                
                # Extract content and metadata
                end_time = datetime.utcnow()
                load_time = (end_time - start_time).total_seconds()
                
                result_data = {
                    "url": url,
                    "title": crawl_result.metadata.get("title", "") if crawl_result.metadata else "",
                    "success": True,
                    "status_code": crawl_result.status_code,
                    "content": {
                        "markdown": crawl_result.markdown,
                        "html": crawl_result.html,
                        "text": crawl_result.cleaned_html,
                        "extracted_data": crawl_result.extracted_content if hasattr(crawl_result, 'extracted_content') else None
                    },
                    "links": self._extract_links(crawl_result),
                    "images": self._extract_images(crawl_result),
                    "metadata": {
                        "load_time": load_time,
                        "timestamp": end_time.isoformat(),
                        "size": len(crawl_result.html) if crawl_result.html else 0,
                        "extraction_strategy": extraction_strategy.get("type") if extraction_strategy else "auto"
                    }
                }
                
                # Add any crawl4ai metadata
                if crawl_result.metadata:
                    result_data["metadata"].update(crawl_result.metadata)
                
                # Store in cache if enabled
                if options.get("cache_enabled", True):
                    cache_ttl = options.get("cache_ttl", self.config_manager.get_setting("scrape.cache_ttl", 3600))
                    await self.storage_manager.store_cached_result(url, result_data, options, cache_ttl)
                
                # Record metrics
                self.metrics.increment_counter("crawl_engine.scrapes.success")
                self.metrics.record_timing("crawl_engine.scrape", load_time)
                
                self.logger.info(f"Successfully scraped {url} in {load_time:.2f}s")
                return result_data
                
            except (TimeoutError, NetworkError, ExtractionError):
                # Re-raise our custom errors
                raise
            except Exception as e:
                # Handle any other unexpected exceptions
                error_msg = f"Unexpected error scraping {url}: {e}"
                self.metrics.increment_counter("crawl_engine.scrapes.error")
                self.logger.error(error_msg)
                extraction_error = ExtractionError(error_msg)
                handle_error(extraction_error, context)
                raise extraction_error
    
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
                for link in crawl_result.links:
                    if isinstance(link, dict):
                        links.append({
                            "url": link.get("href", ""),
                            "text": link.get("text", ""),
                            "type": self._classify_link_type(link.get("href", ""), crawl_result.url)
                        })
                    elif isinstance(link, str):
                        links.append({
                            "url": link,
                            "text": "",
                            "type": self._classify_link_type(link, crawl_result.url)
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
            if not link_url:
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
            
            # Compare domains
            if link_parsed.netloc == base_parsed.netloc:
                return "internal"
            elif link_parsed.netloc.endswith(f".{base_parsed.netloc}"):
                return "subdomain"
            else:
                return "external"
                
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