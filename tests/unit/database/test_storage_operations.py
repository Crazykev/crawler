"""Tests for SQLite storage operations - Phase 1 TDD Requirements."""

import pytest
import sqlite3
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.crawler.core.storage import StorageManager, get_storage_manager
from src.crawler.database.models.crawl_results import CrawlResult
from src.crawler.database.models.cache import CacheEntry
from src.crawler.database.models.sessions import BrowserSession
from src.crawler.foundation.errors import StorageError


@pytest.mark.database
class TestStorageManagerSQLite:
    """Test SQLite storage operations for Phase 1."""
    
    @pytest.mark.asyncio
    async def test_storage_manager_initialization(self, temp_dir):
        """Test SQLite database initialization - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        
        # RED: This should fail until proper SQLite initialization is implemented
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        assert db_path.exists()
        
        # Verify database schema exists
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check that all required Phase 1 tables exist
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [table[0] for table in tables]
        
        required_tables = [
            'crawl_results', 'cache_entries', 'browser_sessions', 'job_queue'
        ]
        for table in required_tables:
            assert table in table_names, f"Missing required table: {table}"
        
        conn.close()
    
    @pytest.mark.asyncio
    async def test_store_scrape_result_sqlite(self, temp_dir):
        """Test storing scrape result in SQLite - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        # RED: This should fail until scrape result storage is implemented
        result_data = {
            "url": "https://example.com",
            "title": "Example Page",
            "content": "Test content",
            "success": True,
            "status_code": 200,
            "extracted_data": {"test": "data"},
            "metadata": {"load_time": 1.5},
            "created_at": datetime.utcnow()
        }
        
        result_id = await storage_manager.store_scrape_result(result_data)
        
        assert result_id is not None
        assert isinstance(result_id, (int, str))
        
        # Verify data was actually stored
        stored_result = await storage_manager.get_scrape_result(result_id)
        assert stored_result is not None
        assert stored_result["url"] == "https://example.com"
        assert stored_result["title"] == "Example Page"
        assert stored_result["success"] is True
    
    @pytest.mark.asyncio
    async def test_cache_operations_sqlite(self, temp_dir):
        """Test SQLite cache operations - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        # RED: This should fail until cache operations are implemented
        cache_key = "test_cache_key"
        cache_data = {
            "url": "https://example.com",
            "content": "Cached content",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in cache
        await storage_manager.store_cache(cache_key, cache_data, ttl=3600)
        
        # Retrieve from cache
        retrieved = await storage_manager.get_cache(cache_key)
        assert retrieved is not None
        assert retrieved["url"] == "https://example.com"
        assert retrieved["content"] == "Cached content"
        
        # Test cache expiration
        expired_key = "expired_key"
        await storage_manager.store_cache(expired_key, cache_data, ttl=-1)  # Already expired
        expired_result = await storage_manager.get_cache(expired_key)
        assert expired_result is None
    
    @pytest.mark.asyncio
    async def test_session_persistence_sqlite(self, temp_dir):
        """Test browser session persistence - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        # RED: This should fail until session persistence is implemented
        session_data = {
            "session_id": "test_session_123",
            "config": {
                "headless": True,
                "timeout": 30
            },
            "state_data": {
                "cookies": [{"name": "test", "value": "cookie"}],
                "local_storage": {}
            },
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1)
        }
        
        # Store session
        await storage_manager.store_session(session_data)
        
        # Retrieve session
        retrieved_session = await storage_manager.get_session("test_session_123")
        assert retrieved_session is not None
        assert retrieved_session["session_id"] == "test_session_123"
        assert retrieved_session["config"]["headless"] is True
        
        # Test session cleanup
        cleanup_count = await storage_manager.cleanup_expired_sessions()
        assert cleanup_count >= 0
    
    @pytest.mark.asyncio
    async def test_job_queue_sqlite(self, temp_dir):
        """Test job queue in SQLite - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        # RED: This should fail until job queue is implemented
        job_data = {
            "job_id": "test_job_456",
            "job_type": "scrape_single",
            "status": "pending",
            "priority": 1,
            "job_data": {
                "url": "https://example.com",
                "options": {"timeout": 30}
            },
            "created_at": datetime.utcnow()
        }
        
        # Store job
        await storage_manager.store_job(job_data)
        
        # Retrieve job
        retrieved_job = await storage_manager.get_job("test_job_456")
        assert retrieved_job is not None
        assert retrieved_job["job_id"] == "test_job_456"
        assert retrieved_job["status"] == "pending"
        
        # Update job status
        await storage_manager.update_job_status("test_job_456", "completed")
        updated_job = await storage_manager.get_job("test_job_456")
        assert updated_job["status"] == "completed"
    
    def test_sqlite_wal_mode_enabled(self, temp_dir):
        """Test SQLite WAL mode is enabled for concurrency - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        storage_manager = StorageManager(db_path=str(db_path))
        
        # RED: This should fail until WAL mode is properly configured
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check WAL mode is enabled
        journal_mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.upper() == "WAL", f"Expected WAL mode, got {journal_mode}"
        
        conn.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self, temp_dir):
        """Test concurrent SQLite operations - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        # RED: This should fail until proper concurrency handling is implemented
        async def store_multiple_results():
            tasks = []
            for i in range(10):
                result_data = {
                    "url": f"https://example.com/{i}",
                    "title": f"Page {i}",
                    "content": f"Content {i}",
                    "success": True,
                    "status_code": 200,
                    "created_at": datetime.utcnow()
                }
                tasks.append(storage_manager.store_scrape_result(result_data))
            
            return await asyncio.gather(*tasks)
        
        # Should handle concurrent operations without errors
        import asyncio
        result_ids = await store_multiple_results()
        assert len(result_ids) == 10
        assert all(rid is not None for rid in result_ids)
    
    @pytest.mark.asyncio
    async def test_storage_error_handling(self, temp_dir):
        """Test storage error handling - Phase 1 requirement."""
        # Use invalid database path to trigger errors
        invalid_path = "/invalid/path/database.db"
        
        # RED: This should fail until proper error handling is implemented
        with pytest.raises(StorageError):
            storage_manager = StorageManager(db_path=invalid_path)
    
    @pytest.mark.asyncio
    async def test_database_migration_support(self, temp_dir):
        """Test database migration support - Phase 1 requirement."""
        db_path = temp_dir / "test.db"
        
        # RED: This should fail until migration system is implemented
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        # Check migration tracking table exists
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [table[0] for table in tables]
        
        # Should have migration tracking
        assert "alembic_version" in table_names or "migration_versions" in table_names
        
        conn.close()


@pytest.mark.integration
class TestStorageIntegration:
    """Integration tests for storage operations."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_storage_workflow(self, temp_dir):
        """Test complete storage workflow - Phase 1 integration."""
        db_path = temp_dir / "integration.db"
        storage_manager = StorageManager(db_path=str(db_path))
        await storage_manager.initialize()
        
        # RED: This should fail until full workflow is implemented
        # 1. Store a scrape result
        result_data = {
            "url": "https://example.com",
            "title": "Integration Test",
            "content": "Test content for integration",
            "success": True,
            "status_code": 200,
            "created_at": datetime.utcnow()
        }
        
        result_id = await storage_manager.store_scrape_result(result_data)
        
        # 2. Cache the result
        cache_key = f"result_{result_id}"
        await storage_manager.store_cache(cache_key, result_data, ttl=3600)
        
        # 3. Create a session
        session_data = {
            "session_id": "integration_session",
            "config": {"headless": True},
            "state_data": {},
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1)
        }
        await storage_manager.store_session(session_data)
        
        # 4. Verify everything is stored and retrievable
        stored_result = await storage_manager.get_scrape_result(result_id)
        cached_result = await storage_manager.get_cache(cache_key)
        stored_session = await storage_manager.get_session("integration_session")
        
        assert stored_result is not None
        assert cached_result is not None
        assert stored_session is not None
        
        # 5. Cleanup operations
        cleanup_cache = await storage_manager.cleanup_expired_cache()
        cleanup_sessions = await storage_manager.cleanup_expired_sessions()
        
        assert cleanup_cache >= 0
        assert cleanup_sessions >= 0


# These tests represent the TDD RED phase for Phase 1 SQLite storage
# They should FAIL initially and guide implementation of storage layer