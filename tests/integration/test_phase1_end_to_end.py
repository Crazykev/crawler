"""End-to-end integration tests for Phase 1 functionality."""

import pytest
import asyncio
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from click.testing import CliRunner
from unittest.mock import Mock, AsyncMock, patch

from src.crawler.cli.main import cli
from src.crawler.core import get_crawl_engine, get_storage_manager, get_job_manager
from src.crawler.services import get_scrape_service
from src.crawler.foundation.config import get_config_manager


@pytest.mark.integration
@pytest.mark.slow
class TestPhase1EndToEndWorkflows:
    """End-to-end tests for complete Phase 1 workflows."""
    
    def test_cli_scrape_to_file_complete_workflow(self, cli_runner, temp_dir):
        """Test complete CLI scrape to file workflow - Phase 1 integration."""
        output_file = temp_dir / "e2e_output.json"
        
        # RED: This should fail until complete workflow is implemented
        result = cli_runner.invoke(cli, [
            'scrape',
            'https://httpbin.org/json',  # Reliable test endpoint
            '--format', 'json',
            '--output', str(output_file),
            '--timeout', '30'
        ])
        
        # Verify CLI command succeeded
        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        
        # Verify output file was created
        assert output_file.exists(), "Output file was not created"
        
        # Verify file content is valid and complete
        content = json.loads(output_file.read_text())
        assert isinstance(content, dict)
        assert "success" in content
        assert content["success"] is True
        assert "url" in content
        assert "content" in content or "extracted_data" in content
        assert "timestamp" in content or "created_at" in content
    
    def test_cli_scrape_with_database_storage(self, cli_runner, temp_dir, mock_crawl4ai):
        """Test CLI scrape with database storage - Phase 1 integration."""
        config_file = temp_dir / "test_config.yaml"
        db_file = temp_dir / "test.db"
        
        # Reset global singletons to ensure clean state
        from src.crawler.core.storage import reset_storage_manager
        from src.crawler.services.scrape import reset_scrape_service
        from src.crawler.core.engine import reset_crawl_engine
        
        reset_storage_manager()
        # Reset other singletons if they exist
        try:
            reset_scrape_service()
        except:
            pass
        try:
            reset_crawl_engine()
        except:
            pass
        
        # Create config that specifies database location
        config_content = f"""
version: "1.0"
storage:
  database_path: "{db_file}"
  results_dir: "{temp_dir / 'results'}"
scrape:
  timeout: 30
  headless: true
  cache_enabled: true
"""
        config_file.write_text(config_content)
        
        # RED: This should fail until database integration is complete
        result = cli_runner.invoke(cli, [
            '--config', str(config_file),
            'scrape',
            'https://httpbin.org/uuid',
            '--format', 'json'
        ])
        
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        
        # Verify database was created and contains data
        assert db_file.exists(), "Database file was not created"
        
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        # Check that crawl_results table has data
        results = cursor.execute("SELECT * FROM crawl_results").fetchall()
        assert len(results) > 0, "No results stored in database"
        
        # Verify result data - use proper column names instead of hardcoded indices
        result_row = results[0]
        
        # Get column names for safer access
        cursor.execute("PRAGMA table_info(crawl_results)")
        columns = [column[1] for column in cursor.fetchall()]
        result_dict = dict(zip(columns, result_row))
        
        # Verify result data using column names
        assert result_dict['url'] == 'https://httpbin.org/uuid', f"Expected URL not found, got: {result_dict['url']}"
        assert result_dict['success'] == True, f"Expected successful crawl, got: {result_dict['success']}"
        assert result_dict['content_markdown'] is not None, "No content_markdown stored"
        
        conn.close()
    
    @pytest.mark.asyncio
    async def test_async_job_processing_workflow(self, temp_dir):
        """Test async job processing workflow - Phase 1 integration."""
        # RED: This should fail until async job system is complete
        
        # Initialize components
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "async_test.db")
        await storage_manager.initialize()
        
        job_manager = get_job_manager()
        await job_manager.initialize()
        
        scrape_service = get_scrape_service()
        await scrape_service.initialize()
        
        # Submit async scrape job
        job_id = await scrape_service.scrape_single_async(
            url="https://httpbin.org/json",
            options={"timeout": 30, "headless": True},
            output_format="json"
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
        
        # Check initial job status
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status in ["pending", "running"]
        
        # Process the job
        await job_manager.process_job(job_id)
        
        # Check final job status
        final_status = await job_manager.get_job_status(job_id)
        assert final_status.status == "completed"
        
        # Get job result
        job_result = await job_manager.get_job_result(job_id)
        assert job_result is not None
        assert job_result["success"] is True
        assert "result" in job_result
    
    @pytest.mark.asyncio
    async def test_cache_integration_workflow(self, temp_dir):
        """Test cache integration workflow - Phase 1 integration."""
        # RED: This should fail until cache system is complete
        
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "cache_test.db")
        await storage_manager.initialize()
        
        crawl_engine = get_crawl_engine()
        await crawl_engine.initialize()
        
        test_url = "https://httpbin.org/json"
        
        # First scrape - should miss cache
        result1 = await crawl_engine.scrape_single(
            url=test_url,
            options={"cache_enabled": True}
        )
        
        assert result1["success"] is True
        cache_miss_timestamp = result1.get("timestamp") or result1.get("created_at")
        
        # Second scrape - should hit cache
        result2 = await crawl_engine.scrape_single(
            url=test_url,
            options={"cache_enabled": True}
        )
        
        assert result2["success"] is True
        
        # Results should be identical (from cache)
        # At minimum, URLs should match
        assert result1["url"] == result2["url"]
        
        # Verify cache was actually used (implementation dependent)
        # This test verifies the cache system is working
    
    def test_config_management_integration(self, cli_runner, temp_dir):
        """Test configuration management integration - Phase 1 integration."""
        config_file = temp_dir / "integration_config.yaml"
        
        # RED: This should fail until config management is complete
        
        # Test setting a configuration value
        result1 = cli_runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'set', 'scrape.timeout', '45'
        ])
        assert result1.exit_code == 0
        
        # Test getting the configuration value
        result2 = cli_runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'get', 'scrape.timeout'
        ])
        assert result2.exit_code == 0
        assert "45" in result2.output
        
        # Test showing all configuration
        result3 = cli_runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'show'
        ])
        assert result3.exit_code == 0
        assert "scrape" in result3.output
        assert "timeout" in result3.output
        
        # Verify config file was created and is valid YAML
        assert config_file.exists()
        import yaml
        config_data = yaml.safe_load(config_file.read_text())
        assert isinstance(config_data, dict)
        assert config_data["scrape"]["timeout"] == 45
    
    @pytest.mark.asyncio
    async def test_session_management_workflow(self, temp_dir):
        """Test browser session management workflow - Phase 1 integration."""
        # RED: This should fail until session management is complete
        
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "session_test.db")
        await storage_manager.initialize()
        
        crawl_engine = get_crawl_engine()
        await crawl_engine.initialize()
        
        # Create a session
        session_config = {
            "headless": True,
            "timeout": 30,
            "user_agent": "Test Agent"
        }
        
        session_id = await crawl_engine.create_session(session_config)
        assert session_id is not None
        assert isinstance(session_id, str)
        
        # Use session for scraping
        result = await crawl_engine.scrape_single(
            url="https://httpbin.org/user-agent",
            session_id=session_id
        )
        
        assert result["success"] is True
        # Should contain our custom user agent
        if "content" in result:
            content = result["content"]
            if isinstance(content, dict):
                # Check in the text content
                content_text = content.get("text", "") or content.get("markdown", "") or content.get("html", "")
                assert "Test Agent" in content_text, f"Expected 'Test Agent' in content, got: {content_text}"
            else:
                assert "Test Agent" in content, f"Expected 'Test Agent' in content, got: {content}"
        
        # Close session
        closed = await crawl_engine.close_session(session_id)
        assert closed is True
        
        # Verify session is no longer available
        with pytest.raises(Exception):  # Should raise session not found error
            await crawl_engine.scrape_single(
                url="https://httpbin.org/uuid",
                session_id=session_id
            )
    
    def test_error_handling_integration(self, cli_runner):
        """Test error handling integration across all layers - Phase 1 integration."""
        # RED: This should fail until comprehensive error handling is complete
        
        # Test invalid URL
        result1 = cli_runner.invoke(cli, [
            'scrape', 'not-a-valid-url'
        ])
        assert result1.exit_code != 0
        assert any(word in result1.output.lower() for word in [
            "invalid", "error", "url", "format"
        ])
        
        # Test unreachable host
        result2 = cli_runner.invoke(cli, [
            'scrape', 'https://nonexistent-domain-12345.invalid'
        ])
        assert result2.exit_code != 0
        assert any(word in result2.output.lower() for word in [
            "error", "failed", "connection", "network"
        ])
        
        # Test timeout scenario
        result3 = cli_runner.invoke(cli, [
            'scrape', 'https://httpbin.org/delay/10',
            '--timeout', '2'
        ])
        # Should either succeed quickly or fail with timeout
        if result3.exit_code != 0:
            assert "timeout" in result3.output.lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_integration(self, temp_dir):
        """Test concurrent operations integration - Phase 1 integration."""
        # RED: This should fail until concurrency handling is complete
        
        # Initialize components
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "concurrent_test.db")
        await storage_manager.initialize()
        
        scrape_service = get_scrape_service()
        await scrape_service.initialize()
        
        # Submit multiple concurrent scrape jobs
        urls = [
            "https://httpbin.org/uuid",
            "https://httpbin.org/json",
            "https://httpbin.org/headers",
            "https://httpbin.org/ip",
            "https://httpbin.org/user-agent"
        ]
        
        # Submit as async jobs
        job_ids = []
        for url in urls:
            job_id = await scrape_service.scrape_single_async(
                url=url,
                options={"timeout": 30}
            )
            job_ids.append(job_id)
        
        assert len(job_ids) == len(urls)
        
        # Process jobs concurrently
        job_manager = get_job_manager()
        await job_manager.process_pending_jobs(max_concurrent=3)
        
        # Verify all jobs completed successfully
        for job_id in job_ids:
            job_status = await job_manager.get_job_status(job_id)
            assert job_status.status == "completed"
            
            job_result = await job_manager.get_job_result(job_id)
            assert job_result["success"] is True
    
    def test_batch_scraping_integration(self, cli_runner, temp_dir):
        """Test batch scraping integration - Phase 1 integration."""
        # RED: This should fail until batch scraping is complete
        
        # Create URL file
        urls_file = temp_dir / "urls.txt"
        urls = [
            "https://httpbin.org/uuid",
            "https://httpbin.org/json",
            "https://httpbin.org/ip"
        ]
        urls_file.write_text("\n".join(urls))
        
        output_dir = temp_dir / "batch_results"
        
        result = cli_runner.invoke(cli, [
            'batch',
            str(urls_file),
            '--output-dir', str(output_dir),
            '--format', 'json',
            '--concurrent', '2'
        ])
        
        assert result.exit_code == 0
        assert output_dir.exists()
        
        # Verify output files were created
        output_files = list(output_dir.glob("*.json"))
        
        # Should have individual result files plus batch summary
        individual_files = [f for f in output_files if not f.name.endswith("_summary.json") and not f.name.startswith("batch_summary")]
        assert len(individual_files) == len(urls)
        
        # Verify each output file has valid content
        for output_file in individual_files:
            content = json.loads(output_file.read_text())
            assert content["success"] is True
            assert "url" in content
            assert content["url"] in urls
    
    def test_status_and_health_check_integration(self, cli_runner, temp_dir):
        """Test status and health check integration - Phase 1 integration."""
        # RED: This should fail until status system is complete
        
        config_file = temp_dir / "status_config.yaml"
        config_content = f"""
version: "1.0"
storage:
  database_path: "{temp_dir / 'status.db'}"
"""
        config_file.write_text(config_content)
        
        # Test basic status
        result1 = cli_runner.invoke(cli, [
            '--config', str(config_file),
            'status'
        ])
        assert result1.exit_code == 0
        assert any(word in result1.output.lower() for word in [
            "status", "ready", "running", "healthy"
        ])
        
        # Test health check
        result2 = cli_runner.invoke(cli, [
            '--config', str(config_file),
            'status', '--health'
        ])
        assert result2.exit_code == 0
        assert any(word in result2.output.lower() for word in [
            "health", "ok", "pass", "fail", "check"
        ])


