"""Service for managing browser sessions."""

import asyncio
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..core import get_storage_manager
from ..foundation.config import get_config_manager
from ..foundation.logging import get_logger
from ..foundation.errors import (
    handle_error, ValidationError, ResourceError, ErrorContext
)
from ..foundation.metrics import get_metrics_collector, timer


@dataclass
class SessionConfig:
    """Configuration for browser sessions."""
    browser_type: str = "chromium"
    headless: bool = True
    timeout: int = 30
    user_agent: Optional[str] = None
    proxy_url: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    viewport_width: int = 1920
    viewport_height: int = 1080
    extra_options: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "browser_type": self.browser_type,
            "headless": self.headless,
            "timeout": self.timeout,
            "user_agent": self.user_agent,
            "proxy_url": self.proxy_url,
            "proxy_username": self.proxy_username,
            "proxy_password": self.proxy_password,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "extra_options": self.extra_options
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionConfig":
        """Create from dictionary."""
        return cls(
            browser_type=data.get("browser_type", "chromium"),
            headless=data.get("headless", True),
            timeout=data.get("timeout", 30),
            user_agent=data.get("user_agent"),
            proxy_url=data.get("proxy_url"),
            proxy_username=data.get("proxy_username"),
            proxy_password=data.get("proxy_password"),
            viewport_width=data.get("viewport_width", 1920),
            viewport_height=data.get("viewport_height", 1080),
            extra_options=data.get("extra_options", {})
        )


