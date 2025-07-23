"""Tests for scraping service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.crawler.services.scrape import ScrapeService
from src.crawler.foundation.errors import NetworkError, ValidationError


class TestScrapeService:
    """Test suite for ScrapeService."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, scrape_service_factory, mock_storage_manager, temp_dir):
        """Test service initialization."""
        # Create service from factory with mock storage manager
        scrape_service = scrape_service_factory(storage_manager=mock_storage_manager)
        
        # Mock the initialize method to avoid async generator issues
        mock_storage_manager.initialize = AsyncMock()
        
        # Mock the crawl engine initialize method as well
        scrape_service.crawl_engine.initialize = AsyncMock()
        
        # Mock the job manager initialize method
        scrape_service.job_manager.initialize = AsyncMock()
        scrape_service.job_manager.register_handler = Mock()  # Not async
        
        # Use a temporary database to avoid conflicts
        if hasattr(mock_storage_manager, 'db_path'):
            mock_storage_manager.db_path = str(temp_dir / "test_scrape.db")
        
        await scrape_service.initialize()
        
        # Service should be properly initialized
        assert scrape_service.crawl_engine is not None
        assert scrape_service.storage_manager is not None
        assert scrape_service.config_manager is not None
        
        # Verify that initialize was called on storage manager
        mock_storage_manager.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scrape_single_success(self, scrape_service, sample_scrape_result):
        """Test successful single page scraping."""
        url = "https://example.com"
        options = {"headless": True, "timeout": 10}
        
        # Mock the crawl engine response
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        result = await scrape_service.scrape_single(
            url=url,
            options=options,
            output_format="markdown"
        )
        
        assert result["success"] is True
        assert result["url"] == url
        assert result["title"] == "Example Page"
        assert result["content"] == "This is example content."
        
        # Verify crawl engine was called correctly
        scrape_service.crawl_engine.scrape_single.assert_called_once()
        call_args = scrape_service.crawl_engine.scrape_single.call_args
        assert call_args[1]["url"] == url
        # Check that our original options are present (service may add defaults)
        actual_options = call_args[1]["options"]
        assert actual_options["headless"] == options["headless"]
        assert actual_options["timeout"] == options["timeout"]
    
    @pytest.mark.asyncio
    async def test_scrape_single_with_extraction_strategy(self, scrape_service, sample_scrape_result):
        """Test scraping with extraction strategy."""
        url = "https://example.com"
        extraction_strategy = {
            "type": "css",
            "selectors": ".content"
        }
        
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        result = await scrape_service.scrape_single(
            url=url,
            extraction_strategy=extraction_strategy
        )
        
        assert result["success"] is True
        
        # Verify extraction strategy was passed
        call_args = scrape_service.crawl_engine.scrape_single.call_args
        assert call_args[1]["extraction_strategy"] == extraction_strategy
    
    @pytest.mark.asyncio
    async def test_scrape_single_network_error(self, scrape_service):
        """Test scraping with network error."""
        url = "https://example.com"
        
        # Mock network error
        scrape_service.crawl_engine.scrape_single.side_effect = NetworkError(
            "Connection failed", status_code=500
        )
        
        result = await scrape_service.scrape_single(url=url)
        
        assert result["success"] is False
        assert result["error"] == "Connection failed"
        assert result["url"] == url
    
    @pytest.mark.asyncio
    async def test_scrape_single_invalid_url(self, scrape_service):
        """Test scraping with invalid URL."""
        invalid_url = "not-a-url"
        
        result = await scrape_service.scrape_single(url=invalid_url)
        
        assert result["success"] is False
        assert "invalid" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_scrape_single_with_session(self, scrape_service, sample_scrape_result):
        """Test scraping with session ID."""
        url = "https://example.com"
        session_id = "test-session-123"
        
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        result = await scrape_service.scrape_single(
            url=url,
            session_id=session_id
        )
        
        assert result["success"] is True
        
        # Verify session ID was passed
        call_args = scrape_service.crawl_engine.scrape_single.call_args
        assert call_args[1]["session_id"] == session_id
    
    @pytest.mark.asyncio
    async def test_scrape_single_store_result(self, scrape_service, sample_scrape_result):
        """Test scraping with result storage."""
        url = "https://example.com"
        
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        scrape_service.storage_manager.store_crawl_result = AsyncMock()
        
        result = await scrape_service.scrape_single(
            url=url,
            store_result=True
        )
        
        assert result["success"] is True
        
        # Verify result was stored
        scrape_service.storage_manager.store_crawl_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scrape_batch_success(self, scrape_service, sample_scrape_result):
        """Test successful batch scraping."""
        urls = ["https://example.com", "https://test.com"]
        
        # Mock successful responses for both URLs
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        results = await scrape_service.scrape_batch(
            urls=urls,
            concurrent_requests=2
        )
        
        assert len(results) == 2
        assert all(result["success"] for result in results)
        assert results[0]["url"] == urls[0]
        assert results[1]["url"] == urls[1]
        
        # Verify both URLs were processed
        assert scrape_service.crawl_engine.scrape_single.call_count == 2
    
    @pytest.mark.asyncio
    async def test_scrape_batch_partial_failure(self, scrape_service, sample_scrape_result):
        """Test batch scraping with some failures."""
        urls = ["https://example.com", "https://bad-url.com"]
        
        # First URL succeeds, second fails
        async def mock_scrape(url, **kwargs):
            if "bad-url" in url:
                raise NetworkError("Connection failed")
            return sample_scrape_result
        
        scrape_service.crawl_engine.scrape_single.side_effect = mock_scrape
        
        results = await scrape_service.scrape_batch(
            urls=urls,
            continue_on_error=True
        )
        
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "Connection failed" in results[1]["error"]
    
    @pytest.mark.asyncio
    async def test_scrape_batch_stop_on_error(self, scrape_service):
        """Test batch scraping that stops on first error."""
        urls = ["https://bad-url.com", "https://example.com"]
        
        # First URL fails
        scrape_service.crawl_engine.scrape_single.side_effect = NetworkError("Connection failed")
        
        with pytest.raises(NetworkError):
            await scrape_service.scrape_batch(
                urls=urls,
                continue_on_error=False
            )
    
    @pytest.mark.asyncio
    async def test_scrape_batch_with_delay(self, scrape_service, sample_scrape_result):
        """Test batch scraping with delay between requests."""
        urls = ["https://example.com", "https://test.com"]
        
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        start_time = datetime.now()
        results = await scrape_service.scrape_batch(
            urls=urls,
            concurrent_requests=1,  # Sequential processing
            delay=0.1  # Small delay for testing
        )
        end_time = datetime.now()
        
        assert len(results) == 2
        assert all(result["success"] for result in results)
        
        # Should take at least the delay time
        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.1
    
    @pytest.mark.asyncio
    async def test_scrape_single_async(self, scrape_service):
        """Test async job submission for single page scraping."""
        url = "https://example.com"
        options = {"headless": True}
        
        # Mock job manager
        scrape_service.job_manager = Mock()
        scrape_service.job_manager.submit_job = AsyncMock(return_value="job-123")
        
        job_id = await scrape_service.scrape_single_async(
            url=url,
            options=options,
            priority=5
        )
        
        assert job_id == "job-123"
        
        # Verify job was submitted correctly
        scrape_service.job_manager.submit_job.assert_called_once()
        call_args = scrape_service.job_manager.submit_job.call_args
        
        job_data = call_args[1]["job_data"]
        assert job_data["url"] == url
        assert job_data["options"] == options
        assert call_args[1]["priority"] == 5
    
    @pytest.mark.asyncio
    async def test_scrape_batch_async(self, scrape_service):
        """Test async job submission for batch scraping."""
        urls = ["https://example.com", "https://test.com"]
        
        # Mock job manager
        scrape_service.job_manager = Mock()
        scrape_service.job_manager.submit_job = AsyncMock(return_value="batch-job-456")
        
        job_id = await scrape_service.scrape_batch_async(
            urls=urls,
            concurrent_requests=3
        )
        
        assert job_id == "batch-job-456"
        
        # Verify job was submitted
        scrape_service.job_manager.submit_job.assert_called_once()
        call_args = scrape_service.job_manager.submit_job.call_args
        
        job_data = call_args[1]["job_data"]
        assert job_data["urls"] == urls
        assert job_data["concurrent_requests"] == 3
    
    @pytest.mark.asyncio
    async def test_validate_url_valid(self, scrape_service):
        """Test URL validation with valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://test.com/path",
            "https://subdomain.example.com/path?query=value"
        ]
        
        for url in valid_urls:
            # Should not raise exception
            scrape_service._validate_url(url)
    
    def test_validate_url_invalid(self, scrape_service):
        """Test URL validation with invalid URLs."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com",
            "javascript:alert('xss')",
            None
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                scrape_service._validate_url(url)
    
    @pytest.mark.asyncio
    async def test_prepare_options(self, scrape_service):
        """Test option preparation and merging."""
        user_options = {
            "timeout": 20,
            "headless": False,
            "custom_option": "value"
        }
        
        prepared_options = scrape_service._prepare_options(user_options)
        
        # Should contain user options
        assert prepared_options["timeout"] == 20
        assert prepared_options["headless"] is False
        assert prepared_options["custom_option"] == "value"
        
        # Should contain default options
        assert "user_agent" in prepared_options
    
    def test_format_result_markdown(self, scrape_service, sample_scrape_result):
        """Test result formatting for markdown output."""
        formatted = scrape_service._format_result(sample_scrape_result, "markdown")
        
        assert formatted["content"] == sample_scrape_result["content"]
        assert formatted["success"] is True
        assert formatted["url"] == sample_scrape_result["url"]
    
    def test_format_result_json(self, scrape_service, sample_scrape_result):
        """Test result formatting for JSON output."""
        formatted = scrape_service._format_result(sample_scrape_result, "json")
        
        # Should contain all original data
        assert "content" in formatted
        assert "links" in formatted
        assert "images" in formatted
        assert "metadata" in formatted
    
    def test_format_result_text(self, scrape_service, sample_scrape_result):
        """Test result formatting for plain text output."""
        formatted = scrape_service._format_result(sample_scrape_result, "text")
        
        # Should extract plain text content
        assert formatted["content"] == sample_scrape_result["content"]
        assert formatted["success"] is True
    
    @pytest.mark.asyncio
    async def test_job_handler_scrape_single(self, scrape_service, sample_scrape_result):
        """Test job handler for single page scraping."""
        job_data = {
            "url": "https://example.com",
            "options": {"headless": True},
            "output_format": "markdown"
        }
        
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        result = await scrape_service._handle_scrape_job(job_data)
        
        assert result["success"] is True
        assert "result" in result
        assert result["result"]["url"] == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_job_handler_scrape_batch(self, scrape_service, sample_scrape_result):
        """Test job handler for batch scraping."""
        job_data = {
            "urls": ["https://example.com", "https://test.com"],
            "concurrent_requests": 2,
            "output_format": "json"
        }
        
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        result = await scrape_service._handle_batch_scrape_job(job_data)
        
        assert result["success"] is True
        assert "results" in result
        assert len(result["results"]) == 2