@pytest.mark.integration
@pytest.mark.slow
class TestPhase1Performance:
    """Performance and scalability tests for Phase 1."""
    
    @pytest.mark.asyncio
    async def test_database_performance_under_load(self, temp_dir):
        """Test database performance under load - Phase 1 performance."""
        # RED: This should fail until database optimization is complete
        
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "perf_test.db")
        await storage_manager.initialize()
        
        # Store many results concurrently
        async def store_result(i):
            result_data = {
                "url": f"https://example.com/{i}",
                "title": f"Page {i}",
                "content": f"Content for page {i}",
                "success": True,
                "status_code": 200,
                "created_at": datetime.utcnow()
            }
            return await storage_manager.store_scrape_result(result_data)
        
        # Store 100 results concurrently
        tasks = [store_result(i) for i in range(100)]
        start_time = datetime.utcnow()
        result_ids = await asyncio.gather(*tasks)
        end_time = datetime.utcnow()
        
        # All should succeed
        assert len(result_ids) == 100
        assert all(rid is not None for rid in result_ids)
        
        # Should complete reasonably quickly (less than 10 seconds)
        duration = (end_time - start_time).total_seconds()
        assert duration < 10, f"Database operations took too long: {duration}s"
    
    def test_cli_performance_baseline(self, cli_runner):
        """Test CLI performance baseline - Phase 1 performance."""
        # RED: This should fail until performance optimization is complete
        
        start_time = datetime.utcnow()
        result = cli_runner.invoke(cli, [
            'scrape', 'https://httpbin.org/json'
        ])
        end_time = datetime.utcnow()
        
        assert result.exit_code == 0
        
        # Should complete within reasonable time (30 seconds)
        duration = (end_time - start_time).total_seconds()
        assert duration < 30, f"CLI scrape took too long: {duration}s"


# These tests represent the complete Phase 1 integration test suite
# They should FAIL initially and guide implementation of full workflows