@dataclass
class Session:
    """Represents a browser session."""
    session_id: str
    config: SessionConfig
    created_at: datetime
    last_accessed: datetime
    page_count: int = 0
    is_active: bool = True
    state_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "config": self.config.to_dict(),
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "page_count": self.page_count,
            "is_active": self.is_active,
            "state_data": self.state_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            config=SessionConfig.from_dict(data["config"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            page_count=data.get("page_count", 0),
            is_active=data.get("is_active", True),
            state_data=data.get("state_data", {})
        )
    
    def is_expired(self, timeout_seconds: int = 1800) -> bool:
        """Check if session has expired.
        
        Args:
            timeout_seconds: Session timeout in seconds
            
        Returns:
            True if session has expired
        """
        timeout = timedelta(seconds=timeout_seconds)
        return (datetime.utcnow() - self.last_accessed) > timeout
    
    def update_access(self) -> None:
        """Update last accessed time and increment page count."""
        self.last_accessed = datetime.utcnow()
        self.page_count += 1


class SessionService:
    """Service for managing browser sessions."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = get_config_manager()
        self.metrics = get_metrics_collector()
        self.storage_manager = get_storage_manager()
        
        # In-memory session cache for active sessions
        self._active_sessions: Dict[str, Session] = {}
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 300  # 5 minutes
    
    async def initialize(self) -> None:
        """Initialize the session service."""
        try:
            # Initialize storage manager
            await self.storage_manager.initialize()
            
            # Load existing sessions from storage
            await self._load_sessions_from_storage()
            
            # Start background cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            self.logger.info("Session service initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize session service: {e}"
            self.logger.error(error_msg)
            handle_error(ResourceError(error_msg, resource_type="session_service"))
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the session service and cleanup resources."""
        try:
            # Cancel cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close all active sessions
            session_ids = list(self._active_sessions.keys())
            for session_id in session_ids:
                await self.close_session(session_id)
            
            self.logger.info("Session service shutdown completed")
        except Exception as e:
            self.logger.error(f"Error during session service shutdown: {e}")
    
    async def create_session(
        self,
        session_config: Optional[SessionConfig] = None,
        session_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ) -> str:
        """Create a new browser session.
        
        Args:
            session_config: Session configuration
            session_id: Optional custom session ID
            timeout_seconds: Session timeout in seconds
            
        Returns:
            Session ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if session_config is None:
            session_config = self._get_default_session_config()
        
        if timeout_seconds is None:
            timeout_seconds = self.config_manager.get_setting("storage.session_timeout", 1800)
        
        context = ErrorContext(
            operation="create_session",
            session_id=session_id
        )
        
        with timer("session_service.create_session"):
            try:
                # Check if session ID already exists
                if session_id in self._active_sessions:
                    raise ValidationError(f"Session {session_id} already exists")
                
                # Create session object
                now = datetime.utcnow()
                session = Session(
                    session_id=session_id,
                    config=session_config,
                    created_at=now,
                    last_accessed=now
                )
                
                # Store in memory and database
                self._active_sessions[session_id] = session
                
                expires_at = now + timedelta(seconds=timeout_seconds)
                await self.storage_manager.store_session(
                    session_id=session_id,
                    config=session_config.to_dict(),
                    state_data=session.state_data,
                    expires_at=expires_at
                )
                
                # Update metrics
                self.metrics.increment_counter("session_service.sessions.created")
                self.metrics.set_gauge("session_service.sessions.active", len(self._active_sessions))
                
                self.logger.info(f"Created session {session_id}")
                return session_id
                
            except Exception as e:
                self.metrics.increment_counter("session_service.sessions.create_errors")
                error_msg = f"Failed to create session: {e}"
                self.logger.error(error_msg)
                handle_error(e, context)
                raise
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a browser session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session object or None if not found
        """
        with timer("session_service.get_session"):
            try:
                # Check memory cache first
                session = self._active_sessions.get(session_id)
                if session:
                    # Check if expired
                    session_timeout = self.config_manager.get_setting("storage.session_timeout", 1800)
                    if session.is_expired(session_timeout):
                        await self.close_session(session_id)
                        return None
                    
                    # Update access time
                    session.update_access()
                    
                    # Update in storage
                    await self.storage_manager.store_session(
                        session_id=session_id,
                        config=session.config.to_dict(),
                        state_data=session.state_data
                    )
                    
                    self.metrics.increment_counter("session_service.sessions.accessed")
                    return session
                
                # Try to load from storage
                session_data = await self.storage_manager.get_session(session_id)
                if session_data:
                    # Reconstruct session object
                    session = Session.from_dict(session_data)
                    
                    # Check if expired
                    session_timeout = self.config_manager.get_setting("storage.session_timeout", 1800)
                    if session.is_expired(session_timeout):
                        await self.close_session(session_id)
                        return None
                    
                    # Add to memory cache
                    self._active_sessions[session_id] = session
                    session.update_access()
                    
                    self.metrics.increment_counter("session_service.sessions.loaded")
                    return session
                
                return None
                
            except Exception as e:
                self.logger.error(f"Failed to get session {session_id}: {e}")
                return None
    
    async def close_session(self, session_id: str) -> bool:
        """Close a browser session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if closed successfully
        """
        with timer("session_service.close_session"):
            try:
                # Remove from memory cache
                session = self._active_sessions.pop(session_id, None)
                
                # Remove from storage
                deleted = await self.storage_manager.delete_session(session_id)
                
                if session or deleted:
                    self.metrics.increment_counter("session_service.sessions.closed")
                    self.metrics.set_gauge("session_service.sessions.active", len(self._active_sessions))
                    self.logger.info(f"Closed session {session_id}")
                    return True
                
                return False
                
            except Exception as e:
                self.logger.error(f"Failed to close session {session_id}: {e}")
                return False
    
    async def list_sessions(
        self,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """List all sessions.
        
        Args:
            include_inactive: Whether to include inactive sessions
            
        Returns:
            List of session information
        """
        with timer("session_service.list_sessions"):
            try:
                sessions = []
                
                # Add active sessions from memory
                for session in self._active_sessions.values():
                    if session.is_active or include_inactive:
                        sessions.append(session.to_dict())
                
                # If including inactive, also check storage
                # (This would require additional storage methods to list all sessions)
                
                self.metrics.increment_counter("session_service.sessions.listed")
                return sessions
                
            except Exception as e:
                self.logger.error(f"Failed to list sessions: {e}")
                return []
    
    async def update_session_state(
        self,
        session_id: str,
        state_data: Dict[str, Any]
    ) -> bool:
        """Update session state data.
        
        Args:
            session_id: Session identifier
            state_data: State data to update
            
        Returns:
            True if updated successfully
        """
        with timer("session_service.update_session_state"):
            try:
                session = await self.get_session(session_id)
                if not session:
                    return False
                
                # Update state data
                session.state_data.update(state_data)
                session.last_accessed = datetime.utcnow()
                
                # Save to storage
                await self.storage_manager.store_session(
                    session_id=session_id,
                    config=session.config.to_dict(),
                    state_data=session.state_data
                )
                
                self.metrics.increment_counter("session_service.sessions.state_updated")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to update session state for {session_id}: {e}")
                return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        with timer("session_service.cleanup_expired_sessions"):
            try:
                session_timeout = self.config_manager.get_setting("storage.session_timeout", 1800)
                cleaned_count = 0
                
                # Check active sessions in memory
                expired_session_ids = []
                for session_id, session in self._active_sessions.items():
                    if session.is_expired(session_timeout):
                        expired_session_ids.append(session_id)
                
                # Close expired sessions
                for session_id in expired_session_ids:
                    if await self.close_session(session_id):
                        cleaned_count += 1
                
                # Clean up expired sessions from storage
                storage_cleaned = await self.storage_manager.cleanup_expired_sessions()
                cleaned_count += storage_cleaned
                
                if cleaned_count > 0:
                    self.logger.info(f"Cleaned up {cleaned_count} expired sessions")
                    self.metrics.record_metric("session_service.sessions.cleaned", cleaned_count)
                
                return cleaned_count
                
            except Exception as e:
                self.logger.error(f"Failed to cleanup expired sessions: {e}")
                return 0
    
    async def get_session_statistics(self) -> Dict[str, Any]:
        """Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        try:
            now = datetime.utcnow()
            session_timeout = self.config_manager.get_setting("storage.session_timeout", 1800)
            
            stats = {
                "total_active": len(self._active_sessions),
                "total_created": self.metrics.get_counter_value("session_service.sessions.created"),
                "total_closed": self.metrics.get_counter_value("session_service.sessions.closed"),
                "session_details": []
            }
            
            # Add details for each active session
            for session in self._active_sessions.values():
                age_seconds = (now - session.created_at).total_seconds()
                idle_seconds = (now - session.last_accessed).total_seconds()
                
                session_detail = {
                    "session_id": session.session_id,
                    "age_seconds": age_seconds,
                    "idle_seconds": idle_seconds,
                    "page_count": session.page_count,
                    "is_expired": session.is_expired(session_timeout),
                    "config": {
                        "browser_type": session.config.browser_type,
                        "headless": session.config.headless,
                        "timeout": session.config.timeout
                    }
                }
                stats["session_details"].append(session_detail)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get session statistics: {e}")
            return {"error": str(e)}
    
    def _get_default_session_config(self) -> SessionConfig:
        """Get default session configuration from settings.
        
        Returns:
            Default session configuration
        """
        return SessionConfig(
            browser_type="chromium",
            headless=self.config_manager.get_setting("browser.headless", True),
            timeout=self.config_manager.get_setting("scrape.timeout", 30),
            user_agent=self.config_manager.get_setting("browser.user_agent", "Crawler/1.0"),
            proxy_url=self.config_manager.get_setting("browser.proxy_url"),
            proxy_username=self.config_manager.get_setting("browser.proxy_username"),
            proxy_password=self.config_manager.get_setting("browser.proxy_password"),
            viewport_width=self.config_manager.get_setting("browser.viewport_width", 1920),
            viewport_height=self.config_manager.get_setting("browser.viewport_height", 1080)
        )
    
    async def _load_sessions_from_storage(self) -> None:
        """Load existing sessions from storage into memory."""
        try:
            # Note: This would require additional storage methods to list all sessions
            # For now, sessions will be loaded on-demand when accessed
            pass
        except Exception as e:
            self.logger.error(f"Failed to load sessions from storage: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup of expired sessions."""
        self.logger.info("Session cleanup loop started")
        
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                
                try:
                    await self.cleanup_expired_sessions()
                except Exception as e:
                    self.logger.error(f"Error in session cleanup loop: {e}")
                
        except asyncio.CancelledError:
            self.logger.info("Session cleanup loop cancelled")
        except Exception as e:
            self.logger.error(f"Session cleanup loop error: {e}")


# Global session service instance
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """Get the global session service instance."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service