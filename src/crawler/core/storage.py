"""Storage management using SQLite for results, cache, and session persistence."""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from sqlalchemy import select, delete, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import get_database_manager
from ..database.models import (
    CrawlResult, CrawlLink, CrawlMedia,
    BrowserSession, CacheEntry, JobQueue
)
from ..foundation.config import get_config_manager
from ..foundation.logging import get_logger
from ..foundation.errors import handle_error, ResourceError
from ..foundation.metrics import get_metrics_collector, timer


class StorageManager:
    """Manages SQLite-based data storage, caching, and persistence."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        self.db_manager = get_database_manager()
    
    async def initialize(self) -> None:
        """Initialize the storage system."""
        try:
            await self.db_manager.setup_database()
            self.logger.info("Storage manager initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize storage manager: {e}"
            self.logger.error(error_msg)
            handle_error(ResourceError(error_msg, resource_type="database"))
            raise
    
    # ==================== CRAWL RESULT STORAGE ====================
    
    async def store_crawl_result(
        self,
        url: str,
        content_markdown: Optional[str] = None,
        content_html: Optional[str] = None,
        content_text: Optional[str] = None,
        extracted_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        success: bool = True,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        job_id: Optional[str] = None,
        links: Optional[List[Dict[str, Any]]] = None,
        media: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Store a crawl result in the database.
        
        Args:
            url: The URL that was crawled
            content_markdown: Markdown content
            content_html: HTML content
            content_text: Plain text content
            extracted_data: Structured extracted data
            metadata: Additional metadata
            title: Page title
            success: Whether the crawl was successful
            status_code: HTTP status code
            error_message: Error message if failed
            job_id: Associated job ID
            links: List of links found on the page
            media: List of media found on the page
            
        Returns:
            The ID of the stored result
        """
        with timer("storage.store_crawl_result"):
            try:
                async with self.db_manager.get_session() as session:
                    # Create crawl result
                    crawl_result = CrawlResult(
                        job_id=job_id,
                        url=url,
                        title=title,
                        success=success,
                        status_code=status_code,
                        content_markdown=content_markdown,
                        content_html=content_html,
                        content_text=content_text,
                        extracted_data=extracted_data,
                        metadata=metadata,
                        error_message=error_message
                    )
                    
                    session.add(crawl_result)
                    await session.flush()  # Get the ID
                    
                    # Store links if provided
                    if links:
                        for link_data in links:
                            link = CrawlLink(
                                crawl_result_id=crawl_result.id,
                                url=link_data.get("url", ""),
                                text=link_data.get("text"),
                                link_type=link_data.get("type", "external"),
                                metadata=link_data.get("metadata")
                            )
                            session.add(link)
                    
                    # Store media if provided
                    if media:
                        for media_data in media:
                            media_item = CrawlMedia(
                                crawl_result_id=crawl_result.id,
                                url=media_data.get("url", ""),
                                media_type=media_data.get("type", "unknown"),
                                alt_text=media_data.get("alt_text"),
                                width=media_data.get("width"),
                                height=media_data.get("height"),
                                file_size=media_data.get("file_size"),
                                metadata=media_data.get("metadata")
                            )
                            session.add(media_item)
                    
                    await session.commit()
                    
                    result_id = str(crawl_result.id)
                    self.metrics.increment_counter("storage.crawl_results.stored")
                    self.logger.debug(f"Stored crawl result {result_id} for URL: {url}")
                    
                    return result_id
                    
            except Exception as e:
                self.metrics.increment_counter("storage.crawl_results.errors")
                error_msg = f"Failed to store crawl result for {url}: {e}"
                self.logger.error(error_msg)
                handle_error(ResourceError(error_msg, resource_type="database"))
                raise
    
    async def get_crawl_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a crawl result by ID.
        
        Args:
            result_id: The result ID
            
        Returns:
            Crawl result data or None if not found
        """
        with timer("storage.get_crawl_result"):
            try:
                async with self.db_manager.get_session() as session:
                    # Get the main result
                    stmt = select(CrawlResult).where(CrawlResult.id == int(result_id))
                    result = await session.execute(stmt)
                    crawl_result = result.scalar_one_or_none()
                    
                    if not crawl_result:
                        return None
                    
                    # Get associated links
                    links_stmt = select(CrawlLink).where(CrawlLink.crawl_result_id == crawl_result.id)
                    links_result = await session.execute(links_stmt)
                    links = links_result.scalars().all()
                    
                    # Get associated media
                    media_stmt = select(CrawlMedia).where(CrawlMedia.crawl_result_id == crawl_result.id)
                    media_result = await session.execute(media_stmt)
                    media = media_result.scalars().all()
                    
                    # Convert to dictionary
                    data = crawl_result.to_dict()
                    data["links"] = [link.to_dict() for link in links]
                    data["media"] = [item.to_dict() for item in media]
                    
                    self.metrics.increment_counter("storage.crawl_results.retrieved")
                    return data
                    
            except Exception as e:
                self.metrics.increment_counter("storage.crawl_results.errors")
                error_msg = f"Failed to retrieve crawl result {result_id}: {e}"
                self.logger.error(error_msg)
                handle_error(ResourceError(error_msg, resource_type="database"))
                return None
    
    async def get_crawl_results_by_job(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all crawl results for a job.
        
        Args:
            job_id: The job ID
            
        Returns:
            List of crawl result data
        """
        with timer("storage.get_crawl_results_by_job"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = select(CrawlResult).where(CrawlResult.job_id == job_id)
                    result = await session.execute(stmt)
                    crawl_results = result.scalars().all()
                    
                    results = []
                    for crawl_result in crawl_results:
                        data = crawl_result.to_dict()
                        
                        # Get links for this result
                        links_stmt = select(CrawlLink).where(CrawlLink.crawl_result_id == crawl_result.id)
                        links_result = await session.execute(links_stmt)
                        links = links_result.scalars().all()
                        data["links"] = [link.to_dict() for link in links]
                        
                        # Get media for this result
                        media_stmt = select(CrawlMedia).where(CrawlMedia.crawl_result_id == crawl_result.id)
                        media_result = await session.execute(media_stmt)
                        media = media_result.scalars().all()
                        data["media"] = [item.to_dict() for item in media]
                        
                        results.append(data)
                    
                    self.metrics.increment_counter("storage.crawl_results.batch_retrieved")
                    return results
                    
            except Exception as e:
                self.metrics.increment_counter("storage.crawl_results.errors")
                error_msg = f"Failed to retrieve crawl results for job {job_id}: {e}"
                self.logger.error(error_msg)
                handle_error(ResourceError(error_msg, resource_type="database"))
                return []
    
    # ==================== CACHE MANAGEMENT ====================
    
    def _generate_cache_key(self, url: str, options: Optional[Dict[str, Any]] = None) -> str:
        """Generate a cache key for a URL and options.
        
        Args:
            url: The URL
            options: Additional options that affect caching
            
        Returns:
            Cache key string
        """
        cache_data = {"url": url}
        if options:
            # Only include cacheable options
            cacheable_options = {
                k: v for k, v in options.items()
                if k in ["extract_strategy", "css_selector", "llm_model", "format"]
            }
            cache_data.update(cacheable_options)
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:32]
    
    async def get_cached_result(
        self,
        url: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached result for a URL.
        
        Args:
            url: The URL
            options: Options that affect caching
            
        Returns:
            Cached result data or None if not found/expired
        """
        cache_key = self._generate_cache_key(url, options)
        
        with timer("storage.get_cached_result"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = select(CacheEntry).where(CacheEntry.cache_key == cache_key)
                    result = await session.execute(stmt)
                    cache_entry = result.scalar_one_or_none()
                    
                    if not cache_entry:
                        self.metrics.increment_counter("storage.cache.misses")
                        return None
                    
                    # Check if expired
                    if cache_entry.is_expired():
                        # Delete expired entry
                        await session.delete(cache_entry)
                        await session.commit()
                        self.metrics.increment_counter("storage.cache.expired")
                        return None
                    
                    # Update access statistics
                    cache_entry.increment_access_count()
                    await session.commit()
                    
                    self.metrics.increment_counter("storage.cache.hits")
                    return cache_entry.data_value
                    
            except Exception as e:
                self.metrics.increment_counter("storage.cache.errors")
                self.logger.error(f"Failed to get cached result for {url}: {e}")
                return None
    
    async def store_cached_result(
        self,
        url: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Store result in cache.
        
        Args:
            url: The URL
            data: Data to cache
            options: Options that affect caching
            ttl_seconds: Time to live in seconds
            
        Returns:
            True if stored successfully
        """
        cache_key = self._generate_cache_key(url, options)
        
        if ttl_seconds is None:
            ttl_seconds = self.config_manager.get_setting("storage.cache_ttl", 3600)
        
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        with timer("storage.store_cached_result"):
            try:
                async with self.db_manager.get_session() as session:
                    # Check if entry already exists
                    stmt = select(CacheEntry).where(CacheEntry.cache_key == cache_key)
                    result = await session.execute(stmt)
                    cache_entry = result.scalar_one_or_none()
                    
                    if cache_entry:
                        # Update existing entry
                        cache_entry.data_value = data
                        cache_entry.expires_at = expires_at
                        cache_entry.last_accessed = datetime.utcnow()
                    else:
                        # Create new entry
                        cache_entry = CacheEntry(
                            cache_key=cache_key,
                            data_value=data,
                            data_type="json",
                            expires_at=expires_at,
                            last_accessed=datetime.utcnow()
                        )
                        session.add(cache_entry)
                    
                    await session.commit()
                    self.metrics.increment_counter("storage.cache.stored")
                    return True
                    
            except Exception as e:
                self.metrics.increment_counter("storage.cache.errors")
                self.logger.error(f"Failed to store cached result for {url}: {e}")
                return False
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries.
        
        Returns:
            Number of entries cleaned up
        """
        with timer("storage.cleanup_expired_cache"):
            try:
                async with self.db_manager.get_session() as session:
                    current_time = datetime.utcnow()
                    stmt = delete(CacheEntry).where(
                        and_(
                            CacheEntry.expires_at.isnot(None),
                            CacheEntry.expires_at < current_time
                        )
                    )
                    result = await session.execute(stmt)
                    await session.commit()
                    
                    cleaned_count = result.rowcount
                    if cleaned_count > 0:
                        self.logger.info(f"Cleaned up {cleaned_count} expired cache entries")
                        self.metrics.record_metric("storage.cache.cleaned", cleaned_count)
                    
                    return cleaned_count
                    
            except Exception as e:
                self.metrics.increment_counter("storage.cache.errors")
                self.logger.error(f"Failed to cleanup expired cache: {e}")
                return 0
    
    # ==================== SESSION MANAGEMENT ====================
    
    async def store_session(
        self,
        session_id: str,
        config: Dict[str, Any],
        state_data: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """Store browser session data.
        
        Args:
            session_id: Session identifier
            config: Session configuration
            state_data: Session state data
            expires_at: When the session expires
            
        Returns:
            True if stored successfully
        """
        with timer("storage.store_session"):
            try:
                async with self.db_manager.get_session() as session:
                    # Check if session already exists
                    stmt = select(BrowserSession).where(BrowserSession.session_id == session_id)
                    result = await session.execute(stmt)
                    browser_session = result.scalar_one_or_none()
                    
                    if browser_session:
                        # Update existing session
                        browser_session.config = config
                        browser_session.state_data = state_data
                        browser_session.last_accessed = datetime.utcnow()
                        if expires_at:
                            browser_session.expires_at = expires_at
                    else:
                        # Create new session
                        browser_session = BrowserSession(
                            session_id=session_id,
                            config=config,
                            state_data=state_data,
                            last_accessed=datetime.utcnow(),
                            expires_at=expires_at
                        )
                        session.add(browser_session)
                    
                    await session.commit()
                    self.metrics.increment_counter("storage.sessions.stored")
                    return True
                    
            except Exception as e:
                self.metrics.increment_counter("storage.sessions.errors")
                self.logger.error(f"Failed to store session {session_id}: {e}")
                return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get browser session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data or None if not found
        """
        with timer("storage.get_session"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = select(BrowserSession).where(BrowserSession.session_id == session_id)
                    result = await session.execute(stmt)
                    browser_session = result.scalar_one_or_none()
                    
                    if not browser_session:
                        return None
                    
                    # Check if expired
                    if browser_session.is_expired():
                        await session.delete(browser_session)
                        await session.commit()
                        self.metrics.increment_counter("storage.sessions.expired")
                        return None
                    
                    # Update last accessed
                    browser_session.last_accessed = datetime.utcnow()
                    await session.commit()
                    
                    self.metrics.increment_counter("storage.sessions.retrieved")
                    return browser_session.to_dict()
                    
            except Exception as e:
                self.metrics.increment_counter("storage.sessions.errors")
                self.logger.error(f"Failed to get session {session_id}: {e}")
                return None
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a browser session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted successfully
        """
        with timer("storage.delete_session"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = delete(BrowserSession).where(BrowserSession.session_id == session_id)
                    result = await session.execute(stmt)
                    await session.commit()
                    
                    if result.rowcount > 0:
                        self.metrics.increment_counter("storage.sessions.deleted")
                        return True
                    return False
                    
            except Exception as e:
                self.metrics.increment_counter("storage.sessions.errors")
                self.logger.error(f"Failed to delete session {session_id}: {e}")
                return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        with timer("storage.cleanup_expired_sessions"):
            try:
                async with self.db_manager.get_session() as session:
                    current_time = datetime.utcnow()
                    stmt = delete(BrowserSession).where(
                        and_(
                            BrowserSession.expires_at.isnot(None),
                            BrowserSession.expires_at < current_time
                        )
                    )
                    result = await session.execute(stmt)
                    await session.commit()
                    
                    cleaned_count = result.rowcount
                    if cleaned_count > 0:
                        self.logger.info(f"Cleaned up {cleaned_count} expired sessions")
                        self.metrics.record_metric("storage.sessions.cleaned", cleaned_count)
                    
                    return cleaned_count
                    
            except Exception as e:
                self.metrics.increment_counter("storage.sessions.errors")
                self.logger.error(f"Failed to cleanup expired sessions: {e}")
                return 0
    
    # ==================== MAINTENANCE ====================
    
    async def cleanup_old_data(self, retention_days: Optional[int] = None) -> Dict[str, int]:
        """Clean up old data based on retention policy.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Dictionary with cleanup counts
        """
        if retention_days is None:
            retention_days = self.config_manager.get_setting("storage.retention_days", 30)
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cleanup_counts = {}
        
        with timer("storage.cleanup_old_data"):
            try:
                async with self.db_manager.get_session() as session:
                    # Clean up old crawl results
                    crawl_stmt = delete(CrawlResult).where(CrawlResult.created_at < cutoff_date)
                    crawl_result = await session.execute(crawl_stmt)
                    cleanup_counts["crawl_results"] = crawl_result.rowcount
                    
                    # Clean up old cache entries
                    cache_stmt = delete(CacheEntry).where(CacheEntry.created_at < cutoff_date)
                    cache_result = await session.execute(cache_stmt)
                    cleanup_counts["cache_entries"] = cache_result.rowcount
                    
                    # Clean up inactive sessions older than cutoff
                    session_stmt = delete(BrowserSession).where(
                        and_(
                            BrowserSession.is_active == False,
                            BrowserSession.created_at < cutoff_date
                        )
                    )
                    session_result = await session.execute(session_stmt)
                    cleanup_counts["browser_sessions"] = session_result.rowcount
                    
                    await session.commit()
                    
                    total_cleaned = sum(cleanup_counts.values())
                    if total_cleaned > 0:
                        self.logger.info(f"Cleaned up {total_cleaned} old records: {cleanup_counts}")
                        self.metrics.record_metric("storage.cleanup.total", total_cleaned)
                    
                    return cleanup_counts
                    
            except Exception as e:
                self.metrics.increment_counter("storage.cleanup.errors")
                self.logger.error(f"Failed to cleanup old data: {e}")
                return {}
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        with timer("storage.get_stats"):
            try:
                async with self.db_manager.get_session() as session:
                    stats = {}
                    
                    # Count crawl results
                    crawl_stmt = select(CrawlResult)
                    crawl_result = await session.execute(crawl_stmt)
                    stats["crawl_results_count"] = len(crawl_result.scalars().all())
                    
                    # Count cache entries
                    cache_stmt = select(CacheEntry)
                    cache_result = await session.execute(cache_stmt)
                    stats["cache_entries_count"] = len(cache_result.scalars().all())
                    
                    # Count sessions
                    session_stmt = select(BrowserSession)
                    session_result = await session.execute(session_stmt)
                    sessions = session_result.scalars().all()
                    stats["browser_sessions_count"] = len(sessions)
                    stats["active_sessions_count"] = len([s for s in sessions if s.is_active])
                    
                    # Database file size
                    db_path = Path(self.config_manager.get_setting("storage.database_path", "~/.crawler/crawler.db")).expanduser()
                    if db_path.exists():
                        stats["database_size_mb"] = db_path.stat().st_size / 1024 / 1024
                    else:
                        stats["database_size_mb"] = 0
                    
                    stats["timestamp"] = datetime.utcnow().isoformat()
                    
                    return stats
                    
            except Exception as e:
                self.logger.error(f"Failed to get storage stats: {e}")
                return {"error": str(e)}


# Global storage manager instance
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """Get the global storage manager instance."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager