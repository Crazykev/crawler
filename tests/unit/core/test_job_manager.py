"""Tests for job management system - Phase 1 TDD Requirements."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.crawler.core.jobs import JobManager, get_job_manager
from src.crawler.database.models.jobs import JobType, JobStatus, JobPriority
from src.crawler.foundation.errors import JobError, ValidationError


@pytest.mark.asyncio
class TestJobManagerCore:
    """Test core job manager functionality for Phase 1."""
    
    async def test_job_manager_initialization(self):
        """Test job manager initialization - Phase 1 requirement."""
        # RED: This should fail until JobManager is properly implemented
        job_manager = JobManager()
        await job_manager.initialize()
        
        assert job_manager.is_initialized
        assert hasattr(job_manager, 'storage_manager')
        assert hasattr(job_manager, 'job_handlers')
        assert hasattr(job_manager, '_running_jobs')
    
    async def test_submit_scrape_job(self):
        """Test submitting a scrape job - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # RED: This should fail until job submission is implemented
        job_data = {
            "url": "https://example.com",
            "options": {"timeout": 30, "headless": True},
            "output_format": "markdown"
        }
        
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data=job_data,
            priority=JobPriority.NORMAL
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
        assert len(job_id) > 0
        
        # Verify job was stored
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.PENDING
        assert job_status.job_type == JobType.SCRAPE_SINGLE
    
    async def test_submit_batch_scrape_job(self):
        """Test submitting a batch scrape job - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # RED: This should fail until batch job support is implemented
        job_data = {
            "urls": ["https://example.com", "https://test.com"],
            "options": {"timeout": 30},
            "concurrent_requests": 2,
            "output_format": "json"
        }
        
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_BATCH,
            job_data=job_data,
            priority=JobPriority.HIGH
        )
        
        assert job_id is not None
        
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.PENDING
        assert job_status.job_type == JobType.SCRAPE_BATCH
        assert job_status.priority == JobPriority.HIGH
    
    async def test_job_execution_workflow(self):
        """Test complete job execution workflow - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # Mock job handler
        mock_handler = AsyncMock()
        mock_handler.return_value = {
            "success": True,
            "result": {"url": "https://example.com", "content": "Test content"}
        }
        
        # RED: This should fail until job handler registration is implemented
        job_manager.register_handler(JobType.SCRAPE_SINGLE, mock_handler)
        
        job_data = {
            "url": "https://example.com",
            "options": {"timeout": 30}
        }
        
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data=job_data
        )
        
        # Start job processing
        await job_manager.process_job(job_id)
        
        # Verify job completed successfully
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.COMPLETED
        
        # Get job result
        job_result = await job_manager.get_job_result(job_id)
        assert job_result is not None
        assert job_result["success"] is True
        assert "result" in job_result
        
        # Verify handler was called
        mock_handler.assert_called_once_with(job_data)
    
    async def test_job_priority_queue(self, temp_dir):
        """Test job priority queue functionality - Phase 1 requirement."""
        # Use a temporary database for this test
        test_db_path = temp_dir / "test_priority.db"
        job_manager = JobManager(db_path=str(test_db_path))
        await job_manager.initialize()
        
        # RED: This should fail until priority queue is implemented
        # Submit jobs with different priorities
        low_job = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://low.com"},
            priority=JobPriority.LOW
        )
        
        high_job = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://high.com"},
            priority=JobPriority.HIGH
        )
        
        normal_job = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://normal.com"},
            priority=JobPriority.NORMAL
        )
        
        # Get next jobs to process - should be in priority order
        next_jobs = await job_manager.get_pending_jobs(limit=3)
        
        assert len(next_jobs) == 3
        # High priority should be first
        assert next_jobs[0].job_id == high_job
        assert next_jobs[0].priority == JobPriority.HIGH
    
    async def test_job_cancellation(self):
        """Test job cancellation - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # RED: This should fail until job cancellation is implemented
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://example.com"}
        )
        
        # Cancel the job
        cancelled = await job_manager.cancel_job(job_id)
        assert cancelled is True
        
        # Verify job status
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.CANCELLED
        
        # Try to cancel already cancelled job
        cancelled_again = await job_manager.cancel_job(job_id)
        assert cancelled_again is False
    
    async def test_job_timeout_handling(self):
        """Test job timeout handling - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # Mock slow handler
        slow_handler = AsyncMock()
        slow_handler.side_effect = asyncio.TimeoutError("Job timed out")
        
        # RED: This should fail until timeout handling is implemented
        job_manager.register_handler(JobType.SCRAPE_SINGLE, slow_handler)
        
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://slow.com"},
            timeout=1  # 1 second timeout
        )
        
        # Process job (should timeout)
        await job_manager.process_job(job_id)
        
        # Verify job failed due to timeout
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.FAILED
        
        job_result = await job_manager.get_job_result(job_id)
        assert job_result is not None
        assert "timeout" in job_result.get("error", "").lower()
    
    async def test_job_retry_mechanism(self):
        """Test job retry mechanism - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # Mock handler that fails first time, succeeds second time
        call_count = 0
        
        async def failing_handler(job_data):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            return {"success": True, "result": "success on retry"}
        
        # RED: This should fail until retry mechanism is implemented
        job_manager.register_handler(JobType.SCRAPE_SINGLE, failing_handler)
        
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://flaky.com"},
            retry_attempts=2
        )
        
        # Process job (should succeed on retry)
        await job_manager.process_job(job_id)
        
        # Verify job completed successfully after retry
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.COMPLETED
        
        job_result = await job_manager.get_job_result(job_id)
        assert job_result["success"] is True
        assert call_count == 2  # Called twice due to retry
    
    async def test_concurrent_job_processing(self, temp_dir):
        """Test concurrent job processing - Phase 1 requirement."""
        # Use a temporary database for this test
        test_db_path = temp_dir / "test_concurrent.db"
        job_manager = JobManager(db_path=str(test_db_path))
        await job_manager.initialize()
        
        # Mock handler
        mock_handler = AsyncMock()
        mock_handler.return_value = {"success": True, "result": "processed"}
        
        # RED: This should fail until concurrent processing is implemented
        job_manager.register_handler(JobType.SCRAPE_SINGLE, mock_handler)
        
        # Submit multiple jobs
        job_ids = []
        for i in range(5):
            job_id = await job_manager.submit_job(
                job_type=JobType.SCRAPE_SINGLE,
                job_data={"url": f"https://example{i}.com"}
            )
            job_ids.append(job_id)
        
        # Process jobs concurrently
        await job_manager.process_pending_jobs(max_concurrent=3)
        
        # Verify all jobs completed
        for job_id in job_ids:
            job_status = await job_manager.get_job_status(job_id)
            assert job_status.status == JobStatus.COMPLETED
        
        # Verify handler was called for each job
        assert mock_handler.call_count == 5


@pytest.mark.asyncio
class TestJobManagerStorage:
    """Test job manager storage integration for Phase 1."""
    
    async def test_job_persistence(self, temp_dir):
        """Test job persistence across restarts - Phase 1 requirement."""
        db_path = temp_dir / "jobs.db"
        
        # Create first job manager instance
        job_manager1 = JobManager(db_path=str(db_path))
        await job_manager1.initialize()
        
        # RED: This should fail until job persistence is implemented
        job_id = await job_manager1.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://persistent.com"}
        )
        
        await job_manager1.close()
        
        # Create second job manager instance
        job_manager2 = JobManager(db_path=str(db_path))
        await job_manager2.initialize()
        
        # Job should still exist
        job_status = await job_manager2.get_job_status(job_id)
        assert job_status is not None
        assert job_status.status == JobStatus.PENDING
        
        await job_manager2.close()
    
    async def test_job_cleanup(self):
        """Test cleanup of old completed jobs - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # Mock handler
        mock_handler = AsyncMock()
        mock_handler.return_value = {"success": True, "result": "completed"}
        job_manager.register_handler(JobType.SCRAPE_SINGLE, mock_handler)
        
        # RED: This should fail until job cleanup is implemented
        # Submit and complete a job
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://cleanup.com"}
        )
        
        await job_manager.process_job(job_id)
        
        # Verify job is completed
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.COMPLETED
        
        # Clean up jobs older than 0 seconds (should clean this job)
        cleanup_before = datetime.utcnow() + timedelta(seconds=1)
        cleaned_count = await job_manager.cleanup_completed_jobs(cleanup_before)
        
        assert cleaned_count > 0
        
        # Job should be gone or marked for cleanup
        job_status_after = await job_manager.get_job_status(job_id)
        assert job_status_after is None or job_status_after.status == JobStatus.CLEANED


