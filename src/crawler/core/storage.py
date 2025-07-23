"""Storage management using SQLite for results, cache, and session persistence."""

import json
import hashlib
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from sqlalchemy import select, delete, update, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy.exc

from ..database.connection import get_database_manager
from ..database.models import (
    CrawlResult, CrawlLink, CrawlMedia,
    BrowserSession, CacheEntry, JobQueue
)
from ..foundation.config import get_config_manager
from ..foundation.logging import get_logger
from ..foundation.errors import handle_error, ResourceError
from ..foundation.metrics import get_metrics_collector, timer


def _serialize_datetime(obj: Any) -> Any:
    """Serialize datetime objects to ISO format strings for JSON storage."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_datetime(item) for item in obj]
    else:
        return obj


class StorageManager:
    """Manages SQLite-based data storage, caching, and persistence."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        
        # Concurrency control
        self._write_lock = asyncio.Lock()
        self._cache_locks = {}  # Per-key locks for cache operations
        
        # Set custom database path if provided
        if db_path:
            self.config_manager.set_setting("storage.database_path", db_path)
        
        # Import here to avoid circular imports
        from ..database.connection import DatabaseManager
        self.db_manager = DatabaseManager(config_manager=self.config_manager)
        
        # Ensure database is created with WAL mode when custom path is provided
        if db_path:
            self._ensure_database_created()
        
        # Don't initialize engine here - wait for initialize() call
    
    def _ensure_database_created(self) -> None:
        """Ensure the database file is created and WAL mode is enabled."""
        try:
            # Get database path from configuration
            db_path = self.config_manager.get_setting(
                "storage.database_path", 
                "~/.crawler/crawler.db"
            )
            db_path = Path(db_path).expanduser().resolve()
            
            # Ensure directory exists
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create a direct SQLite connection to set up WAL mode
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                # Performance optimizations
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
                
            self.logger.debug(f"Database created with WAL mode at: {db_path}")
        except (PermissionError, OSError) as e:
            # Convert permission/OS errors to StorageError for proper error handling
            from ..foundation.errors import StorageError
            raise StorageError(f"Failed to create database at {db_path}: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to ensure database creation: {e}")
    
    @property
    def db_path(self) -> str:
        """Get the current database path."""
        return self.config_manager.get_setting("storage.database_path", "~/.crawler/crawler.db")
    
    @db_path.setter
    def db_path(self, value: str) -> None:
        """Set the database path."""
        self.config_manager.set_setting("storage.database_path", value)
        # Recreate the database manager with the new config
        from ..database.connection import DatabaseManager
        self.db_manager = DatabaseManager(config_manager=self.config_manager)
    
    async def initialize(self) -> None:
        """Initialize the storage system."""
        try:
            # Initialize the database engine to trigger WAL mode setup
            # This ensures the database is ready immediately
            _ = self.db_manager.engine
            
            # Trigger a connection to ensure database file is created with WAL mode
            self._ensure_database_created()
            
            # Check if database path is valid
            db_path = self.config_manager.get_setting(
                "storage.database_path", 
                "~/.crawler/crawler.db"
            )
            db_path = Path(db_path).expanduser().resolve()
            
            # Check if parent directory is accessible/creatable
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                from ..foundation.errors import StorageError
                error_msg = f"Cannot create database directory {db_path.parent}: {e}"
                self.logger.error(error_msg)
                raise StorageError(error_msg)
            
            await self.db_manager.initialize()
            self.logger.info("Storage manager initialized successfully")
        except Exception as e:
            # Import here to avoid circular imports
            from ..foundation.errors import StorageError
            if isinstance(e, StorageError):
                raise  # Re-raise StorageError as-is
            error_msg = f"Failed to initialize storage manager: {e}"
            self.logger.error(error_msg)
            handle_error(StorageError(error_msg))
            raise StorageError(error_msg)
    
    async def cleanup(self) -> None:
        """Clean up storage resources."""
        try:
            await self.db_manager.close()
            self.logger.info("Storage manager cleaned up successfully")
        except Exception as e:
            self.logger.error(f"Failed to cleanup storage manager: {e}")
            raise
    
    # ==================== CRAWL RESULT STORAGE ====================
    
    async def store_scrape_result(
        self,
        url_or_data: Union[str, Dict[str, Any]],
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
            url_or_data: Either a URL string or a dictionary containing all result data
            content_markdown: Markdown content (if url_or_data is a string)
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
                # Handle both dictionary and individual parameter calling conventions
                if isinstance(url_or_data, dict):
                    # Extract data from dictionary
                    data = url_or_data
                    url = data.get("url")
                    content_markdown = data.get("content_markdown") or data.get("content")
                    content_html = data.get("content_html")
                    content_text = data.get("content_text")
                    extracted_data = data.get("extracted_data")
                    metadata = data.get("metadata")
                    title = data.get("title")
                    success = data.get("success", True)
                    status_code = data.get("status_code")
                    error_message = data.get("error_message")
                    job_id = data.get("job_id")
                    links = data.get("links")
                    media = data.get("media")
                else:
                    # Use individual parameters
                    url = url_or_data
                
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
                        meta_data=metadata,
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
                                meta_data=link_data.get("metadata")
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
                                meta_data=media_data.get("metadata")
                            )
                            session.add(media_item)
                    
                    await session.commit()
                    
                    result_id = str(crawl_result.id)
                    self.metrics.increment_counter("storage.crawl_results.stored")
                    self.logger.debug(f"Stored crawl result {result_id} for URL: {url}")
                    
                    return result_id
                    
            except (sqlite3.OperationalError, sqlalchemy.exc.OperationalError) as e:
                self.metrics.increment_counter("storage.crawl_results.errors")
                url_for_error = url if isinstance(url_or_data, str) else url_or_data.get("url", "unknown")
                error_msg = f"Failed to store crawl result for {url_for_error}: {e}"
                self.logger.error(error_msg)
                
                # Convert database errors to StorageError
                from ..foundation.errors import StorageError
                if "disk" in str(e).lower() or "full" in str(e).lower():
                    storage_error = StorageError(f"Database disk space exhausted: {e}")
                else:
                    storage_error = StorageError(f"Database operational error: {e}")
                
                handle_error(storage_error)
                raise storage_error
            except Exception as e:
                self.metrics.increment_counter("storage.crawl_results.errors")
                url_for_error = url if isinstance(url_or_data, str) else url_or_data.get("url", "unknown")
                error_msg = f"Failed to store crawl result for {url_for_error}: {e}"
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
    
    # Alias for backward compatibility
    async def store_crawl_result(self, *args, **kwargs):
        """Alias for store_scrape_result for backward compatibility."""
        return await self.store_scrape_result(*args, **kwargs)
    
    # Alias for backward compatibility 
    async def get_scrape_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Alias for get_crawl_result for backward compatibility."""
        return await self.get_crawl_result(result_id)
    
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
        
        # Use per-key locking to prevent race conditions
        if cache_key not in self._cache_locks:
            self._cache_locks[cache_key] = asyncio.Lock()
        
        async with self._cache_locks[cache_key]:
            with timer("storage.get_cached_result"):
                try:
                    async with self.db_manager.get_session() as session:
                        stmt = select(CacheEntry).where(CacheEntry.cache_key == cache_key)
                        result = await session.execute(stmt)
                        cache_entry = result.scalar_one_or_none()
                        
                        if not cache_entry:
                            self.metrics.increment_counter("storage.cache.misses")
                            return None
                        
                        # Check if expired manually to avoid greenlet issues
                        current_time = datetime.utcnow()
                        is_expired = False
                        if cache_entry.expires_at is not None:
                            is_expired = current_time > cache_entry.expires_at
                        
                        if is_expired:
                            # Delete expired entry
                            await session.delete(cache_entry)
                            await session.commit()
                            self.metrics.increment_counter("storage.cache.expired")
                            return None
                        
                        # Update access statistics manually
                        cache_entry.access_count += 1
                        cache_entry.last_accessed = current_time
                        await session.commit()
                        
                        self.metrics.increment_counter("storage.cache.hits")
                        return cache_entry.data_value
                        
                except Exception as e:
                    self.metrics.increment_counter("storage.cache.errors")
                    self.logger.error(f"Failed to get cached result for {url}: {e}")
                    return None
    
    
    # Alias for backward compatibility  
    async def store_cached_result(self, url: str, data: Dict[str, Any], options: Optional[Dict[str, Any]] = None, cache_ttl: Optional[int] = None, ttl: Optional[int] = None):
        """Store cached result with proper parameter handling."""
        # Use ttl parameter if provided, otherwise use cache_ttl
        effective_ttl = ttl if ttl is not None else cache_ttl
        
        # Generate cache key same way as get_cached_result for consistency
        cache_key = self._generate_cache_key(url, options)
        
        # Call store_cache directly with the generated key (locking happens there)
        return await self.store_cache(cache_key, data, ttl=effective_ttl)
    
    # Test-compatible cache methods
    async def store_cache(
        self,
        cache_key_or_url: Union[str, Dict[str, Any]],
        data: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Store data in cache - handles both test signature and original signature."""
        # Handle test calling convention: store_cache(cache_key, data, ttl=...)
        if isinstance(cache_key_or_url, str) and data is not None:
            cache_key = cache_key_or_url
            cache_data = data
            ttl_to_use = ttl or ttl_seconds
        # Handle original calling convention: store_cache(url, data, options=..., ttl_seconds=...)
        else:
            url = cache_key_or_url if isinstance(cache_key_or_url, str) else "unknown"
            cache_key = self._generate_cache_key(url, options)
            cache_data = data
            ttl_to_use = ttl_seconds or ttl
        
        if ttl_to_use is None:
            ttl_to_use = self.config_manager.get_setting("storage.cache_ttl", 3600)
        
        # Ensure ttl_to_use is an integer
        if not isinstance(ttl_to_use, int):
            if isinstance(ttl_to_use, dict):
                # If it's a dict, try to extract a numeric value or use default
                ttl_to_use = 3600
            else:
                # Try to convert to int, fallback to default
                try:
                    ttl_to_use = int(ttl_to_use)
                except (ValueError, TypeError):
                    ttl_to_use = 3600
        
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_to_use)
        
        # Get or create a lock for this cache key
        if cache_key not in self._cache_locks:
            self._cache_locks[cache_key] = asyncio.Lock()
        
        async with self._cache_locks[cache_key]:
            with timer("storage.store_cache"):
                try:
                    async with self.db_manager.get_session() as session:
                        # Check if entry already exists
                        stmt = select(CacheEntry).where(CacheEntry.cache_key == cache_key)
                        result = await session.execute(stmt)
                        cache_entry = result.scalar_one_or_none()
                    
                        # Serialize datetime objects in cache data
                        serialized_data = _serialize_datetime(cache_data)
                        
                        if cache_entry:
                            # Update existing entry
                            cache_entry.data_value = serialized_data
                            cache_entry.expires_at = expires_at
                            cache_entry.last_accessed = datetime.utcnow()
                        else:
                            # Create new entry
                            cache_entry = CacheEntry(
                                cache_key=cache_key,
                                data_value=serialized_data,
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
                    self.logger.error(f"Failed to store cache: {e}")
                    return False
    
    async def get_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached data by cache key - test compatibility method."""
        # Get or create a lock for this cache key
        if cache_key not in self._cache_locks:
            self._cache_locks[cache_key] = asyncio.Lock()
        
        async with self._cache_locks[cache_key]:
            with timer("storage.get_cache"):
                try:
                    async with self.db_manager.get_session() as session:
                        stmt = select(CacheEntry).where(CacheEntry.cache_key == cache_key)
                        result = await session.execute(stmt)
                        cache_entry = result.scalar_one_or_none()
                    
                        if not cache_entry:
                            return None
                        
                        # Check if expired manually to avoid greenlet issues
                        current_time = datetime.utcnow()
                        is_expired = False
                        if cache_entry.expires_at is not None:
                            is_expired = current_time > cache_entry.expires_at
                        
                        if is_expired:
                            await session.delete(cache_entry)
                            await session.commit()
                            return None
                        
                        # Update access statistics manually
                        cache_entry.access_count += 1
                        cache_entry.last_accessed = current_time
                        await session.commit()
                        
                        return cache_entry.data_value
                        
                except Exception as e:
                    self.logger.error(f"Failed to get cache for key {cache_key}: {e}")
                    return None
    
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
        session_id_or_data: Union[str, Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
        state_data: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """Store browser session data.
        
        Args:
            session_id_or_data: Either session ID string or session data dictionary
            config: Session configuration (if session_id_or_data is string)
            state_data: Session state data
            expires_at: When the session expires
            
        Returns:
            True if stored successfully
        """
        with timer("storage.store_session"):
            try:
                # Handle both dictionary and individual parameter calling conventions
                if isinstance(session_id_or_data, dict):
                    # Extract data from dictionary
                    data = session_id_or_data
                    session_id = data.get("session_id")
                    config = data.get("config")
                    state_data = data.get("state_data")
                    expires_at = data.get("expires_at")
                else:
                    # Use individual parameters
                    session_id = session_id_or_data
                
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
                session_id_for_error = session_id if isinstance(session_id_or_data, str) else session_id_or_data.get("session_id", "unknown")
                self.logger.error(f"Failed to store session {session_id_for_error}: {e}")
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
                # Use direct SQL query to avoid greenlet issues with SQLAlchemy ORM
                from sqlalchemy import text
                async with self.db_manager.get_session() as session:
                    stmt = text("""
                        SELECT session_id, config, state_data, is_active, expires_at
                        FROM browser_sessions 
                        WHERE session_id = :session_id
                    """)
                    result = await session.execute(stmt, {"session_id": session_id})
                    row = result.fetchone()
                    
                    if not row:
                        return None
                    
                    session_id_db, config_json, state_data_json, is_active, expires_at = row
                    
                    # Check if expired
                    current_time = datetime.utcnow()
                    if expires_at is not None:
                        # Handle case where expires_at might be a string from database
                        if isinstance(expires_at, str):
                            from dateutil.parser import parse
                            try:
                                expires_at = parse(expires_at)
                            except (ValueError, TypeError):
                                expires_at = None
                        
                        if expires_at and current_time > expires_at:
                            # Delete expired session
                            delete_stmt = text("DELETE FROM browser_sessions WHERE session_id = :session_id")
                            await session.execute(delete_stmt, {"session_id": session_id})
                            await session.commit()
                            self.metrics.increment_counter("storage.sessions.expired")
                            return None
                    
                    # Update last accessed
                    update_stmt = text("""
                        UPDATE browser_sessions 
                        SET last_accessed = :current_time, updated_at = :current_time
                        WHERE session_id = :session_id
                    """)
                    await session.execute(update_stmt, {
                        "current_time": current_time,
                        "session_id": session_id
                    })
                    await session.commit()
                    
                    # Parse JSON data
                    import json
                    config = json.loads(config_json) if config_json else {}
                    state_data = json.loads(state_data_json) if state_data_json else {}
                    
                    self.metrics.increment_counter("storage.sessions.retrieved")
                    return {
                        "session_id": session_id_db,
                        "config": config,
                        "state_data": state_data,
                        "is_active": is_active
                    }
                    
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
    
    # Aliases for browser session management
    async def store_browser_session(
        self,
        session_id: str,
        browser_config: Dict[str, Any],
        is_active: bool = True
    ) -> bool:
        """Store browser session with specific config format.
        
        Args:
            session_id: Session identifier
            browser_config: Browser configuration
            is_active: Whether session is active
            
        Returns:
            True if stored successfully
        """
        return await self.store_session(
            session_id_or_data=session_id,
            config=browser_config,
            state_data={"is_active": is_active}
        )
    
    async def update_browser_session(
        self,
        session_id: str,
        is_active: bool
    ) -> bool:
        """Update browser session status.
        
        Args:
            session_id: Session identifier
            is_active: Whether session is active
            
        Returns:
            True if updated successfully
        """
        with timer("storage.update_browser_session"):
            try:
                from sqlalchemy import text
                import json
                
                async with self.db_manager.get_session() as session:
                    # First, get the current state_data
                    select_stmt = text("""
                        SELECT state_data FROM browser_sessions 
                        WHERE session_id = :session_id
                    """)
                    result = await session.execute(select_stmt, {"session_id": session_id})
                    row = result.fetchone()
                    
                    if not row:
                        return False
                    
                    # Update state data
                    state_data = json.loads(row[0]) if row[0] else {}
                    state_data["is_active"] = is_active
                    
                    # Update session with new state
                    update_stmt = text("""
                        UPDATE browser_sessions 
                        SET state_data = :state_data, 
                            is_active = :is_active,
                            last_accessed = :current_time,
                            updated_at = :current_time
                        WHERE session_id = :session_id
                    """)
                    current_time = datetime.utcnow()
                    await session.execute(update_stmt, {
                        "state_data": json.dumps(state_data),
                        "is_active": is_active,
                        "current_time": current_time,
                        "session_id": session_id
                    })
                    await session.commit()
                    self.metrics.increment_counter("storage.sessions.updated")
                    return True
                    
            except Exception as e:
                self.metrics.increment_counter("storage.sessions.errors")
                self.logger.error(f"Failed to update session {session_id}: {e}")
                return False
    
    # ==================== JOB QUEUE MANAGEMENT ====================
    
    async def store_job(self, job_data: Dict[str, Any]) -> bool:
        """Store job data in the job queue.
        
        Args:
            job_data: Job data dictionary
            
        Returns:
            True if stored successfully
        """
        with timer("storage.store_job"):
            try:
                async with self.db_manager.get_session() as session:
                    job = JobQueue(
                        job_id=job_data.get("job_id"),
                        job_type=job_data.get("job_type"),
                        status=job_data.get("status", "pending"),
                        priority=job_data.get("priority", 0),
                        job_data=job_data.get("job_data"),
                        result_data=job_data.get("result_data")
                    )
                    session.add(job)
                    await session.commit()
                    self.metrics.increment_counter("storage.jobs.stored")
                    return True
                    
            except Exception as e:
                self.metrics.increment_counter("storage.jobs.errors")
                self.logger.error(f"Failed to store job {job_data.get('job_id', 'unknown')}: {e}")
                return False
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job data by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job data or None if not found
        """
        with timer("storage.get_job"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = select(JobQueue).where(JobQueue.job_id == job_id)
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()
                    
                    if not job:
                        return None
                    
                    self.metrics.increment_counter("storage.jobs.retrieved")
                    return job.to_dict()
                    
            except Exception as e:
                self.metrics.increment_counter("storage.jobs.errors")
                self.logger.error(f"Failed to get job {job_id}: {e}")
                return None
    
    async def update_job_status(self, job_id: str, status: str) -> bool:
        """Update job status.
        
        Args:
            job_id: Job identifier
            status: New status
            
        Returns:
            True if updated successfully
        """
        with timer("storage.update_job_status"):
            try:
                async with self.db_manager.get_session() as session:
                    stmt = update(JobQueue).where(JobQueue.job_id == job_id).values(
                        status=status,
                        updated_at=datetime.utcnow()
                    )
                    result = await session.execute(stmt)
                    await session.commit()
                    
                    if result.rowcount > 0:
                        self.metrics.increment_counter("storage.jobs.updated")
                        return True
                    return False
                    
            except Exception as e:
                self.metrics.increment_counter("storage.jobs.errors")
                self.logger.error(f"Failed to update job status {job_id}: {e}")
                return False

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
    
    async def store_performance_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store a performance metric."""
        if tags is None:
            tags = {}
        
        # For now, just log the metric - in a real system this would go to a metrics DB
        self.logger.info(f"Performance metric: {metric_name}={value} tags={tags}")
        
        # Store in cache for tests to retrieve
        cache_key = f"perf_metric_{metric_name}"
        metrics_list = await self.get_cached_result(cache_key) or []
        
        metric_entry = {
            "value": value,
            "tags": tags,
            "timestamp": datetime.utcnow().isoformat()
        }
        metrics_list.append(metric_entry)
        
        # Keep only last 100 metrics
        if len(metrics_list) > 100:
            metrics_list = metrics_list[-100:]
        
        await self.store_cached_result(cache_key, metrics_list, cache_ttl=86400)  # 24 hours
    
    async def get_performance_metrics(
        self, 
        metric_name: str, 
        tags: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get performance metrics by name and optional tags."""
        cache_key = f"perf_metric_{metric_name}"
        metrics_list = await self.get_cached_result(cache_key) or []
        
        if tags:
            # Filter by tags
            filtered_metrics = []
            for metric in metrics_list:
                metric_tags = metric.get("tags", {})
                if all(metric_tags.get(k) == v for k, v in tags.items()):
                    filtered_metrics.append(metric)
            return filtered_metrics
        
        return metrics_list
    
    async def store_scrape_results_batch(self, results_data: List[Dict[str, Any]]) -> List[str]:
        """Store multiple scrape results in a batch operation."""
        if not results_data:
            return []
        
        result_ids = []
        
        async with self.db_manager.get_session() as session:
            try:
                # Prepare batch data for bulk insert
                batch_data = []
                for result_data in results_data:
                    batch_data.append({
                        "url": result_data["url"],
                        "title": result_data.get("title", ""),
                        "success": result_data.get("success", True),
                        "status_code": result_data.get("status_code", 200),
                        "content_markdown": result_data.get("content_markdown", ""),
                        "content_html": result_data.get("content_html", ""),
                        "content_text": result_data.get("content_text", ""),
                        "extracted_data": json.dumps(result_data.get("extracted_data", {})),
                        "metadata": json.dumps(result_data.get("metadata", {})),
                        "created_at": result_data.get("created_at", datetime.utcnow())
                    })
                
                # Use bulk insert for better performance
                from sqlalchemy import insert
                result = await session.execute(
                    insert(CrawlResult).returning(CrawlResult.id),
                    batch_data
                )
                
                # Get all inserted IDs
                result_ids = [str(row.id) for row in result.fetchall()]
                
                await session.commit()
                self.logger.debug(f"Stored {len(results_data)} results in batch")
                
                return result_ids
                
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Failed to store batch results: {e}")
                raise ResourceError(f"Batch storage failed: {e}")
    
    async def clear_all_results(self) -> None:
        """Clear all stored results (for testing)."""
        async with self.db_manager.get_session() as session:
            try:
                # Delete all crawl results
                await session.execute(delete(CrawlResult))
                await session.execute(delete(CrawlLink))
                await session.execute(delete(CrawlMedia))
                await session.commit()
                
                self.logger.debug("Cleared all stored results")
                
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Failed to clear results: {e}")
                raise ResourceError(f"Clear operation failed: {e}")
    
    def get_connection(self):
        """Get database connection as async context manager."""
        return self.db_manager.get_session()


# Global storage manager instance
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """Get the global storage manager instance."""
    global _storage_manager
    if _storage_manager is None:
        # Get database path from config
        config_manager = get_config_manager()
        db_path = config_manager.get_setting("storage.database_path")
        _storage_manager = StorageManager(db_path=db_path)
    return _storage_manager


def reset_storage_manager() -> None:
    """Reset the global storage manager instance to pick up config changes."""
    global _storage_manager
    _storage_manager = None