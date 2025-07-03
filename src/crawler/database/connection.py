"""Database connection management for SQLite."""

import os
from pathlib import Path
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import StaticPool

from ..foundation.config import ConfigManager
from ..foundation.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages SQLite database connections and sessions."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        
    @property
    def database_url(self) -> str:
        """Get the database URL from configuration."""
        db_path = self.config_manager.get_setting(
            "storage.database_path", 
            "~/.crawler/crawler.db"
        )
        
        # Expand user path and ensure directory exists
        db_path = Path(db_path).expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        return f"sqlite+aiosqlite:///{db_path}"
    
    @property
    def engine(self) -> AsyncEngine:
        """Get or create the database engine."""
        if self._engine is None:
            self._engine = create_async_engine(
                self.database_url,
                echo=self.config_manager.get_setting("database.echo", False),
                poolclass=StaticPool,
                pool_pre_ping=True,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                },
            )
            logger.info(f"Created database engine: {self.database_url}")
        return self._engine
    
    @property
    def session_factory(self) -> async_sessionmaker:
        """Get or create the session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._session_factory
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session with automatic cleanup."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self) -> None:
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            logger.info("Database engine closed")
    
    async def setup_database(self) -> None:
        """Set up database with WAL mode and optimizations."""
        try:
            async with self.get_session() as session:
                # Enable WAL mode for better concurrency
                await session.execute("PRAGMA journal_mode=WAL")
                
                # Performance optimizations
                await session.execute("PRAGMA synchronous=NORMAL")
                await session.execute("PRAGMA cache_size=10000")
                await session.execute("PRAGMA temp_store=MEMORY")
                await session.execute("PRAGMA mmap_size=268435456")  # 256MB
                
                # Enable foreign keys
                await session.execute("PRAGMA foreign_keys=ON")
                
                await session.commit()
                logger.info("Database setup completed with optimizations")
                
        except Exception as e:
            logger.error(f"Failed to setup database: {e}")
            raise


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Convenience function to get a database session."""
    db_manager = get_database_manager()
    async with db_manager.get_session() as session:
        yield session