@pytest.mark.asyncio
class TestJobManagerErrorHandling:
    """Test job manager error handling for Phase 1."""
    
    async def test_invalid_job_type(self):
        """Test handling of invalid job type - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # RED: This should fail until proper validation is implemented
        with pytest.raises(ValidationError):
            await job_manager.submit_job(
                job_type="invalid_job_type",
                job_data={"url": "https://example.com"}
            )
    
    async def test_missing_job_handler(self):
        """Test handling of missing job handler - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # RED: This should fail until proper error handling is implemented
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://example.com"}
        )
        
        # Don't register handler, try to process
        await job_manager.process_job(job_id)
        
        # Job should fail
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.FAILED
        
        job_result = await job_manager.get_job_result(job_id)
        assert "handler" in job_result.get("error", "").lower()
    
    async def test_job_handler_exception(self):
        """Test handling of job handler exceptions - Phase 1 requirement."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # Mock handler that raises exception
        failing_handler = AsyncMock()
        failing_handler.side_effect = Exception("Handler error")
        
        # RED: This should fail until exception handling is implemented
        job_manager.register_handler(JobType.SCRAPE_SINGLE, failing_handler)
        
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={"url": "https://error.com"}
        )
        
        await job_manager.process_job(job_id)
        
        # Job should fail gracefully
        job_status = await job_manager.get_job_status(job_id)
        assert job_status.status == JobStatus.FAILED
        
        job_result = await job_manager.get_job_result(job_id)
        assert "Handler error" in job_result.get("error", "")


@pytest.mark.integration
class TestJobManagerIntegration:
    """Integration tests for job manager with other components."""
    
    async def test_scrape_service_job_integration(self):
        """Test job manager integration with scrape service - Phase 1 integration."""
        job_manager = JobManager()
        await job_manager.initialize()
        
        # Mock scrape service handler
        mock_scrape_result = {
            "success": True,
            "url": "https://example.com",
            "title": "Test Page",
            "content": "Test content"
        }
        
        async def scrape_handler(job_data):
            return {"success": True, "result": mock_scrape_result}
        
        # RED: This should fail until service integration is implemented
        job_manager.register_handler(JobType.SCRAPE_SINGLE, scrape_handler)
        
        # Submit scrape job
        job_id = await job_manager.submit_job(
            job_type=JobType.SCRAPE_SINGLE,
            job_data={
                "url": "https://example.com",
                "options": {"timeout": 30},
                "output_format": "markdown"
            }
        )
        
        # Process job
        await job_manager.process_job(job_id)
        
        # Verify result
        job_result = await job_manager.get_job_result(job_id)
        assert job_result["success"] is True
        assert job_result["result"]["url"] == "https://example.com"
        assert job_result["result"]["title"] == "Test Page"


# These tests represent the TDD RED phase for Phase 1 job management
# They should FAIL initially and guide implementation of async job system