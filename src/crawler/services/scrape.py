"""Service for handling single-page scraping operations."""

import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path

from ..core import get_crawl_engine, get_storage_manager, get_job_manager
from ..database.models.jobs import JobType
from ..foundation.config import get_config_manager
from ..foundation.logging import get_logger
from ..foundation.errors import (
    handle_error, ValidationError, NetworkError, ExtractionError, ErrorContext
)
from ..foundation.metrics import get_metrics_collector, timer


class ScrapeService:
    """Service for handling single-page scraping operations."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        self.crawl_engine = get_crawl_engine()
        self.storage_manager = get_storage_manager()
        self.job_manager = get_job_manager()
    
    async def initialize(self) -> None:
        """Initialize the scrape service."""
        try:
            # Initialize dependencies
            await self.storage_manager.initialize()
            await self.crawl_engine.initialize()
            await self.job_manager.initialize()
            
            # Register job handler
            self.job_manager.register_handler(JobType.SCRAPE_SINGLE, self._handle_scrape_job)
            self.job_manager.register_handler(JobType.SCRAPE_BATCH, self._handle_batch_scrape_job)
            
            self.logger.info("Scrape service initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize scrape service: {e}"
            self.logger.error(error_msg)
            handle_error(ValidationError(error_msg))
            raise
    
    async def scrape_single(
        self,
        url: str,
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        output_format: str = "markdown",
        session_id: Optional[str] = None,
        store_result: bool = True
    ) -> Dict[str, Any]:
        """Scrape a single URL synchronously.
        
        Args:
            url: URL to scrape
            options: Scraping options (timeout, headless, etc.)
            extraction_strategy: Content extraction configuration
            output_format: Output format (markdown, json, html, text)
            session_id: Optional session ID for browser reuse
            store_result: Whether to store the result in database
            
        Returns:
            Scraping result
        """
        if options is None:
            options = {}
        
        context = ErrorContext(
            operation="scrape_single",
            url=url,
            session_id=session_id
        )
        
        with timer("scrape_service.scrape_single"):
            # Validate URL - handle validation errors gracefully
            try:
                self._validate_url(url)
            except ValidationError as e:
                # Return error result for invalid URLs
                self.metrics.increment_counter("scrape_service.scrapes.failed")
                error_msg = f"Invalid URL {url}: {str(e)}"
                self.logger.error(error_msg)
                handle_error(e, context)
                
                return {
                    "success": False,
                    "url": url,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Merge with default options
            scrape_options = self._get_default_scrape_options()
            scrape_options.update(options)
            
            # Get retry configuration
            retry_attempts = scrape_options.get("retry_attempts", scrape_options.get("retry_count", 3))
            retry_delay = scrape_options.get("retry_delay", 1.0)
            
            last_error = None
            
            # Retry loop
            for attempt in range(retry_attempts):
                try:
                    # Execute scraping using crawl engine
                    result = await self.crawl_engine.scrape_single(
                        url=url,
                        options=scrape_options,
                        extraction_strategy=extraction_strategy,
                        session_id=session_id
                    )
                    
                    # Apply output format transformation
                    formatted_result = self._format_result(result, output_format)
                    
                    # For service layer, extract content based on output format if not JSON
                    if output_format != "json":
                        content = formatted_result.get("content", {})
                        if isinstance(content, dict):
                            if output_format == "markdown":
                                formatted_result["content"] = content.get("markdown", "")
                            elif output_format == "html":
                                formatted_result["content"] = content.get("html", "")
                            elif output_format == "text":
                                formatted_result["content"] = content.get("text", "")
                            else:
                                formatted_result["content"] = content.get("markdown", "")
                    
                    # Ensure the URL in the result matches the actual URL being scraped
                    formatted_result["url"] = url
                    
                    # Store result if requested
                    if store_result:
                        await self._store_scrape_result(formatted_result)
                    
                    # Update metrics
                    self.metrics.increment_counter("scrape_service.scrapes.completed")
                    self.metrics.record_timing(
                        "scrape_service.scrape_duration",
                        formatted_result.get("metadata", {}).get("load_time", 0)
                    )
                    
                    if attempt > 0:
                        self.logger.info(f"Successfully scraped {url} on attempt {attempt + 1}")
                    else:
                        self.logger.info(f"Successfully scraped {url}")
                    return formatted_result
                    
                except (NetworkError, ExtractionError) as e:
                    last_error = e
                    if attempt < retry_attempts - 1:
                        # Calculate exponential backoff delay
                        backoff_delay = retry_delay * (2 ** attempt)
                        # Wait before retrying
                        await asyncio.sleep(backoff_delay)
                        self.logger.warning(f"Scrape attempt {attempt + 1} failed for {url}: {e}. Retrying after {backoff_delay:.2f}s...")
                        continue
                    else:
                        # Final attempt failed
                        break
                        
                except Exception as e:
                    # Non-retryable error
                    last_error = e
                    break
            
            # All attempts failed
            self.metrics.increment_counter("scrape_service.scrapes.failed")
            error_msg = f"Failed to scrape {url}: {last_error}"
            self.logger.error(error_msg)
            handle_error(last_error, context)
            
            # Return error result instead of raising
            return {
                "success": False,
                "url": url,
                "error": str(last_error),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def scrape_single_async(
        self,
        url: str,
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        output_format: str = "markdown",
        session_id: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """Scrape a single URL asynchronously via job queue.
        
        Args:
            url: URL to scrape
            options: Scraping options
            extraction_strategy: Content extraction configuration
            output_format: Output format
            session_id: Optional session ID
            priority: Job priority
            
        Returns:
            Job ID for tracking the operation
        """
        try:
            # Validate URL
            self._validate_url(url)
            
            # Prepare job data
            job_data = {
                "url": url,
                "options": options or {},
                "extraction_strategy": extraction_strategy,
                "output_format": output_format,
                "session_id": session_id
            }
            
            # Submit job
            job_id = await self.job_manager.submit_job(
                job_type=JobType.SCRAPE_SINGLE,
                job_data=job_data,
                priority=priority
            )
            
            self.metrics.increment_counter("scrape_service.async_jobs.submitted")
            self.logger.info(f"Submitted async scrape job {job_id} for {url}")
            
            return job_id
            
        except Exception as e:
            error_msg = f"Failed to submit async scrape job for {url}: {e}"
            self.logger.error(error_msg)
            handle_error(ValidationError(error_msg))
            raise
    
    async def scrape_batch(
        self,
        urls: List[str],
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        output_format: str = "markdown",
        max_concurrent: int = 5,
        concurrent_requests: Optional[int] = None,
        store_results: bool = True,
        continue_on_error: bool = True,
        delay: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently.
        
        Args:
            urls: List of URLs to scrape
            options: Scraping options
            extraction_strategy: Content extraction configuration
            output_format: Output format
            max_concurrent: Maximum concurrent requests
            store_results: Whether to store results in database
            
        Returns:
            List of scraping results
        """
        if options is None:
            options = {}
        
        with timer("scrape_service.scrape_batch"):
            try:
                # Validate URLs
                valid_urls = []
                for url in urls:
                    try:
                        self._validate_url(url)
                        valid_urls.append(url)
                    except ValidationError as e:
                        self.logger.warning(f"Skipping invalid URL {url}: {e}")
                
                if not valid_urls:
                    raise ValidationError("No valid URLs provided")
                
                # Use concurrent_requests if provided, otherwise max_concurrent
                actual_concurrent = concurrent_requests if concurrent_requests is not None else max_concurrent
                
                # Merge with default options
                scrape_options = self._get_default_scrape_options()
                scrape_options.update(options)
                
                # Execute batch scraping using individual scrape_single calls
                results = []
                semaphore = asyncio.Semaphore(actual_concurrent)
                
                async def scrape_with_semaphore(url):
                    async with semaphore:
                        if delay > 0:
                            await asyncio.sleep(delay)
                        
                        result = await self.scrape_single(
                            url=url,
                            options=scrape_options,
                            extraction_strategy=extraction_strategy,
                            output_format=output_format,
                            store_result=False  # We'll handle storage below
                        )
                        
                        # If continue_on_error is False and we got an error result, raise exception
                        if not continue_on_error and not result.get("success", False):
                            from ..foundation.errors import NetworkError
                            raise NetworkError(result.get("error", "Unknown error"))
                        
                        return result
                
                # Execute all scraping tasks
                tasks = [scrape_with_semaphore(url) for url in valid_urls]
                if continue_on_error:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    results = await asyncio.gather(*tasks, return_exceptions=False)
                
                # Format results
                formatted_results = []
                for result in results:
                    try:
                        formatted_result = self._format_result(result, output_format)
                        formatted_results.append(formatted_result)
                        
                        # Store result if requested and successful
                        if store_results and formatted_result.get("success"):
                            await self._store_scrape_result(formatted_result)
                            
                    except Exception as e:
                        self.logger.error(f"Failed to format result for {result.get('url', 'unknown')}: {e}")
                        # Add error result
                        formatted_results.append({
                            "url": result.get("url", "unknown"),
                            "success": False,
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                # Update metrics
                successful = len([r for r in formatted_results if r.get("success")])
                failed = len(formatted_results) - successful
                
                self.metrics.record_metric("scrape_service.batch.total", len(formatted_results))
                self.metrics.record_metric("scrape_service.batch.successful", successful)
                self.metrics.record_metric("scrape_service.batch.failed", failed)
                
                self.logger.info(f"Batch scrape completed: {successful}/{len(formatted_results)} successful")
                return formatted_results
                
            except Exception as e:
                self.metrics.increment_counter("scrape_service.batch.errors")
                error_msg = f"Batch scrape failed: {e}"
                self.logger.error(error_msg)
                handle_error(e)
                raise
    
    async def scrape_batch_async(
        self,
        urls: List[str],
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        output_format: str = "markdown",
        max_concurrent: int = 5,
        concurrent_requests: Optional[int] = None,
        priority: int = 0
    ) -> str:
        """Scrape multiple URLs asynchronously via job queue.
        
        Args:
            urls: List of URLs to scrape
            options: Scraping options
            extraction_strategy: Content extraction configuration
            output_format: Output format
            max_concurrent: Maximum concurrent requests
            priority: Job priority
            
        Returns:
            Job ID for tracking the operation
        """
        try:
            # Validate URLs
            valid_urls = []
            for url in urls:
                try:
                    self._validate_url(url)
                    valid_urls.append(url)
                except ValidationError as e:
                    self.logger.warning(f"Skipping invalid URL {url}: {e}")
            
            if not valid_urls:
                raise ValidationError("No valid URLs provided")
            
            # Use concurrent_requests if provided, otherwise max_concurrent
            actual_concurrent = concurrent_requests if concurrent_requests is not None else max_concurrent
            
            # Prepare job data
            job_data = {
                "urls": valid_urls,
                "options": options or {},
                "extraction_strategy": extraction_strategy,
                "output_format": output_format,
                "max_concurrent": actual_concurrent,
                "concurrent_requests": concurrent_requests if concurrent_requests is not None else max_concurrent
            }
            
            # Submit job
            job_id = await self.job_manager.submit_job(
                job_type=JobType.SCRAPE_BATCH,
                job_data=job_data,
                priority=priority
            )
            
            self.metrics.increment_counter("scrape_service.async_batch_jobs.submitted")
            self.logger.info(f"Submitted async batch scrape job {job_id} for {len(valid_urls)} URLs")
            
            return job_id
            
        except Exception as e:
            error_msg = f"Failed to submit async batch scrape job: {e}"
            self.logger.error(error_msg)
            handle_error(ValidationError(error_msg))
            raise
    
    def _validate_url(self, url: str) -> None:
        """Validate a URL.
        
        Args:
            url: URL to validate
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url or not isinstance(url, str):
            raise ValidationError("URL must be a non-empty string")
        
        if not url.startswith(("http://", "https://")):
            raise ValidationError("Invalid URL format: must start with http:// or https://")
        
        # Additional URL validation can be added here
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValidationError("URL must have a valid domain")
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {e}")
    
    def _get_default_scrape_options(self) -> Dict[str, Any]:
        """Get default scraping options from configuration.
        
        Returns:
            Dictionary of default options
        """
        return {
            "timeout": self.config_manager.get_setting("scrape.timeout", 30),
            "headless": self.config_manager.get_setting("scrape.headless", True),
            "retry_count": self.config_manager.get_setting("scrape.retry_count", 3),
            "retry_delay": self.config_manager.get_setting("scrape.retry_delay", 1.0),
            "cache_enabled": self.config_manager.get_setting("scrape.cache_enabled", True),
            "cache_ttl": self.config_manager.get_setting("scrape.cache_ttl", 3600),
            "user_agent": self.config_manager.get_setting("browser.user_agent", "Crawler/1.0")
        }
    
    def _format_result(
        self,
        result: Dict[str, Any],
        output_format: str
    ) -> Dict[str, Any]:
        """Format scraping result according to output format.
        
        Args:
            result: Raw scraping result
            output_format: Desired output format
            
        Returns:
            Formatted result
        """
        if not result.get("success"):
            # Return error results as-is
            return result
        
        # Start with the original result
        formatted_result = result.copy()
        
        # Extract content based on format
        content = result.get("content", {})
        
        if output_format == "json":
            # Keep structured format for JSON
            formatted_result["content"] = content
        else:
            # For other formats, preserve the original content structure
            # The service layer will extract the specific format
            formatted_result["content"] = content
        
        # Add output format to metadata
        if "metadata" not in formatted_result:
            formatted_result["metadata"] = {}
        formatted_result["metadata"]["output_format"] = output_format
        
        # Add timestamp if not present
        if "timestamp" not in formatted_result and "created_at" not in formatted_result:
            formatted_result["timestamp"] = datetime.utcnow().isoformat()
        
        return formatted_result
    
    def _prepare_options(self, user_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Prepare and merge scraping options with defaults.
        
        Args:
            user_options: User-provided options
            
        Returns:
            Merged options dictionary
        """
        # Start with default options
        options = self._get_default_scrape_options()
        
        # Update with user options if provided
        if user_options:
            options.update(user_options)
            
        return options
    
    async def _store_scrape_result(self, result: Dict[str, Any]) -> Optional[str]:
        """Store scraping result in database.
        
        Args:
            result: Scraping result to store
            
        Returns:
            Result ID if stored successfully
        """
        try:
            if not result.get("success"):
                # Don't store failed results
                return None
            
            # Extract data for storage
            content = result.get("content", {})
            
            # Determine content format
            if isinstance(content, dict):
                content_markdown = content.get("markdown")
                content_html = content.get("html")
                content_text = content.get("text")
                extracted_data = content.get("extracted_data")
            else:
                # Simple string content
                output_format = result.get("metadata", {}).get("output_format", "markdown")
                if output_format == "markdown":
                    content_markdown = content
                    content_html = None
                    content_text = None
                elif output_format == "html":
                    content_markdown = None
                    content_html = content
                    content_text = None
                else:
                    content_markdown = None
                    content_html = None
                    content_text = content
                extracted_data = None
            
            # Store in database
            result_id = await self.storage_manager.store_crawl_result(
                url_or_data=result.get("url", ""),
                content_markdown=content_markdown,
                content_html=content_html,
                content_text=content_text,
                extracted_data=extracted_data,
                metadata=result.get("metadata"),
                title=result.get("title"),
                success=result.get("success", False),
                status_code=result.get("status_code"),
                links=result.get("links"),
                media=result.get("images")  # Map images to media
            )
            
            self.metrics.increment_counter("scrape_service.results.stored")
            return result_id
            
        except Exception as e:
            self.logger.error(f"Failed to store scrape result: {e}")
            return None
    
    # Job handlers for async processing
    
    async def _handle_scrape_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle single scrape job.
        
        Args:
            job_data: Job parameters
            
        Returns:
            Job result
        """
        try:
            result = await self.scrape_single(
                url=job_data["url"],
                options=job_data.get("options"),
                extraction_strategy=job_data.get("extraction_strategy"),
                output_format=job_data.get("output_format", "markdown"),
                session_id=job_data.get("session_id"),
                store_result=True
            )
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_batch_scrape_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch scrape job.
        
        Args:
            job_data: Job parameters
            
        Returns:
            Job result
        """
        try:
            results = await self.scrape_batch(
                urls=job_data["urls"],
                options=job_data.get("options"),
                extraction_strategy=job_data.get("extraction_strategy"),
                output_format=job_data.get("output_format", "markdown"),
                max_concurrent=job_data.get("max_concurrent", 5),
                store_results=True
            )
            
            successful = len([r for r in results if r.get("success")])
            
            return {
                "success": True,
                "results": results,
                "total": len(results),
                "successful": successful,
                "failed": len(results) - successful
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Global scrape service instance
_scrape_service: Optional[ScrapeService] = None


def get_scrape_service() -> ScrapeService:
    """Get the global scrape service instance."""
    global _scrape_service
    if _scrape_service is None:
        _scrape_service = ScrapeService()
    return _scrape_service


def reset_scrape_service() -> None:
    """Reset the global scrape service instance."""
    global _scrape_service
    _scrape_service = None