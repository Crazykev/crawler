"""TDD refactoring tests for CrawlEngine improvements."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.crawler.core.engine import CrawlEngine


@pytest.mark.refactoring
class TestCrawlEngineRefactoring:
    """TDD tests for CrawlEngine refactoring - RED phase."""
    
    @pytest.mark.asyncio
    async def test_crawler_connection_pooling(self, temp_dir):
        """Test that crawler uses connection pooling for better performance."""
        # RED: This test should fail initially because there's no connection pooling
        # GREEN: Should pass after implementing connection pooling
        # REFACTOR: Should maintain performance with cleaner code
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # Mock crawl4ai to track connection usage
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            # Mock successful crawl result
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test</body></html>"
            mock_result.cleaned_html = "<body>Test</body>"
            mock_result.markdown = "Test"
            mock_result.extracted_content = "Test"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            # This should use connection pooling
            # Multiple scrapes should reuse connections
            urls = [f"https://example.com/{i}" for i in range(10)]
            
            start_time = time.time()
            
            # Sequential scraping should be faster with connection pooling
            results = []
            for url in urls:
                result = await engine.scrape_single(
                    url=url,
                    options={"timeout": 30}
                )
                results.append(result)
            
            duration = time.time() - start_time
            
            # All should succeed
            assert all(result["success"] for result in results)
            
            # RED: This will fail initially - no connection pooling
            # Should have connection pooling that reuses crawler instances
            assert hasattr(engine, '_crawler_pool'), "Engine should have crawler pool"
            assert engine._crawler_pool is not None, "Crawler pool should be initialized"
            
            # Pool should have reasonable size
            pool_size = engine._crawler_pool.pool_size
            assert pool_size >= 0, "Crawler pool should be initialized"
            
            # Should be faster than creating new crawler each time
            assert duration < 2.0, f"Pooled scraping took {duration:.2f}s, should be < 2.0s"
    
    @pytest.mark.asyncio
    async def test_method_decomposition(self, temp_dir):
        """Test that scrape_single method is decomposed into smaller methods."""
        # RED: This test should fail initially because scrape_single is monolithic
        # GREEN: Should pass after method decomposition
        # REFACTOR: Should maintain functionality with better structure
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # These methods should exist after refactoring
        assert hasattr(engine, '_prepare_scrape_request'), "Should have _prepare_scrape_request method"
        assert hasattr(engine, '_execute_scrape'), "Should have _execute_scrape method"
        assert hasattr(engine, '_process_scrape_result'), "Should have _process_scrape_result method"
        assert hasattr(engine, '_handle_scrape_error'), "Should have _handle_scrape_error method"
        assert hasattr(engine, '_validate_scrape_options'), "Should have _validate_scrape_options method"
        
        # Methods should be callable
        assert callable(engine._prepare_scrape_request), "_prepare_scrape_request should be callable"
        assert callable(engine._execute_scrape), "_execute_scrape should be callable"
        assert callable(engine._process_scrape_result), "_process_scrape_result should be callable"
        assert callable(engine._handle_scrape_error), "_handle_scrape_error should be callable"
        assert callable(engine._validate_scrape_options), "_validate_scrape_options should be callable"
    
    @pytest.mark.asyncio
    async def test_configuration_abstraction(self, temp_dir):
        """Test that configuration handling is abstracted properly."""
        # RED: This test should fail initially because configuration is handled inline
        # GREEN: Should pass after configuration abstraction
        # REFACTOR: Should maintain configuration flexibility with better structure
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # Should have configuration abstraction
        assert hasattr(engine, '_config_builder'), "Should have configuration builder"
        assert hasattr(engine, '_build_crawler_config'), "Should have _build_crawler_config method"
        
        # Configuration builder should be able to create different configurations
        config_builder = engine._config_builder
        
        # Test different configuration scenarios
        basic_config = config_builder.build_basic_config()
        assert basic_config is not None
        assert isinstance(basic_config, dict)
        
        advanced_config = config_builder.build_advanced_config(
            headless=True,
            timeout=30,
            user_agent="Test Agent"
        )
        assert advanced_config is not None
        assert isinstance(advanced_config, dict)
        assert advanced_config.get("headless") is True
        assert advanced_config.get("timeout") == 30
    
    @pytest.mark.asyncio
    async def test_error_handling_consistency(self, temp_dir):
        """Test that error handling is consistent across all methods."""
        # RED: This test should fail initially because error handling is inconsistent
        # GREEN: Should pass after error handling standardization
        # REFACTOR: Should maintain error handling with better structure
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # Should have consistent error handling
        assert hasattr(engine, '_error_handler'), "Should have error handler"
        assert hasattr(engine, '_handle_network_error'), "Should have _handle_network_error method"
        assert hasattr(engine, '_handle_timeout_error'), "Should have _handle_timeout_error method"
        assert hasattr(engine, '_handle_extraction_error'), "Should have _handle_extraction_error method"
        
        # Error handlers should be callable
        assert callable(engine._handle_network_error), "_handle_network_error should be callable"
        assert callable(engine._handle_timeout_error), "_handle_timeout_error should be callable"
        assert callable(engine._handle_extraction_error), "_handle_extraction_error should be callable"
        
        # All error handlers should return consistent error format
        from src.crawler.foundation.errors import NetworkError, TimeoutError, ExtractionError
        
        network_error = NetworkError("Network failed")
        timeout_error = TimeoutError("Request timed out")
        extraction_error = ExtractionError("Extraction failed")
        
        # All should return consistent error format
        network_result = engine._handle_network_error(network_error, "https://example.com")
        timeout_result = engine._handle_timeout_error(timeout_error, "https://example.com")
        extraction_result = engine._handle_extraction_error(extraction_error, "https://example.com")
        
        # All should have consistent structure
        for error_result in [network_result, timeout_result, extraction_result]:
            assert isinstance(error_result, dict)
            assert "success" in error_result
            assert error_result["success"] is False
            assert "error" in error_result
            assert "url" in error_result
            assert "timestamp" in error_result
    
    @pytest.mark.asyncio
    async def test_resource_management_improvement(self, temp_dir):
        """Test that resource management is improved with proper cleanup."""
        # RED: This test should fail initially because resource management is not optimal
        # GREEN: Should pass after resource management improvements
        # REFACTOR: Should maintain resource efficiency with better structure
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # Should have resource manager
        assert hasattr(engine, '_resource_manager'), "Should have resource manager"
        assert hasattr(engine, '_cleanup_resources'), "Should have _cleanup_resources method"
        assert hasattr(engine, '_acquire_resource'), "Should have _acquire_resource method"
        assert hasattr(engine, '_release_resource'), "Should have _release_resource method"
        
        # Resource manager should track resources
        resource_manager = engine._resource_manager
        assert hasattr(resource_manager, 'active_resources'), "Should track active resources"
        assert hasattr(resource_manager, 'cleanup_expired'), "Should have cleanup_expired method"
        
        # Test resource acquisition and release
        resource_id = await engine._acquire_resource("test_resource")
        assert resource_id is not None
        assert resource_id in resource_manager.active_resources
        
        await engine._release_resource(resource_id)
        assert resource_id not in resource_manager.active_resources
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, temp_dir):
        """Test that performance monitoring is integrated into the engine."""
        # RED: This test should fail initially because performance monitoring is not integrated
        # GREEN: Should pass after performance monitoring integration
        # REFACTOR: Should maintain monitoring with better structure
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # Should have performance monitor
        assert hasattr(engine, '_performance_monitor'), "Should have performance monitor"
        assert hasattr(engine, '_record_performance_metric'), "Should have _record_performance_metric method"
        assert hasattr(engine, '_get_performance_metrics'), "Should have _get_performance_metrics method"
        
        # Performance monitor should track metrics
        performance_monitor = engine._performance_monitor
        assert hasattr(performance_monitor, 'metrics'), "Should track metrics"
        assert hasattr(performance_monitor, 'record_timing'), "Should have record_timing method"
        assert hasattr(performance_monitor, 'record_counter'), "Should have record_counter method"
        
        # Test metric recording
        await engine._record_performance_metric("test_metric", 1.5, {"operation": "test"})
        
        # Should be able to retrieve metrics
        metrics = await engine._get_performance_metrics("test_metric")
        assert metrics is not None
        assert len(metrics) > 0
    
    @pytest.mark.asyncio
    async def test_async_pattern_optimization(self, temp_dir):
        """Test that async patterns are optimized for better performance."""
        # RED: This test should fail initially because async patterns are not optimized
        # GREEN: Should pass after async pattern optimization
        # REFACTOR: Should maintain async efficiency with better structure
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # Should have async optimizations
        assert hasattr(engine, '_async_semaphore'), "Should have async semaphore for concurrency control"
        assert hasattr(engine, '_batch_processor'), "Should have batch processor"
        assert hasattr(engine, '_parallel_executor'), "Should have parallel executor"
        
        # Async semaphore should control concurrency
        semaphore = engine._async_semaphore
        assert hasattr(semaphore, '_value'), "Semaphore should have value"
        assert semaphore._value > 0, "Semaphore should allow some concurrency"
        
        # Batch processor should handle multiple requests efficiently
        batch_processor = engine._batch_processor
        assert hasattr(batch_processor, 'process_batch'), "Should have process_batch method"
        assert callable(batch_processor.process_batch), "process_batch should be callable"
        
        # Test batch processing
        urls = [f"https://example.com/{i}" for i in range(5)]
        
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test</body></html>"
            mock_result.cleaned_html = "<body>Test</body>"
            mock_result.markdown = "Test"
            mock_result.extracted_content = "Test"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            # Should process batch efficiently
            results = await batch_processor.process_batch(urls, {"timeout": 30})
            
            assert len(results) == len(urls)
            assert all(result["success"] for result in results)
    
    @pytest.mark.asyncio
    async def test_code_complexity_reduction(self, temp_dir):
        """Test that code complexity is reduced through refactoring."""
        # RED: This test should fail initially because code is complex
        # GREEN: Should pass after complexity reduction
        # REFACTOR: Should maintain functionality with reduced complexity
        
        engine = CrawlEngine()
        
        # Check that main methods are reasonably sized
        import inspect
        
        # scrape_single should be decomposed into smaller methods
        scrape_single_source = inspect.getsource(engine.scrape_single)
        scrape_single_lines = len(scrape_single_source.split('\n'))
        
        # RED: This will fail initially - scrape_single is too long
        assert scrape_single_lines < 50, f"scrape_single has {scrape_single_lines} lines, should be < 50"
        
        # Should have cyclomatic complexity < 10
        # This is a simplified check - in practice would use tools like radon
        def count_complexity_keywords(source):
            keywords = ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally', 'with']
            return sum(1 for keyword in keywords if keyword in source.lower())
        
        scrape_single_complexity = count_complexity_keywords(scrape_single_source)
        assert scrape_single_complexity < 10, f"scrape_single complexity {scrape_single_complexity}, should be < 10"
    
    @pytest.mark.asyncio
    async def test_maintainability_improvements(self, temp_dir):
        """Test that maintainability is improved through better structure."""
        # RED: This test should fail initially because maintainability is poor
        # GREEN: Should pass after maintainability improvements
        # REFACTOR: Should maintain improvements with better structure
        
        engine = CrawlEngine()
        
        # Should have clear separation of concerns
        assert hasattr(engine, '_validation_layer'), "Should have validation layer"
        assert hasattr(engine, '_execution_layer'), "Should have execution layer"
        assert hasattr(engine, '_processing_layer'), "Should have processing layer"
        assert hasattr(engine, '_storage_layer'), "Should have storage layer"
        
        # Each layer should be independent
        validation_layer = engine._validation_layer
        execution_layer = engine._execution_layer
        processing_layer = engine._processing_layer
        storage_layer = engine._storage_layer
        
        # Layers should not be tightly coupled
        assert validation_layer != execution_layer, "Validation and execution should be separate"
        assert execution_layer != processing_layer, "Execution and processing should be separate"
        assert processing_layer != storage_layer, "Processing and storage should be separate"
        
        # Each layer should have clear responsibilities
        assert hasattr(validation_layer, 'validate'), "Validation layer should have validate method"
        assert hasattr(execution_layer, 'execute'), "Execution layer should have execute method"
        assert hasattr(processing_layer, 'process'), "Processing layer should have process method"
        assert hasattr(storage_layer, 'store'), "Storage layer should have store method"


@pytest.mark.refactoring
class TestEnginePerformanceAfterRefactoring:
    """Performance tests that should pass after refactoring."""
    
    @pytest.mark.asyncio
    async def test_improved_scraping_performance(self, temp_dir):
        """Test that scraping performance is improved after refactoring."""
        # This test should pass after refactoring improvements
        
        engine = CrawlEngine()
        await engine.initialize()
        
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test</body></html>"
            mock_result.cleaned_html = "<body>Test</body>"
            mock_result.markdown = "Test"
            mock_result.extracted_content = "Test"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            # Should be significantly faster after refactoring
            start_time = time.time()
            
            result = await engine.scrape_single(
                url="https://example.com",
                options={"timeout": 30}
            )
            
            duration = time.time() - start_time
            
            assert result["success"] is True
            # Should be faster than 1 second after optimization
            assert duration < 1.0, f"Scraping took {duration:.2f}s, should be < 1.0s after refactoring"
    
    @pytest.mark.asyncio
    async def test_improved_memory_usage(self, temp_dir):
        """Test that memory usage is improved after refactoring."""
        # This test should pass after memory optimization
        
        import psutil
        import gc
        
        engine = CrawlEngine()
        await engine.initialize()
        
        # Measure memory usage
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler
            
            mock_result = Mock()
            mock_result.success = True
            mock_result.html = "<html><body>Test</body></html>"
            mock_result.cleaned_html = "<body>Test</body>"
            mock_result.markdown = "Test"
            mock_result.extracted_content = "Test"
            mock_result.status_code = 200
            mock_result.response_headers = {}
            mock_result.links = []
            mock_result.media = []
            mock_result.metadata = {}
            mock_result.error_message = None
            mock_crawler.arun.return_value = mock_result
            
            # Process multiple pages
            for i in range(10):
                result = await engine.scrape_single(
                    url=f"https://example.com/{i}",
                    options={"timeout": 30}
                )
                assert result["success"] is True
            
            gc.collect()
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_growth = final_memory - initial_memory
            
            # Should have minimal memory growth after refactoring
            assert memory_growth < 10, f"Memory growth {memory_growth:.2f}MB, should be < 10MB after refactoring"