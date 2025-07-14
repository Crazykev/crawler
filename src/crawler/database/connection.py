"""Database connection management for SQLite."""

import os
from pathlib import Path
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
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
        
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            from src.crawler.foundation.errors import StorageError
            raise StorageError(f"Failed to create database directory {db_path.parent}: {e}")
        
        return f"sqlite+aiosqlite:///{db_path}"
    
    @property
    def engine(self) -> AsyncEngine:
        """Get or create the database engine."""
        if self._engine is None:
            # Configure SQLite for optimal performance with WAL mode
            connect_args = {
                "check_same_thread": False,
                "timeout": 30,
            }
            
            self._engine = create_async_engine(
                self.database_url,
                echo=self.config_manager.get_setting("database.echo", False),
                poolclass=StaticPool,
                pool_pre_ping=False,  # Disable pre-ping to avoid greenlet issues
                pool_recycle=-1,  # Don't recycle connections
                connect_args=connect_args,
            )
            
            # Set up WAL mode and other optimizations on connection
            @event.listens_for(self._engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                # Performance optimizations
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            
            logger.info(f"Created database engine with WAL mode: {self.database_url}")
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
        session = self.session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
        finally:
            try:
                await session.close()
            except Exception as e:
                # Log but don't raise connection cleanup errors
                logger.warning(f"Failed to close session cleanly: {e}")
    
    async def initialize(self) -> None:
        """Initialize the database with tables and optimizations."""
        try:
            # Import all models to ensure they're registered with Base
            from .models import (
                Base, CrawlResult, CrawlLink, CrawlMedia,
                BrowserSession, CacheEntry, JobQueue
            )
            
            # Create all tables if they don't exist
            logger.info(f"Creating tables from metadata: {list(Base.metadata.tables.keys())}")
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Tables created successfully")
            
            # Create migration tracking table for Phase 1 requirement
            await self.create_migration_table()
            logger.info("Migration tracking table created")
            
            # Setup database optimizations
            await self.setup_database()
            
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self) -> None:
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            logger.info("Database engine closed")
    
    async def setup_database(self) -> None:
        """Set up database with WAL mode and optimizations."""
        try:
            from sqlalchemy import text
            
            async with self.get_session() as session:
                # Enable WAL mode for better concurrency
                await session.execute(text("PRAGMA journal_mode=WAL"))
                
                # Performance optimizations
                await session.execute(text("PRAGMA synchronous=NORMAL"))
                await session.execute(text("PRAGMA cache_size=10000"))
                await session.execute(text("PRAGMA temp_store=MEMORY"))
                await session.execute(text("PRAGMA mmap_size=268435456"))  # 256MB
                
                # Enable foreign keys
                await session.execute(text("PRAGMA foreign_keys=ON"))
                
                await session.commit()
                logger.info("Database setup completed with optimizations")
                
        except Exception as e:
            logger.error(f"Failed to setup database: {e}")
            raise
    
    async def create_migration_table(self) -> None:
        """Create migration tracking table for Phase 1 requirement."""
        try:
            from sqlalchemy import text
            
            async with self.get_session() as session:
                # Create a simple migration tracking table
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS migration_versions (
                        version_num VARCHAR(32) PRIMARY KEY,
                        is_applied BOOLEAN NOT NULL DEFAULT TRUE,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Insert current version as applied
                await session.execute(text("""
                    INSERT OR IGNORE INTO migration_versions (version_num, is_applied) 
                    VALUES ('phase1_initial', TRUE)
                """))
                
                await session.commit()
                logger.info("Migration tracking table created and initialized")
                
        except Exception as e:
            logger.error(f"Failed to create migration table: {e}")
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