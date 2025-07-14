"""Edge case tests for database operations."""

import pytest
import pytest_asyncio
import asyncio
import sqlite3
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.crawler.database.connection import DatabaseManager
from src.crawler.core.storage import StorageManager
from src.crawler.foundation.errors import StorageError, ValidationError


@pytest.mark.database
class TestDatabaseEdgeCases:
    """Test edge cases and boundary conditions for database operations."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield f.name
        # Cleanup
        try:
            os.unlink(f.name)
        except FileNotFoundError:
            pass

    @pytest_asyncio.fixture
    async def storage_manager(self, temp_db_path):
        """Create a storage manager with temporary database."""
        manager = StorageManager()
        manager.db_path = temp_db_path
        await manager.initialize()
        yield manager
        await manager.cleanup()

    @pytest.mark.asyncio
    async def test_database_connection_pool_exhaustion(self, temp_db_path):
        """Test behavior when database connection pool is exhausted."""
        # SQLite has a default limit, let's simulate exhaustion
        connections = []
        
        try:
            # Create many connections rapidly
            for i in range(100):
                conn = sqlite3.connect(temp_db_path)
                connections.append(conn)
                
            # Try to create one more connection - should work for SQLite
            # but test we handle potential limits gracefully
            storage_manager = StorageManager()
            storage_manager.db_path = temp_db_path
            
            # This should not raise an error
            await storage_manager.initialize()
            
            # Test that we can still perform operations
            result = await storage_manager.store_crawl_result(
                "https://example.com",
                content_markdown="Test content",
                title="Test",
                success=True
            )
            
            assert result is not None
            
        finally:
            # Cleanup connections
            for conn in connections:
                conn.close()

    @pytest.mark.asyncio
    async def test_concurrent_transaction_deadlock_resolution(self, storage_manager):
        """Test handling of concurrent transactions that might deadlock."""
        
        async def concurrent_store(index):
            """Store a result concurrently."""
            try:
                return await storage_manager.store_crawl_result(
                    f"https://example.com/{index}",
                    content_markdown=f"Content {index}",
                    title=f"Title {index}",
                    success=True
                )
            except Exception as e:
                # Should not deadlock - return error info
                return f"Error: {str(e)}"
        
        # Run many concurrent operations
        tasks = [concurrent_store(i) for i in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most should succeed, any failures should be handled gracefully
        successful_results = [r for r in results if isinstance(r, str) and not str(r).startswith("Error")]
        error_results = [r for r in results if isinstance(r, (str, Exception)) and str(r).startswith("Error")]
        
        # At least 80% should succeed
        assert len(successful_results) >= 40, f"Too many failures: {len(error_results)} errors. Successful: {len(successful_results)}, Errors: {error_results[:5]}"

    @pytest.mark.asyncio
    async def test_database_corruption_recovery(self, temp_db_path):
        """Test recovery from database corruption."""
        # Create a valid database first
        storage_manager = StorageManager()
        storage_manager.db_path = temp_db_path
        await storage_manager.initialize()
        
        # Store some data
        await storage_manager.store_crawl_result(
            "https://example.com",
            content_markdown="Test content",
            title="Test",
            success=True
        )
        
        await storage_manager.cleanup()
        
        # Corrupt the database file
        with open(temp_db_path, 'w') as f:
            f.write("This is not a valid SQLite database")
        
        # Try to initialize again - should handle corruption gracefully
        storage_manager2 = StorageManager()
        storage_manager2.db_path = temp_db_path
        
        # This should either recreate the database or raise a clear error
        try:
            await storage_manager2.initialize()
            # If it succeeds, it should have recreated the database
            assert os.path.exists(temp_db_path)
        except StorageError as e:
            # Should raise a clear database error, not a generic exception
            assert "database" in str(e).lower() or "corrupt" in str(e).lower()

    @pytest.mark.asyncio
    async def test_disk_space_exhaustion_simulation(self, temp_db_path):
        """Test behavior when disk space is exhausted."""
        storage_manager = StorageManager()
        storage_manager.db_path = temp_db_path
        await storage_manager.initialize()
        
        # Mock SQLAlchemy session to simulate disk full error
        from sqlalchemy.exc import OperationalError
        from unittest.mock import AsyncMock
        with patch.object(storage_manager.db_manager, 'get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.add = Mock()
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=OperationalError("database or disk is full", None, None))
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None
            
            # This should raise a clear error about disk space
            with pytest.raises(StorageError) as exc_info:
                await storage_manager.store_scrape_result(
                    "https://example.com",
                    content_markdown="Test content",
                    title="Test",
                    success=True
                )
            
            assert "disk" in str(exc_info.value).lower() or "space" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_wal_checkpoint_during_heavy_load(self, storage_manager):
        """Test WAL checkpoint behavior during heavy database load."""
        
        # Store many records to build up WAL file
        async def store_batch(batch_size=10):
            tasks = []
            for i in range(batch_size):
                task = storage_manager.store_crawl_result(
                    f"https://example.com/batch/{i}",
                    content_markdown=f"Batch content {i}",
                    title=f"Batch {i}",
                    success=True
                )
                tasks.append(task)
            return await asyncio.gather(*tasks)
        
        # Store several batches
        for batch in range(5):
            await store_batch(20)
        
        # Verify that all data was stored successfully
        # This tests that WAL checkpointing didn't interfere with operations
        db_path = storage_manager.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        result = cursor.execute("SELECT COUNT(*) FROM crawl_results").fetchone()
        assert result[0] == 100  # 5 batches × 20 records each
        
        conn.close()

    @pytest.mark.asyncio
    async def test_vacuum_operation_with_active_connections(self, storage_manager):
        """Test VACUUM operation behavior with active connections."""
        
        # Store some data
        await storage_manager.store_crawl_result(
            "https://example.com",
            content_markdown="Test content",
            title="Test",
            success=True
        )
        
        # Delete some data to create space that could be reclaimed
        db_path = storage_manager.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crawl_results WHERE url = ?", ("https://example.com",))
        conn.commit()
        conn.close()
        
        # Try to vacuum while storage manager is active
        try:
            vacuum_conn = sqlite3.connect(db_path)
            vacuum_cursor = vacuum_conn.cursor()
            vacuum_cursor.execute("VACUUM")
            vacuum_conn.close()
            
            # Should complete without error
            assert True
        except sqlite3.OperationalError as e:
            # If vacuum fails due to active connections, that's expected
            # The test verifies we handle this gracefully
            assert "database is locked" in str(e).lower()

    @pytest.mark.asyncio
    async def test_large_blob_storage_limits(self, storage_manager):
        """Test storage of very large content blobs."""
        
        # Create a large content string (1MB)
        large_content = "x" * (1024 * 1024)
        
        # This should succeed for reasonable sizes
        result = await storage_manager.store_crawl_result(
            "https://example.com/large",
            content_markdown=large_content,
            title="Large Content Test",
            success=True
        )
        
        assert result is not None
        
        # Verify the content was stored correctly
        db_path = storage_manager.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        stored_content = cursor.execute(
            "SELECT content_markdown FROM crawl_results WHERE url = ?",
            ("https://example.com/large",)
        ).fetchone()
        
        assert stored_content[0] == large_content
        conn.close()

    @pytest.mark.asyncio
    async def test_database_migration_failure_rollback(self, temp_db_path):
        """Test rollback behavior when database migration fails."""
        
        # Create a database with old schema
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE old_table (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
        """)
        cursor.execute("INSERT INTO old_table (data) VALUES ('test')")
        conn.commit()
        conn.close()
        
        # Mock a migration that fails
        with patch('src.crawler.database.connection.DatabaseManager.initialize') as mock_init:
            mock_init.side_effect = sqlite3.OperationalError("Migration failed")
            
            storage_manager = StorageManager()
            storage_manager.db_path = temp_db_path
            
            # Migration should fail gracefully
            with pytest.raises(Exception):  # Could be OperationalError or StorageError
                await storage_manager.initialize()

    @pytest.mark.asyncio
    async def test_concurrent_schema_changes(self, temp_db_path):
        """Test handling of concurrent schema changes."""
        
        # Initialize first storage manager
        storage_manager1 = StorageManager()
        storage_manager1.db_path = temp_db_path
        await storage_manager1.initialize()
        
        # Try to initialize another storage manager on same database
        storage_manager2 = StorageManager()
        storage_manager2.db_path = temp_db_path
        
        # This should work - both should use the same schema
        await storage_manager2.initialize()
        
        # Both should be able to store data
        result1 = await storage_manager1.store_crawl_result(
            "https://example1.com",
            content_markdown="Content 1",
            title="Test 1",
            success=True
        )
        
        result2 = await storage_manager2.store_crawl_result(
            "https://example2.com",
            content_markdown="Content 2",
            title="Test 2",
            success=True
        )
        
        assert result1 is not None
        assert result2 is not None
        
        await storage_manager1.cleanup()
        await storage_manager2.cleanup()

    @pytest.mark.asyncio
    async def test_invalid_sql_injection_prevention(self, storage_manager):
        """Test that SQL injection attempts are properly handled."""
        
        # Try to store content with SQL injection attempts
        malicious_content = "'; DROP TABLE crawl_results; --"
        malicious_url = "https://example.com'; DROP TABLE crawl_results; --"
        
        # These should be safely escaped/parameterized
        result = await storage_manager.store_crawl_result(
            malicious_url,
            content_markdown=malicious_content,
            title="Malicious Content",
            success=True
        )
        
        assert result is not None
        
        # Verify the table still exists and contains the data
        db_path = storage_manager.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Table should still exist
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [table[0] for table in tables]
        assert "crawl_results" in table_names
        
        # Data should be stored safely
        result = cursor.execute("SELECT url, content_markdown FROM crawl_results").fetchall()
        assert len(result) > 0
        assert malicious_url in result[0][0]
        assert malicious_content in result[0][1]
        
        conn.close()


