"""Performance benchmark tests for refactoring phase."""

import pytest
import asyncio
import time
import psutil
import gc
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from src.crawler.core.engine import CrawlEngine, get_crawl_engine
from src.crawler.core.storage import StorageManager, get_storage_manager
from src.crawler.services.scrape import ScrapeService, get_scrape_service
from src.crawler.core.jobs import JobManager, get_job_manager


@pytest.mark.performance
@pytest.mark.refactoring
class TestPerformanceBenchmarks:
    """Performance benchmark tests to guide refactoring priorities."""
    
    @pytest.mark.asyncio
    async def test_single_scrape_performance_baseline(self, temp_dir):
        """Establish baseline performance for single scrape operations."""
        # RED: This test should initially fail performance targets
        # GREEN: Should pass after optimization
        # REFACTOR: Should maintain performance with cleaner code
        
        engine = CrawlEngine()
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "perf_test.db")
        
        await engine.initialize()
        await storage_manager.initialize()
        
        # Mock crawl4ai for consistent testing
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            # Mock successful crawl result
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test content</body></html>"
            mock_result.cleaned_html = "<body>Test content</body>"
            mock_result.markdown = "Test content"
            mock_result.extracted_content = "Test content"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            # Measure baseline performance
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            result = await engine.scrape_single(
                url="https://example.com",
                options={"timeout": 30, "cache_enabled": False}
            )
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            # Performance assertions
            duration = end_time - start_time
            memory_used = end_memory - start_memory
            
            # Current baseline targets (these should be improved through refactoring)
            assert result["success"] is True
            assert duration < 5.0, f"Single scrape took {duration:.2f}s, target is < 5.0s"
            assert memory_used < 100, f"Memory usage {memory_used:.2f}MB, target is < 100MB"
            
            # Store baseline metrics for comparison
            await storage_manager.store_performance_metric(
                metric_name="single_scrape_duration_baseline",
                value=duration,
                tags={"test": "baseline", "operation": "single_scrape"}
            )
            
            await storage_manager.store_performance_metric(
                metric_name="single_scrape_memory_baseline",
                value=memory_used,
                tags={"test": "baseline", "operation": "single_scrape"}
            )
    
    @pytest.mark.asyncio
    async def test_concurrent_scrape_performance_baseline(self, temp_dir):
        """Establish baseline performance for concurrent scrape operations."""
        # RED: This test should initially fail concurrency targets
        # GREEN: Should pass after async optimization
        # REFACTOR: Should maintain performance with better code structure
        
        engine = CrawlEngine()
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "concurrent_perf_test.db")
        
        await engine.initialize()
        await storage_manager.initialize()
        
        # Mock crawl4ai for consistent testing
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            # Mock successful crawl result
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test content</body></html>"
            mock_result.cleaned_html = "<body>Test content</body>"
            mock_result.markdown = "Test content"
            mock_result.extracted_content = "Test content"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            # Test concurrent scraping
            urls = [f"https://example.com/{i}" for i in range(10)]
            
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Submit concurrent scrape requests
            tasks = []
            for url in urls:
                task = engine.scrape_single(
                    url=url,
                    options={"timeout": 30, "cache_enabled": False}
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Performance assertions
            duration = end_time - start_time
            memory_used = end_memory - start_memory
            
            # All results should be successful
            assert all(result["success"] for result in results)
            
            # Concurrent performance targets (to be improved)
            assert duration < 15.0, f"Concurrent scrape took {duration:.2f}s, target is < 15.0s"
            assert memory_used < 200, f"Memory usage {memory_used:.2f}MB, target is < 200MB"
            
            # Store metrics
            await storage_manager.store_performance_metric(
                metric_name="concurrent_scrape_duration_baseline",
                value=duration,
                tags={"test": "baseline", "operation": "concurrent_scrape", "count": len(urls)}
            )
    
    @pytest.mark.asyncio
    async def test_database_performance_baseline(self, temp_dir):
        """Establish baseline performance for database operations."""
        # RED: This test should initially fail database performance targets
        # GREEN: Should pass after database optimization
        # REFACTOR: Should maintain performance with better query structure
        
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "db_perf_test.db")
        
        await storage_manager.initialize()
        
        # Test individual insert performance
        results_data = []
        for i in range(100):
            result_data = {
                "url": f"https://example.com/{i}",
                "title": f"Page {i}",
                "success": True,
                "status_code": 200,
                "content_markdown": f"Content for page {i}",
                "content_html": f"<html><body>Content for page {i}</body></html>",
                "content_text": f"Content for page {i}",
                "extracted_data": {"key": f"value_{i}"},
                "metadata": {"test": True},
                "created_at": datetime.utcnow()
            }
            results_data.append(result_data)
        
        # Test individual inserts
        start_time = time.time()
        
        for result_data in results_data:
            await storage_manager.store_scrape_result(result_data)
        
        individual_insert_time = time.time() - start_time
        
        # Clear data for batch test
        await storage_manager.clear_all_results()
        
        # Test batch insert performance
        start_time = time.time()
        
        await storage_manager.store_scrape_results_batch(results_data)
        
        batch_insert_time = time.time() - start_time
        
        # Performance assertions
        # Individual inserts should be reasonably fast
        assert individual_insert_time < 10.0, f"Individual inserts took {individual_insert_time:.2f}s, target is < 10.0s"
        
        # Batch inserts should be significantly faster
        assert batch_insert_time < 2.0, f"Batch insert took {batch_insert_time:.2f}s, target is < 2.0s"
        
        # Batch should be at least 3x faster than individual
        speedup = individual_insert_time / batch_insert_time
        assert speedup > 3.0, f"Batch speedup is {speedup:.2f}x, target is > 3.0x"
        
        # Store metrics
        await storage_manager.store_performance_metric(
            metric_name="database_individual_insert_baseline",
            value=individual_insert_time,
            tags={"test": "baseline", "operation": "individual_insert", "count": len(results_data)}
        )
        
        await storage_manager.store_performance_metric(
            metric_name="database_batch_insert_baseline",
            value=batch_insert_time,
            tags={"test": "baseline", "operation": "batch_insert", "count": len(results_data)}
        )
    
    @pytest.mark.asyncio
    async def test_cache_performance_baseline(self, temp_dir):
        """Establish baseline performance for cache operations."""
        # RED: This test should initially fail cache performance targets
        # GREEN: Should pass after cache optimization
        # REFACTOR: Should maintain performance with better cache design
        
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "cache_perf_test.db")
        
        await storage_manager.initialize()
        
        # Test cache miss performance
        cache_key = "test_cache_key"
        cache_data = {"large_data": "x" * 10000}  # 10KB of data
        
        start_time = time.time()
        
        # This should be a cache miss
        cached_result = await storage_manager.get_cached_result(cache_key)
        
        cache_miss_time = time.time() - start_time
        
        assert cached_result is None
        
        # Test cache store performance
        start_time = time.time()
        
        await storage_manager.store_cached_result(cache_key, cache_data, ttl=3600)
        
        cache_store_time = time.time() - start_time
        
        # Test cache hit performance
        start_time = time.time()
        
        cached_result = await storage_manager.get_cached_result(cache_key)
        
        cache_hit_time = time.time() - start_time
        
        assert cached_result is not None
        assert cached_result == cache_data
        
        # Performance assertions
        assert cache_miss_time < 0.1, f"Cache miss took {cache_miss_time:.4f}s, target is < 0.1s"
        assert cache_store_time < 0.1, f"Cache store took {cache_store_time:.4f}s, target is < 0.1s"
        assert cache_hit_time < 0.05, f"Cache hit took {cache_hit_time:.4f}s, target is < 0.05s"
        
        # Store metrics
        await storage_manager.store_performance_metric(
            metric_name="cache_miss_baseline",
            value=cache_miss_time,
            tags={"test": "baseline", "operation": "cache_miss"}
        )
        
        await storage_manager.store_performance_metric(
            metric_name="cache_hit_baseline",
            value=cache_hit_time,
            tags={"test": "baseline", "operation": "cache_hit"}
        )
    
    @pytest.mark.asyncio
    async def test_memory_management_baseline(self, temp_dir):
        """Establish baseline for memory management during operations."""
        # RED: This test should initially fail memory management targets
        # GREEN: Should pass after memory optimization
        # REFACTOR: Should maintain low memory with cleaner code
        
        engine = CrawlEngine()
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "memory_perf_test.db")
        
        await engine.initialize()
        await storage_manager.initialize()
        
        # Mock crawl4ai for consistent testing
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            # Mock result with large content
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>" + "x" * 100000 + "</body></html>"  # 100KB
            mock_result.cleaned_html = "<body>" + "x" * 100000 + "</body>"
            mock_result.markdown = "x" * 100000
            mock_result.extracted_content = "x" * 100000
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            # Measure initial memory
            gc.collect()
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Process multiple large pages
            for i in range(20):
                result = await engine.scrape_single(
                    url=f"https://example.com/{i}",
                    options={"timeout": 30, "cache_enabled": False}
                )
                
                assert result["success"] is True
                
                # Force garbage collection
                gc.collect()
            
            # Measure final memory
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_growth = final_memory - initial_memory
            
            # Memory growth should be reasonable
            assert memory_growth < 50, f"Memory growth {memory_growth:.2f}MB, target is < 50MB"
            
            # Store metrics
            await storage_manager.store_performance_metric(
                metric_name="memory_growth_baseline",
                value=memory_growth,
                tags={"test": "baseline", "operation": "memory_management", "pages": 20}
            )
    
    @pytest.mark.asyncio
    async def test_job_queue_performance_baseline(self, temp_dir):
        """Establish baseline performance for job queue operations."""
        # RED: This test should initially fail job queue performance targets
        # GREEN: Should pass after job queue optimization
        # REFACTOR: Should maintain performance with better job queue design
        
        job_manager = get_job_manager()
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "job_perf_test.db")
        
        await job_manager.initialize()
        await storage_manager.initialize()
        
        # Test job submission performance
        start_time = time.time()
        
        job_ids = []
        for i in range(100):
            job_data = {
                "url": f"https://example.com/{i}",
                "options": {"timeout": 30},
                "format": "json"
            }
            job_id = await job_manager.submit_scrape_job(job_data)
            job_ids.append(job_id)
        
        submission_time = time.time() - start_time
        
        # Test job status retrieval performance
        start_time = time.time()
        
        for job_id in job_ids:
            status = await job_manager.get_job_status(job_id)
            assert status is not None
        
        status_retrieval_time = time.time() - start_time
        
        # Performance assertions
        assert submission_time < 5.0, f"Job submission took {submission_time:.2f}s, target is < 5.0s"
        assert status_retrieval_time < 2.0, f"Status retrieval took {status_retrieval_time:.2f}s, target is < 2.0s"
        
        # Store metrics
        await storage_manager.store_performance_metric(
            metric_name="job_submission_baseline",
            value=submission_time,
            tags={"test": "baseline", "operation": "job_submission", "count": len(job_ids)}
        )
        
        await storage_manager.store_performance_metric(
            metric_name="job_status_retrieval_baseline",
            value=status_retrieval_time,
            tags={"test": "baseline", "operation": "status_retrieval", "count": len(job_ids)}
        )


