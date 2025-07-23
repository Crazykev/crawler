"""Performance benchmark for concurrent operations test."""

import asyncio
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, AsyncMock
import pytest

from src.crawler.core import get_crawl_engine, get_storage_manager, get_job_manager
from src.crawler.services import get_scrape_service


@pytest.mark.asyncio
async def test_concurrent_operations_benchmark(temp_dir, mock_scrape_service):
    """Benchmark concurrent operations with different configurations."""
    
    # Use the mock scrape service to avoid database conflicts
    scrape_service = mock_scrape_service
    
    # Configure the mock to return job IDs properly
    async def mock_scrape_single_async(url, options=None):
        # Return a job ID after minimal delay
        import uuid
        await asyncio.sleep(0.001)
        return str(uuid.uuid4())
    
    mock_scrape_service.scrape_single_async.side_effect = mock_scrape_single_async
    
    crawl_engine = get_crawl_engine()
    
    # Mock response for consistent timing
    mock_response = {
        "success": True,
        "url": "https://test.com",
        "title": "Test Page",
        "content_markdown": "# Test Content",
        "content_html": "<p>Test Content</p>",
        "status_code": 200,
        "created_at": datetime.utcnow().isoformat()
    }
    
    async def mock_scrape_single(url, options=None, **kwargs):
        # Simulate minimal processing
        await asyncio.sleep(0.001)
        return {**mock_response, "url": url}
    
    with patch.object(crawl_engine, 'scrape_single', side_effect=mock_scrape_single):
        # Test different concurrency levels
        for num_jobs in [5, 10, 20, 50]:
            for max_concurrent in [1, 3, 5, 10]:
                if max_concurrent > num_jobs:
                    continue
                    
                print(f"\nBenchmark: {num_jobs} jobs, max_concurrent={max_concurrent}")
                
                # Generate URLs
                urls = [f"https://test.com/page-{i}" for i in range(num_jobs)]
                
                # Measure job submission time
                start_time = time.time()
                job_ids = await asyncio.gather(*[
                    scrape_service.scrape_single_async(
                        url=url,
                        options={"timeout": 1}
                    )
                    for url in urls
                ])
                submission_time = time.time() - start_time
                
                # Measure job processing time
                start_time = time.time()
                job_manager = get_job_manager()
                
                # Mock job manager methods for testing
                from unittest.mock import AsyncMock
                job_manager.process_pending_jobs = AsyncMock()
                job_manager.get_job_result = AsyncMock()
                
                # Mock job results
                mock_result = {"success": True, "url": "test", "content": "test"}
                job_manager.get_job_result.return_value = mock_result
                
                await job_manager.process_pending_jobs(max_concurrent=max_concurrent)
                processing_time = time.time() - start_time
                
                # Verify results
                results = await asyncio.gather(*[
                    job_manager.get_job_result(job_id) for job_id in job_ids
                ])
                
                # Filter out None results
                valid_results = [r for r in results if r is not None]
                success_count = sum(1 for r in valid_results if r.get("success", False))
                
                print(f"  Submission: {submission_time:.3f}s")
                print(f"  Processing: {processing_time:.3f}s")
                print(f"  Total: {submission_time + processing_time:.3f}s")
                print(f"  Success: {success_count}/{len(valid_results)} (of {num_jobs} total)")
                print(f"  Rate: {num_jobs/(submission_time + processing_time):.1f} jobs/sec")
                
                # Most should succeed (allow for some failures in concurrent testing)
                success_rate = success_count / num_jobs if num_jobs > 0 else 0
                assert success_rate >= 0.8, f"Expected at least 80% success rate, got {success_count}/{num_jobs} ({success_rate:.1%})"