@pytest_asyncio.fixture
async def performance_storage_manager():
    """Create a storage manager with temporary database for performance tests."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    manager = StorageManager()
    manager.db_path = db_path
    await manager.initialize()
    yield manager
    await manager.cleanup()
    
    # Cleanup
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.mark.database
class TestDatabasePerformanceEdgeCases:
    """Test performance-related edge cases for database operations."""

    @pytest.mark.asyncio
    async def test_bulk_insert_performance(self, performance_storage_manager):
        """Test performance of bulk insert operations."""
        import time
        
        # Insert many records and measure time
        start_time = time.time()
        
        tasks = []
        for i in range(100):
            task = performance_storage_manager.store_crawl_result(
                f"https://example.com/bulk/{i}",
                content_markdown=f"Bulk content {i}",
                title=f"Bulk {i}",
                success=True
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # All inserts should succeed
        assert len(results) == 100
        assert all(r is not None for r in results)
        
        # Should complete in reasonable time (less than 10 seconds)
        duration = end_time - start_time
        assert duration < 10, f"Bulk insert took too long: {duration:.2f}s"

    @pytest.mark.asyncio
    async def test_large_result_set_retrieval(self, performance_storage_manager):
        """Test retrieval of large result sets."""
        
        # Store many records
        for i in range(1000):
            await performance_storage_manager.store_crawl_result(
                f"https://example.com/large_set/{i}",
                content_markdown=f"Content {i}",
                title=f"Title {i}",
                success=True
            )
        
        # Try to retrieve all results
        import time
        start_time = time.time()
        
        # This would typically be done through a proper API
        # For now, test direct database access
        db_path = performance_storage_manager.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        results = cursor.execute("SELECT * FROM crawl_results").fetchall()
        end_time = time.time()
        
        assert len(results) == 1000
        
        # Should complete in reasonable time
        duration = end_time - start_time
        assert duration < 5, f"Large result set retrieval took too long: {duration:.2f}s"
        
        conn.close()

    @pytest.mark.asyncio
    async def test_database_size_monitoring(self, performance_storage_manager):
        """Test monitoring of database size growth."""
        
        # Get initial size
        initial_size = os.path.getsize(performance_storage_manager.db_path)
        
        # Store data with significant content
        large_content = "x" * 10000  # 10KB per record
        
        for i in range(100):
            await performance_storage_manager.store_crawl_result(
                f"https://example.com/size_test/{i}",
                content_markdown=large_content,
                title=f"Size Test {i}",
                success=True
            )
        
        # Check final size
        final_size = os.path.getsize(performance_storage_manager.db_path)
        
        # Database should have grown significantly
        size_increase = final_size - initial_size
        assert size_increase > 500000  # At least 500KB increase
        
        # But not excessively (should be compressed/efficient)
        assert size_increase < 2000000  # Less than 2MB increase