@pytest.mark.performance
@pytest.mark.refactoring
class TestPerformanceRegressionPrevention:
    """Tests to prevent performance regressions during refactoring."""
    
    @pytest.mark.asyncio
    async def test_performance_regression_detection(self, temp_dir):
        """Test that detects performance regressions during refactoring."""
        # This test should be run after each refactoring step
        # to ensure no performance regressions are introduced
        
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "regression_test.db")
        
        await storage_manager.initialize()
        
        # Get baseline metrics
        baseline_metrics = await storage_manager.get_performance_metrics(
            metric_name="single_scrape_duration_baseline",
            tags={"test": "baseline"}
        )
        
        if not baseline_metrics:
            pytest.skip("No baseline metrics available")
        
        baseline_duration = baseline_metrics[0]["value"]
        
        # Run current implementation
        engine = CrawlEngine()
        await engine.initialize()
        
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test content</body></html>"
            mock_result.cleaned_html = "<body>Test content</body>"
            mock_result.markdown = "Test content"
            mock_result.extracted_content = "Test content"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            start_time = time.time()
            
            result = await engine.scrape_single(
                url="https://example.com",
                options={"timeout": 30, "cache_enabled": False}
            )
            
            current_duration = time.time() - start_time
            
            # Should not be significantly slower than baseline
            regression_threshold = baseline_duration * 1.2  # 20% slower is considered regression
            
            assert current_duration < regression_threshold, (
                f"Performance regression detected: {current_duration:.2f}s vs "
                f"baseline {baseline_duration:.2f}s (threshold: {regression_threshold:.2f}s)"
            )
            
            # Store current metrics
            await storage_manager.store_performance_metric(
                metric_name="single_scrape_duration_current",
                value=current_duration,
                tags={"test": "current", "operation": "single_scrape"}
            )
    
    @pytest.mark.asyncio
    async def test_memory_regression_detection(self, temp_dir):
        """Test that detects memory usage regressions during refactoring."""
        
        storage_manager = get_storage_manager()
        storage_manager.db_path = str(temp_dir / "memory_regression_test.db")
        
        await storage_manager.initialize()
        
        # Get baseline metrics
        baseline_metrics = await storage_manager.get_performance_metrics(
            metric_name="single_scrape_memory_baseline",
            tags={"test": "baseline"}
        )
        
        if not baseline_metrics:
            pytest.skip("No baseline memory metrics available")
        
        baseline_memory = baseline_metrics[0]["value"]
        
        # Run current implementation
        engine = CrawlEngine()
        await engine.initialize()
        
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test content</body></html>"
            mock_result.cleaned_html = "<body>Test content</body>"
            mock_result.markdown = "Test content"
            mock_result.extracted_content = "Test content"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            result = await engine.scrape_single(
                url="https://example.com",
                options={"timeout": 30, "cache_enabled": False}
            )
            
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            current_memory = end_memory - start_memory
            
            # Should not use significantly more memory than baseline
            memory_regression_threshold = baseline_memory * 1.3  # 30% more memory is regression
            
            assert current_memory < memory_regression_threshold, (
                f"Memory regression detected: {current_memory:.2f}MB vs "
                f"baseline {baseline_memory:.2f}MB (threshold: {memory_regression_threshold:.2f}MB)"
            )
            
            # Store current metrics
            await storage_manager.store_performance_metric(
                metric_name="single_scrape_memory_current",
                value=current_memory,
                tags={"test": "current", "operation": "single_scrape"}
            )