@pytest.mark.integration
class TestScrapeServiceIntegration:
    """Integration tests for ScrapeService."""
    
    @pytest.mark.asyncio
    async def test_full_scrape_workflow(self, scrape_service, sample_scrape_result):
        """Test complete scraping workflow."""
        url = "https://example.com"
        
        # Mock storage
        scrape_service.storage_manager.store_crawl_result = AsyncMock()
        scrape_service.crawl_engine.scrape_single.return_value = sample_scrape_result
        
        # Scrape with storage
        result = await scrape_service.scrape_single(
            url=url,
            options={"timeout": 15},
            extraction_strategy={"type": "auto"},
            output_format="markdown",
            store_result=True
        )
        
        # Verify result
        assert result["success"] is True
        assert result["url"] == url
        
        # Verify storage was called
        scrape_service.storage_manager.store_crawl_result.assert_called_once()
        
        # Verify crawl engine was called with correct parameters
        call_args = scrape_service.crawl_engine.scrape_single.call_args
        assert call_args[1]["url"] == url
        assert call_args[1]["options"]["timeout"] == 15
        assert call_args[1]["extraction_strategy"]["type"] == "auto"
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_retry(self, scrape_service, sample_scrape_result):
        """Test error recovery and retry mechanisms."""
        url = "https://example.com"
        
        # First call fails, second succeeds
        call_count = 0
        async def mock_scrape(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("Temporary failure", status_code=503)
            return sample_scrape_result
        
        scrape_service.crawl_engine.scrape_single.side_effect = mock_scrape
        
        with patch('crawler.services.scrape.asyncio.sleep'):  # Speed up test
            result = await scrape_service.scrape_single(
                url=url,
                options={"retry_attempts": 2}
            )
        
        assert result["success"] is True
        assert call_count == 2  # Failed once, then succeeded