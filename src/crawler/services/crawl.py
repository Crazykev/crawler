"""Service for handling multi-page crawling operations."""

import asyncio
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
from dataclasses import dataclass, field

from ..core import get_crawl_engine, get_storage_manager, get_job_manager
from ..database.models.jobs import JobType
from ..foundation.config import get_config_manager
from ..foundation.logging import get_logger
from ..foundation.errors import (
    handle_error, ValidationError, NetworkError, ExtractionError, ErrorContext
)
from ..foundation.metrics import get_metrics_collector, timer
from .scrape import get_scrape_service


@dataclass
class CrawlRule:
    """Configuration for crawling rules."""
    max_depth: int = 3
    max_pages: int = 100
    max_duration: int = 3600  # seconds
    delay: float = 1.0
    concurrent_requests: int = 5
    respect_robots: bool = True
    allow_external_links: bool = False
    allow_subdomains: bool = True
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)


@dataclass
class CrawlState:
    """Represents the current state of a crawl operation."""
    crawl_id: str
    start_url: str
    start_time: datetime
    current_depth: int = 0
    pages_crawled: int = 0
    pages_successful: int = 0
    pages_failed: int = 0
    urls_discovered: int = 0
    urls_queued: int = 0
    status: str = "running"  # running, completed, failed, cancelled
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert crawl state to dictionary."""
        return {
            "crawl_id": self.crawl_id,
            "start_url": self.start_url,
            "start_time": self.start_time.isoformat(),
            "current_depth": self.current_depth,
            "pages_crawled": self.pages_crawled,
            "pages_successful": self.pages_successful,
            "pages_failed": self.pages_failed,
            "urls_discovered": self.urls_discovered,
            "urls_queued": self.urls_queued,
            "status": self.status,
            "error_message": self.error_message,
            "success_rate": self.pages_successful / max(self.pages_crawled, 1),
            "elapsed_time": (datetime.utcnow() - self.start_time).total_seconds()
        }


class CrawlService:
    """Service for handling multi-page crawling operations."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        self.crawl_engine = get_crawl_engine()
        self.storage_manager = get_storage_manager()
        self.job_manager = get_job_manager()
        self.scrape_service = get_scrape_service()
        
        # Active crawl tracking
        self._active_crawls: Dict[str, CrawlState] = {}
        self._crawl_queues: Dict[str, deque] = {}
        self._crawl_visited: Dict[str, Set[str]] = {}
        self._crawl_tasks: Dict[str, List[asyncio.Task]] = {}
    
    async def initialize(self) -> None:
        """Initialize the crawl service."""
        try:
            # Initialize dependencies
            await self.scrape_service.initialize()
            
            # Register job handler
            self.job_manager.register_handler(JobType.CRAWL_SITE, self._handle_crawl_job)
            
            self.logger.info("Crawl service initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize crawl service: {e}"
            self.logger.error(error_msg)
            handle_error(ValidationError(error_msg))
            raise

    async def shutdown(self) -> None:
        """Shutdown the crawl service and clean up resources."""
        for crawl_id, crawl_state in list(self._active_crawls.items()):
            if crawl_state.status == "running":
                await self.cancel_crawl(crawl_id)

        if hasattr(self.scrape_service, "shutdown"):
            await self.scrape_service.shutdown()
        elif hasattr(self.scrape_service, "close"):
            await self.scrape_service.close()

    async def close(self) -> None:
        """Alias for shutdown()."""
        await self.shutdown()
    
    async def start_crawl(
        self,
        start_url: str,
        crawl_rules: Optional[CrawlRule] = None,
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        output_format: str = "markdown",
        session_id: Optional[str] = None,
        store_results: bool = True
    ) -> str:
        """Start a new crawling operation.
        
        Args:
            start_url: Starting URL for the crawl
            crawl_rules: Crawling rules and limits
            options: Scraping options for each page
            extraction_strategy: Content extraction configuration
            output_format: Output format for scraped content
            session_id: Optional session ID for browser reuse
            store_results: Whether to store results in database
            
        Returns:
            Crawl ID for tracking the operation
        """
        if crawl_rules is None:
            crawl_rules = self._get_default_crawl_rules()
        
        if options is None:
            options = {}
        
        crawl_id = str(uuid.uuid4())
        
        context = ErrorContext(
            operation="start_crawl",
            url=start_url,
            session_id=session_id,
            metadata={"crawl_id": crawl_id}
        )
        
        with timer("crawl_service.start_crawl"):
            try:
                # Validate start URL
                self._validate_url(start_url)

                # Normalize for crawl/dedupe (e.g., strip #fragments)
                crawl_start_url = self._normalize_url_for_crawl(start_url)
                
                # Initialize crawl state
                crawl_state = CrawlState(
                    crawl_id=crawl_id,
                    start_url=start_url,
                    start_time=datetime.utcnow()
                )
                
                # Initialize crawl data structures
                self._active_crawls[crawl_id] = crawl_state
                self._crawl_queues[crawl_id] = deque([(crawl_start_url, 0)])  # (url, depth)
                self._crawl_visited[crawl_id] = {crawl_start_url}
                self._crawl_tasks[crawl_id] = []
                
                # Start crawl execution
                crawl_task = asyncio.create_task(
                    self._execute_crawl(
                        crawl_id=crawl_id,
                        crawl_rules=crawl_rules,
                        options=options,
                        extraction_strategy=extraction_strategy,
                        output_format=output_format,
                        session_id=session_id,
                        store_results=store_results
                    )
                )
                
                # Don't wait for completion - return immediately
                self.metrics.increment_counter("crawl_service.crawls.started")
                self.logger.info(f"Started crawl {crawl_id} for {start_url}")
                
                return crawl_id
                
            except Exception as e:
                # Clean up on error
                self._cleanup_crawl(crawl_id)
                
                self.metrics.increment_counter("crawl_service.crawls.failed_to_start")
                error_msg = f"Failed to start crawl for {start_url}: {e}"
                self.logger.error(error_msg)
                handle_error(e, context)
                raise
    
    async def start_crawl_async(
        self,
        start_url: str,
        crawl_rules: Optional[CrawlRule] = None,
        options: Optional[Dict[str, Any]] = None,
        extraction_strategy: Optional[Dict[str, Any]] = None,
        output_format: str = "markdown",
        session_id: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """Start a crawl operation asynchronously via job queue.
        
        Args:
            start_url: Starting URL for the crawl
            crawl_rules: Crawling rules and limits
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
            self._validate_url(start_url)
            
            # Convert crawl rules to dict if provided
            rules_dict = None
            if crawl_rules:
                rules_dict = {
                    "max_depth": crawl_rules.max_depth,
                    "max_pages": crawl_rules.max_pages,
                    "max_duration": crawl_rules.max_duration,
                    "delay": crawl_rules.delay,
                    "concurrent_requests": crawl_rules.concurrent_requests,
                    "respect_robots": crawl_rules.respect_robots,
                    "allow_external_links": crawl_rules.allow_external_links,
                    "allow_subdomains": crawl_rules.allow_subdomains,
                    "include_patterns": crawl_rules.include_patterns,
                    "exclude_patterns": crawl_rules.exclude_patterns
                }
            
            # Prepare job data
            job_data = {
                "start_url": start_url,
                "crawl_rules": rules_dict,
                "options": options or {},
                "extraction_strategy": extraction_strategy,
                "output_format": output_format,
                "session_id": session_id
            }
            
            # Submit job
            job_id = await self.job_manager.submit_job(
                job_type=JobType.CRAWL_SITE,
                job_data=job_data,
                priority=priority
            )
            
            self.metrics.increment_counter("crawl_service.async_jobs.submitted")
            self.logger.info(f"Submitted async crawl job {job_id} for {start_url}")
            
            return job_id
            
        except Exception as e:
            error_msg = f"Failed to submit async crawl job for {start_url}: {e}"
            self.logger.error(error_msg)
            handle_error(ValidationError(error_msg))
            raise
    
    async def get_crawl_status(self, crawl_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a crawl operation.
        
        Args:
            crawl_id: Crawl identifier
            
        Returns:
            Crawl status information or None if not found
        """
        crawl_state = self._active_crawls.get(crawl_id)
        if not crawl_state:
            return None
        
        # Update queue status
        crawl_state.urls_queued = len(self._crawl_queues.get(crawl_id, []))
        
        return crawl_state.to_dict()
    
    async def cancel_crawl(self, crawl_id: str) -> bool:
        """Cancel a running crawl operation.
        
        Args:
            crawl_id: Crawl identifier
            
        Returns:
            True if cancelled successfully
        """
        crawl_state = self._active_crawls.get(crawl_id)
        if not crawl_state:
            return False
        
        try:
            # Mark as cancelled
            crawl_state.status = "cancelled"
            
            # Cancel all running tasks
            tasks = self._crawl_tasks.get(crawl_id, [])
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Clean up
            self._cleanup_crawl(crawl_id)
            
            self.metrics.increment_counter("crawl_service.crawls.cancelled")
            self.logger.info(f"Cancelled crawl {crawl_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel crawl {crawl_id}: {e}")
            return False
    
    async def get_crawl_results(self, crawl_id: str) -> List[Dict[str, Any]]:
        """Get results from a completed crawl.
        
        Args:
            crawl_id: Crawl identifier
            
        Returns:
            List of crawl results
        """
        try:
            # Get results from storage using crawl_id as job_id
            results = await self.storage_manager.get_crawl_results_by_job(crawl_id)
            
            self.metrics.increment_counter("crawl_service.results.retrieved")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get crawl results for {crawl_id}: {e}")
            return []
    
    async def _execute_crawl(
        self,
        crawl_id: str,
        crawl_rules: CrawlRule,
        options: Dict[str, Any],
        extraction_strategy: Optional[Dict[str, Any]],
        output_format: str,
        session_id: Optional[str],
        store_results: bool
    ) -> None:
        """Execute the main crawl loop.
        
        Args:
            crawl_id: Crawl identifier
            crawl_rules: Crawling rules
            options: Scraping options
            extraction_strategy: Content extraction configuration
            output_format: Output format
            session_id: Optional session ID
            store_results: Whether to store results
        """
        crawl_state = self._active_crawls[crawl_id]
        queue = self._crawl_queues[crawl_id]
        visited = self._crawl_visited[crawl_id]
        
        try:
            start_time = datetime.utcnow()
            semaphore = asyncio.Semaphore(crawl_rules.concurrent_requests)
            
            while queue and crawl_state.status == "running":
                # Check limits
                if self._should_stop_crawl(crawl_state, crawl_rules, start_time):
                    break
                
                # Get next batch of URLs to process
                batch_urls = []
                while queue and len(batch_urls) < crawl_rules.concurrent_requests:
                    url, depth = queue.popleft()
                    batch_urls.append((url, depth))
                
                # Process batch concurrently
                tasks = []
                for url, depth in batch_urls:
                    task = asyncio.create_task(
                        self._process_crawl_page(
                            crawl_id=crawl_id,
                            url=url,
                            depth=depth,
                            crawl_rules=crawl_rules,
                            options=options,
                            extraction_strategy=extraction_strategy,
                            output_format=output_format,
                            session_id=session_id,
                            store_results=store_results,
                            semaphore=semaphore
                        )
                    )
                    tasks.append(task)
                
                self._crawl_tasks[crawl_id].extend(tasks)
                
                # Wait for batch completion
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Apply delay between batches
                if crawl_rules.delay > 0 and queue:
                    await asyncio.sleep(crawl_rules.delay)
            
            # Mark as completed
            if crawl_state.status == "running":
                crawl_state.status = "completed"
                self.metrics.increment_counter("crawl_service.crawls.completed")
                self.logger.info(f"Crawl {crawl_id} completed successfully")
            
        except Exception as e:
            crawl_state.status = "failed"
            crawl_state.error_message = str(e)
            self.metrics.increment_counter("crawl_service.crawls.failed")
            self.logger.error(f"Crawl {crawl_id} failed: {e}")
            
        finally:
            # Clean up resources
            self._cleanup_crawl(crawl_id)
    
    async def _process_crawl_page(
        self,
        crawl_id: str,
        url: str,
        depth: int,
        crawl_rules: CrawlRule,
        options: Dict[str, Any],
        extraction_strategy: Optional[Dict[str, Any]],
        output_format: str,
        session_id: Optional[str],
        store_results: bool,
        semaphore: asyncio.Semaphore
    ) -> None:
        """Process a single page in the crawl.
        
        Args:
            crawl_id: Crawl identifier
            url: URL to process
            depth: Current depth
            crawl_rules: Crawling rules
            options: Scraping options
            extraction_strategy: Content extraction configuration
            output_format: Output format
            session_id: Optional session ID
            store_results: Whether to store results
            semaphore: Concurrency semaphore
        """
        crawl_state = self._active_crawls[crawl_id]
        queue = self._crawl_queues[crawl_id]
        visited = self._crawl_visited[crawl_id]
        
        async with semaphore:
            try:
                url = self._normalize_url_for_crawl(url)

                # Update state
                crawl_state.pages_crawled += 1
                crawl_state.current_depth = max(crawl_state.current_depth, depth)
                
                # Scrape the page
                scrape_options = options.copy()
                if store_results:
                    # Store with crawl_id as job_id for grouping
                    scrape_options["job_id"] = crawl_id
                
                result = await self.scrape_service.scrape_single(
                    url=url,
                    options=scrape_options,
                    extraction_strategy=extraction_strategy,
                    output_format=output_format,
                    session_id=session_id,
                    store_result=store_results
                )
                
                if result.get("success"):
                    crawl_state.pages_successful += 1
                    
                    # Extract links if we haven't reached max depth
                    if depth < crawl_rules.max_depth:
                        discovered_urls = await self._discover_links(
                            url=url,
                            result=result,
                            crawl_rules=crawl_rules
                        )
                        
                        # Add new URLs to queue
                        new_urls = 0
                        for discovered_url in discovered_urls:
                            if discovered_url not in visited:
                                visited.add(discovered_url)
                                queue.append((discovered_url, depth + 1))
                                new_urls += 1
                        
                        crawl_state.urls_discovered += len(discovered_urls)
                else:
                    crawl_state.pages_failed += 1
                
            except Exception as e:
                crawl_state.pages_failed += 1
                self.logger.error(f"Failed to process page {url} in crawl {crawl_id}: {e}")
    
    async def _discover_links(
        self,
        url: str,
        result: Dict[str, Any],
        crawl_rules: CrawlRule
    ) -> List[str]:
        """Discover links from a scraped page.
        
        Args:
            url: Source URL
            result: Scraping result
            crawl_rules: Crawling rules
            
        Returns:
            List of discovered URLs
        """
        discovered_urls: List[str] = []
        discovered_set: Set[str] = set()
        
        try:
            # Get links from result - check both top level and metadata
            links = result.get("links", [])
            if not links and "metadata" in result:
                links = result["metadata"].get("links", [])
            
            for link in links:
                link_url = link.get("url", "")
                if not link_url:
                    continue
                
                # Convert relative URLs to absolute
                if not link_url.startswith(("http://", "https://")):
                    link_url = urljoin(url, link_url)

                # Normalize for crawl (e.g., strip in-page #fragments)
                link_url = self._normalize_url_for_crawl(link_url)
                
                # Apply filtering rules
                if link_url and self._should_follow_link(url, link_url, crawl_rules):
                    if link_url not in discovered_set:
                        discovered_set.add(link_url)
                        discovered_urls.append(link_url)
            
        except Exception as e:
            self.logger.error(f"Failed to discover links from {url}: {e}")
        
        return discovered_urls

    def _normalize_url_for_crawl(self, url: str) -> str:
        """Normalize URLs for crawl queueing/deduplication.

        Currently:
        - Strips `#fragment` so in-page anchors don't cause duplicate crawls.
        """
        if not url:
            return url
        normalized, _fragment = urldefrag(url)
        return normalized
    
    def _should_follow_link(
        self,
        source_url: str,
        target_url: str,
        crawl_rules: CrawlRule
    ) -> bool:
        """Determine if a link should be followed.
        
        Args:
            source_url: Source page URL
            target_url: Target link URL
            crawl_rules: Crawling rules
            
        Returns:
            True if link should be followed
        """
        try:
            source_parsed = urlparse(source_url)
            target_parsed = urlparse(target_url)
            
            # Check domain restrictions
            if not crawl_rules.allow_external_links:
                if target_parsed.netloc != source_parsed.netloc:
                    if not crawl_rules.allow_subdomains:
                        return False
                    elif not target_parsed.netloc.endswith(f".{source_parsed.netloc}"):
                        return False
            
            # Apply include patterns
            if crawl_rules.include_patterns:
                if not any(re.search(pattern, target_url) for pattern in crawl_rules.include_patterns):
                    return False
            
            # Apply exclude patterns
            if crawl_rules.exclude_patterns:
                if any(re.search(pattern, target_url) for pattern in crawl_rules.exclude_patterns):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _should_stop_crawl(
        self,
        crawl_state: CrawlState,
        crawl_rules: CrawlRule,
        start_time: datetime
    ) -> bool:
        """Check if crawl should be stopped based on limits.
        
        Args:
            crawl_state: Current crawl state
            crawl_rules: Crawling rules
            start_time: Crawl start time
            
        Returns:
            True if crawl should stop
        """
        # Check page limit
        if crawl_state.pages_crawled >= crawl_rules.max_pages:
            self.logger.info(f"Crawl {crawl_state.crawl_id} reached max pages limit")
            return True
        
        # Check time limit
        elapsed_time = (datetime.utcnow() - start_time).total_seconds()
        if elapsed_time >= crawl_rules.max_duration:
            self.logger.info(f"Crawl {crawl_state.crawl_id} reached max duration limit")
            return True
        
        # Check if cancelled
        if crawl_state.status == "cancelled":
            return True
        
        return False
    
    def _cleanup_crawl(self, crawl_id: str) -> None:
        """Clean up crawl resources.
        
        Args:
            crawl_id: Crawl identifier
        """
        try:
            # Cancel any remaining tasks
            tasks = self._crawl_tasks.get(crawl_id, [])
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Remove from tracking (keep state for status queries)
            self._crawl_queues.pop(crawl_id, None)
            self._crawl_visited.pop(crawl_id, None)
            self._crawl_tasks.pop(crawl_id, None)
            
            # Note: Keep _active_crawls for status queries
            
        except Exception as e:
            self.logger.error(f"Error cleaning up crawl {crawl_id}: {e}")
    
    def _get_default_crawl_rules(self) -> CrawlRule:
        """Get default crawling rules from configuration.
        
        Returns:
            Default crawl rules
        """
        return CrawlRule(
            max_depth=self.config_manager.get_setting("crawl.max_depth", 3),
            max_pages=self.config_manager.get_setting("crawl.max_pages", 100),
            max_duration=self.config_manager.get_setting("crawl.max_duration", 3600),
            delay=self.config_manager.get_setting("crawl.delay", 1.0),
            concurrent_requests=self.config_manager.get_setting("crawl.concurrent_requests", 5),
            respect_robots=self.config_manager.get_setting("crawl.respect_robots", True),
            allow_external_links=self.config_manager.get_setting("crawl.allow_external_links", False),
            allow_subdomains=self.config_manager.get_setting("crawl.allow_subdomains", True)
        )
    
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
            raise ValidationError("URL must start with http:// or https://")
        
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValidationError("URL must have a valid domain")
        except Exception as e:
            raise ValidationError(f"Invalid URL format: {e}")
    
    # Job handler for async processing
    
    async def _handle_crawl_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle crawl job.
        
        Args:
            job_data: Job parameters
            
        Returns:
            Job result
        """
        try:
            # Convert rules dict back to CrawlRule object
            crawl_rules = None
            if job_data.get("crawl_rules"):
                rules_dict = job_data["crawl_rules"]
                crawl_rules = CrawlRule(
                    max_depth=rules_dict.get("max_depth", 3),
                    max_pages=rules_dict.get("max_pages", 100),
                    max_duration=rules_dict.get("max_duration", 3600),
                    delay=rules_dict.get("delay", 1.0),
                    concurrent_requests=rules_dict.get("concurrent_requests", 5),
                    respect_robots=rules_dict.get("respect_robots", True),
                    allow_external_links=rules_dict.get("allow_external_links", False),
                    allow_subdomains=rules_dict.get("allow_subdomains", True),
                    include_patterns=rules_dict.get("include_patterns", []),
                    exclude_patterns=rules_dict.get("exclude_patterns", [])
                )
            
            crawl_id = await self.start_crawl(
                start_url=job_data["start_url"],
                crawl_rules=crawl_rules,
                options=job_data.get("options"),
                extraction_strategy=job_data.get("extraction_strategy"),
                output_format=job_data.get("output_format", "markdown"),
                session_id=job_data.get("session_id"),
                store_results=True
            )
            
            # Wait for crawl completion
            while True:
                status = await self.get_crawl_status(crawl_id)
                if not status or status["status"] in ["completed", "failed", "cancelled"]:
                    break
                await asyncio.sleep(5)  # Check every 5 seconds
            
            # Get final results
            final_status = await self.get_crawl_status(crawl_id)
            results = await self.get_crawl_results(crawl_id)
            
            return {
                "success": True,
                "result": {
                    "crawl_id": crawl_id,
                    "status": final_status,
                    "results_count": len(results),
                    "results": results[:10]  # Return first 10 results in job result
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Global crawl service instance
_crawl_service: Optional[CrawlService] = None


def get_crawl_service() -> CrawlService:
    """Get the global crawl service instance."""
    global _crawl_service
    if _crawl_service is None:
        _crawl_service = CrawlService()
    return _crawl_service
