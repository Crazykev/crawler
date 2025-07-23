"""Tests for the core crawling engine."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urljoin

import pytest

from src.crawler.core.engine import CrawlEngine, get_crawl_engine
from src.crawler.foundation.errors import (
    NetworkError, TimeoutError, ExtractionError, ConfigurationError
)


class TestCrawlEngine:
    """Test core crawling engine functionality."""
    
    def test_crawl_engine_initialization(self):
        """Test crawl engine initialization."""
        engine = CrawlEngine()
        
        assert hasattr(engine, 'logger')
        assert hasattr(engine, 'config_manager')
        assert hasattr(engine, 'metrics')
        assert hasattr(engine, 'storage_manager')
        assert engine._crawler is None
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_asyncwebcrawler):
        """Test successful engine initialization."""
        engine = CrawlEngine()
        
        # Mock storage manager initialization
        engine.storage_manager = Mock()
        engine.storage_manager.initialize = AsyncMock()
        
        await engine.initialize()
        
        engine.storage_manager.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test engine initialization failure when crawl4ai not available."""
        with patch('src.crawler.core.engine.AsyncWebCrawler', None):
            engine = CrawlEngine()
            
            with pytest.raises(ConfigurationError, match="crawl4ai library not available"):
                await engine.initialize()
    
    @pytest.mark.asyncio
    async def test_get_crawler_default_config(self, mock_asyncwebcrawler):
        """Test getting crawler with default configuration."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.side_effect = lambda key, default: {
            "browser.headless": True,
            "browser.user_agent": "TestCrawler/1.0",
            "browser.viewport_width": 1920,
            "browser.viewport_height": 1080
        }.get(key, default)
        
        crawler = await engine._get_crawler()
        
        assert crawler is not None
        # Verify we got the mocked crawler instance
        assert crawler == mock_asyncwebcrawler
    
    @pytest.mark.asyncio
    async def test_get_crawler_custom_config(self, mock_asyncwebcrawler):
        """Test getting crawler with custom browser configuration."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.return_value = "default"
        
        browser_config = {
            "headless": False,
            "timeout": 60,
            "user_agent": "CustomBot/1.0",
            "viewport_width": 1024,
            "viewport_height": 768
        }
        
        crawler = await engine._get_crawler(browser_config)
        
        assert crawler is not None
        # Verify we got the mocked crawler instance
        assert crawler == mock_asyncwebcrawler
    
    @pytest.mark.asyncio
    async def test_get_crawler_without_crawl4ai(self):
        """Test getting crawler when crawl4ai is not available."""
        with patch('src.crawler.core.engine.AsyncWebCrawler', None):
            engine = CrawlEngine()
            
            with pytest.raises(ConfigurationError, match="crawl4ai library not available"):
                await engine._get_crawler()
    
    def test_translate_extraction_strategy_css(self):
        """Test translating CSS extraction strategy."""
        engine = CrawlEngine()
        
        # Test simple CSS selector
        strategy_config = {
            "type": "css",
            "selectors": ".content"
        }
        
        with patch('crawl4ai.extraction_strategy.JsonCssExtractionStrategy') as mock_css:
            mock_strategy = Mock()
            mock_css.return_value = mock_strategy
            
            result = engine._translate_extraction_strategy(strategy_config)
            
            assert result == mock_strategy
            mock_css.assert_called_once_with({"content": ".content"})
    
    def test_translate_extraction_strategy_css_multiple(self):
        """Test translating CSS extraction strategy with multiple selectors."""
        engine = CrawlEngine()
        
        strategy_config = {
            "type": "css",
            "selectors": {
                "title": "h1",
                "content": ".article-content",
                "author": ".byline"
            }
        }
        
        with patch('crawl4ai.extraction_strategy.JsonCssExtractionStrategy') as mock_css:
            mock_strategy = Mock()
            mock_css.return_value = mock_strategy
            
            result = engine._translate_extraction_strategy(strategy_config)
            
            assert result == mock_strategy
            mock_css.assert_called_once_with(strategy_config["selectors"])
    
    def test_translate_extraction_strategy_llm(self):
        """Test translating LLM extraction strategy."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.return_value = "test-api-key"
        
        strategy_config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "prompt": "Extract the main content"
        }
        
        with patch('crawl4ai.extraction_strategy.LLMExtractionStrategy') as mock_llm:
            mock_strategy = Mock()
            mock_llm.return_value = mock_strategy
            
            result = engine._translate_extraction_strategy(strategy_config)
            
            assert result == mock_strategy
            mock_llm.assert_called_once_with(
                provider="openai",
                api_token="test-api-key",
                instruction="Extract the main content"
            )
    
    def test_translate_extraction_strategy_llm_no_api_key(self):
        """Test translating LLM extraction strategy without API key."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.return_value = None
        engine.logger = Mock()
        
        strategy_config = {
            "type": "llm",
            "model": "openai/gpt-4o-mini",
            "prompt": "Extract the main content"
        }
        
        result = engine._translate_extraction_strategy(strategy_config)
        
        assert result is None
        engine.logger.warning.assert_called_once()
    
    def test_translate_extraction_strategy_json(self):
        """Test translating JSON schema extraction strategy."""
        engine = CrawlEngine()
        
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"}
            }
        }
        
        strategy_config = {
            "type": "json",
            "schema": schema
        }
        
        with patch('crawl4ai.extraction_strategy.JsonCssExtractionStrategy') as mock_json:
            mock_strategy = Mock()
            mock_json.return_value = mock_strategy
            
            result = engine._translate_extraction_strategy(strategy_config)
            
            assert result == mock_strategy
            mock_json.assert_called_once_with(schema)
    
    def test_translate_extraction_strategy_auto(self):
        """Test translating auto extraction strategy."""
        engine = CrawlEngine()
        
        strategy_config = {"type": "auto"}
        
        result = engine._translate_extraction_strategy(strategy_config)
        
        assert result is None  # Auto strategy returns None (use default)
    
    def test_translate_extraction_strategy_unknown(self):
        """Test translating unknown extraction strategy."""
        engine = CrawlEngine()
        
        strategy_config = {"type": "unknown_strategy"}
        
        result = engine._translate_extraction_strategy(strategy_config)
        
        assert result is None
    
    def test_translate_extraction_strategy_exception(self):
        """Test handling exception in extraction strategy translation."""
        engine = CrawlEngine()
        engine.logger = Mock()
        
        strategy_config = {
            "type": "css",
            "selectors": ".content"
        }
        
        with patch('crawl4ai.extraction_strategy.JsonCssExtractionStrategy', side_effect=Exception("Import error")):
            result = engine._translate_extraction_strategy(strategy_config)
            
            assert result is None
            engine.logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scrape_single_success(self, mock_asyncwebcrawler):
        """Test successful single page scraping."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.storage_manager.get_cached_result = AsyncMock(return_value=None)
        engine.storage_manager.store_cached_result = AsyncMock()
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        engine.metrics.record_timing = Mock()
        
        # Mock successful crawl result
        mock_result = Mock()
        mock_result.success = True
        mock_result.status_code = 200
        mock_result.markdown = "# Test Page\n\nContent"
        mock_result.html = "<html><head><title>Test</title></head><body><h1>Test Page</h1><p>Content</p></body></html>"
        mock_result.cleaned_html = "Test Page\n\nContent"
        mock_result.metadata = {"title": "Test Page"}
        mock_result.links = []
        mock_result.media = []
        mock_asyncwebcrawler.arun.return_value = mock_result
        
        url = "https://example.com"
        result = await engine.scrape_single(url)
        
        assert result["url"] == url
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["title"] == "Test Page"
        assert "content" in result
        assert "metadata" in result
        
        # Verify metrics were recorded
        engine.metrics.increment_counter.assert_called()
        engine.metrics.record_timing.assert_called()
    
    @pytest.mark.asyncio
    async def test_scrape_single_cache_hit(self, mock_asyncwebcrawler):
        """Test single page scraping with cache hit."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        
        # Mock cache hit
        cached_result = {"url": "https://example.com", "cached": True}
        engine.storage_manager.get_cached_result = AsyncMock(return_value=cached_result)
        
        url = "https://example.com"
        result = await engine.scrape_single(url, options={"cache_enabled": True})
        
        assert result == cached_result
        engine.metrics.increment_counter.assert_called_with("crawl_engine.cache_hits")
        
        # Verify crawler was not called
        mock_asyncwebcrawler.arun.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_scrape_single_failed_crawl(self, mock_asyncwebcrawler):
        """Test single page scraping with failed crawl."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.storage_manager.get_cached_result = AsyncMock(return_value=None)
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        
        # Mock failed crawl result
        mock_result = Mock()
        mock_result.success = False
        mock_result.status_code = 404
        mock_result.error_message = "Page not found"
        mock_asyncwebcrawler.arun.return_value = mock_result
        
        url = "https://example.com/notfound"
        
        with pytest.raises(NetworkError, match="Crawl failed"):
            await engine.scrape_single(url)
        
        # Check that cache miss was incremented (normal flow)
        engine.metrics.increment_counter.assert_any_call("crawl_engine.cache_misses")
    
    @pytest.mark.asyncio
    async def test_scrape_single_timeout(self, mock_asyncwebcrawler):
        """Test single page scraping with timeout."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.storage_manager.get_cached_result = AsyncMock(return_value=None)
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        
        # Mock timeout exception
        mock_asyncwebcrawler.arun.side_effect = asyncio.TimeoutError("Request timed out")
        
        url = "https://example.com"
        
        with pytest.raises(TimeoutError, match="Timeout scraping"):
            await engine.scrape_single(url)
        
        # Check that both cache miss and timeout metrics were incremented
        engine.metrics.increment_counter.assert_any_call("crawl_engine.cache_misses")
        engine.metrics.increment_counter.assert_any_call("crawl_engine.scrapes.timeout")
    
    @pytest.mark.asyncio
    async def test_scrape_single_network_error(self, mock_asyncwebcrawler):
        """Test single page scraping with network error."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.storage_manager.get_cached_result = AsyncMock(return_value=None)
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        
        # Mock connection error
        mock_asyncwebcrawler.arun.side_effect = Exception("Connection refused")
        
        url = "https://example.com"
        
        with pytest.raises(NetworkError, match="Network error scraping"):
            await engine.scrape_single(url)
        
        # Check that both cache miss and error metrics were incremented
        engine.metrics.increment_counter.assert_any_call("crawl_engine.cache_misses")
        engine.metrics.increment_counter.assert_any_call("crawl_engine.scrapes.error")
    
    @pytest.mark.asyncio
    async def test_scrape_single_with_extraction_strategy(self, mock_asyncwebcrawler):
        """Test single page scraping with extraction strategy."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.storage_manager.get_cached_result = AsyncMock(return_value=None)
        engine.storage_manager.store_cached_result = AsyncMock()
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        engine.metrics.record_timing = Mock()
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.status_code = 200
        mock_result.markdown = "# Test"
        mock_result.html = "<html></html>"
        mock_result.cleaned_html = "Test"
        mock_result.metadata = {}
        mock_result.links = []
        mock_result.media = []
        mock_asyncwebcrawler.arun.return_value = mock_result
        
        extraction_strategy = {
            "type": "css",
            "selectors": ".content"
        }
        
        with patch.object(engine, '_translate_extraction_strategy') as mock_translate:
            mock_strategy = Mock()
            mock_translate.return_value = mock_strategy
            
            result = await engine.scrape_single(
                "https://example.com",
                extraction_strategy=extraction_strategy
            )
            
            assert result["success"] is True
            mock_translate.assert_called_once_with(extraction_strategy)
            
            # Verify strategy was passed to crawler
            call_args = mock_asyncwebcrawler.arun.call_args[1]
            assert call_args["extraction_strategy"] == mock_strategy
    
    @pytest.mark.asyncio
    async def test_scrape_single_with_js_code(self, mock_asyncwebcrawler):
        """Test single page scraping with JavaScript code."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.storage_manager.get_cached_result = AsyncMock(return_value=None)
        engine.storage_manager.store_cached_result = AsyncMock()
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        engine.metrics.record_timing = Mock()
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.status_code = 200
        mock_result.markdown = "# Test"
        mock_result.html = "<html></html>"
        mock_result.cleaned_html = "Test"
        mock_result.metadata = {}
        mock_result.links = []
        mock_result.media = []
        mock_asyncwebcrawler.arun.return_value = mock_result
        
        options = {
            "js_code": "document.querySelector('button').click();",
            "wait_for": ".loaded-content"
        }
        
        result = await engine.scrape_single("https://example.com", options=options)
        
        assert result["success"] is True
        
        # Verify JS code and wait_for were passed to crawler
        call_args = mock_asyncwebcrawler.arun.call_args[1]
        assert call_args["js_code"] == options["js_code"]
        assert call_args["wait_for"] == options["wait_for"]
    
    @pytest.mark.asyncio
    async def test_scrape_batch_success(self, mock_asyncwebcrawler):
        """Test successful batch scraping."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.return_value = 5
        engine.metrics = Mock()
        engine.metrics.record_metric = Mock()
        
        # Mock individual scrape results
        with patch.object(engine, 'scrape_single') as mock_scrape:
            mock_scrape.side_effect = [
                {"url": "https://example.com/1", "success": True},
                {"url": "https://example.com/2", "success": True},
                {"url": "https://example.com/3", "success": False, "error": "Failed"}
            ]
            
            urls = [
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3"
            ]
            
            results = await engine.scrape_batch(urls)
            
            assert len(results) == 3
            assert results[0]["success"] is True
            assert results[1]["success"] is True
            assert results[2]["success"] is False
            
            # Verify metrics were recorded
            engine.metrics.record_metric.assert_called()
    
    @pytest.mark.asyncio
    async def test_scrape_batch_concurrency_limit(self, mock_asyncwebcrawler):
        """Test batch scraping with concurrency limit."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.return_value = 2  # Lower limit
        engine.metrics = Mock()
        engine.metrics.record_metric = Mock()
        
        with patch.object(engine, 'scrape_single') as mock_scrape:
            mock_scrape.return_value = {"success": True}
            
            urls = ["https://example.com/{}".format(i) for i in range(10)]
            
            results = await engine.scrape_batch(urls, max_concurrent=10)
            
            # Should be limited by config setting (2)
            assert len(results) == 10
            assert mock_scrape.call_count == 10
    
    @pytest.mark.asyncio
    async def test_scrape_batch_with_errors(self, mock_asyncwebcrawler):
        """Test batch scraping with individual failures."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.return_value = 5
        engine.metrics = Mock()
        engine.metrics.record_metric = Mock()
        
        with patch.object(engine, 'scrape_single') as mock_scrape:
            # Mix of success and failure
            mock_scrape.side_effect = [
                {"url": "https://example.com/1", "success": True},
                Exception("Network error"),
                {"url": "https://example.com/3", "success": True}
            ]
            
            urls = [
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3"
            ]
            
            results = await engine.scrape_batch(urls)
            
            assert len(results) == 3
            assert results[0]["success"] is True
            assert results[1]["success"] is False
            assert "error" in results[1]
            assert results[2]["success"] is True
    
    def test_extract_links_from_crawl_result(self):
        """Test link extraction from crawl result."""
        engine = CrawlEngine()
        
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.links = [
            {"href": "https://example.com/page1", "text": "Page 1"},
            {"href": "/page2", "text": "Page 2"},
            "https://external.com/page3"
        ]
        
        links = engine._extract_links(mock_result)
        
        assert len(links) == 3
        assert links[0]["url"] == "https://example.com/page1"
        assert links[0]["text"] == "Page 1"
        assert links[0]["type"] == "internal"
        assert links[1]["url"] == "/page2"
        assert links[2]["url"] == "https://external.com/page3"
    
    def test_extract_links_exception_handling(self):
        """Test link extraction with exception handling."""
        engine = CrawlEngine()
        engine.logger = Mock()
        
        mock_result = Mock()
        # Create a mock that raises an exception when accessed
        mock_result.links = Mock()
        mock_result.links.__iter__ = Mock(side_effect=Exception("Test exception"))
        
        links = engine._extract_links(mock_result)
        
        assert links == []
        engine.logger.warning.assert_called_once()
    
    def test_extract_images_from_crawl_result(self):
        """Test image extraction from crawl result."""
        engine = CrawlEngine()
        
        mock_result = Mock()
        mock_result.media = [
            {
                "type": "image",
                "src": "https://example.com/image1.jpg",
                "alt": "Image 1",
                "width": 800,
                "height": 600
            },
            {
                "type": "video",  # Should be ignored
                "src": "https://example.com/video.mp4"
            },
            {
                "type": "image",
                "src": "/image2.png",
                "alt": "Image 2"
            }
        ]
        
        images = engine._extract_images(mock_result)
        
        assert len(images) == 2
        assert images[0]["src"] == "https://example.com/image1.jpg"
        assert images[0]["alt"] == "Image 1"
        assert images[0]["width"] == 800
        assert images[1]["src"] == "/image2.png"
        assert images[1]["alt"] == "Image 2"
    
    def test_extract_images_exception_handling(self):
        """Test image extraction with exception handling."""
        engine = CrawlEngine()
        engine.logger = Mock()
        
        mock_result = Mock()
        # Create a mock that raises an exception when accessed
        mock_result.media = Mock()
        mock_result.media.__iter__ = Mock(side_effect=Exception("Test exception"))
        
        images = engine._extract_images(mock_result)
        
        assert images == []
        engine.logger.warning.assert_called_once()
    
    def test_classify_link_type_internal(self):
        """Test classifying internal links."""
        engine = CrawlEngine()
        
        base_url = "https://example.com/page"
        
        # Same domain
        assert engine._classify_link_type("https://example.com/other", base_url) == "internal"
        # Relative URL
        assert engine._classify_link_type("/other", base_url) == "internal"
        assert engine._classify_link_type("other.html", base_url) == "internal"
    
    def test_classify_link_type_subdomain(self):
        """Test classifying subdomain links."""
        engine = CrawlEngine()
        
        base_url = "https://example.com/page"
        
        assert engine._classify_link_type("https://blog.example.com/post", base_url) == "subdomain"
        assert engine._classify_link_type("https://www.example.com/page", base_url) == "subdomain"
    
    def test_classify_link_type_external(self):
        """Test classifying external links."""
        engine = CrawlEngine()
        
        base_url = "https://example.com/page"
        
        assert engine._classify_link_type("https://google.com", base_url) == "external"
        assert engine._classify_link_type("https://other-domain.com/page", base_url) == "external"
    
    def test_classify_link_type_unknown(self):
        """Test classifying unknown or invalid links."""
        engine = CrawlEngine()
        
        base_url = "https://example.com/page"
        
        assert engine._classify_link_type("", base_url) == "unknown"
        assert engine._classify_link_type(None, base_url) == "unknown"
    
    def test_classify_link_type_exception_handling(self):
        """Test link classification with malformed URLs."""
        engine = CrawlEngine()
        
        base_url = "invalid-url"
        link_url = "also-invalid"
        
        result = engine._classify_link_type(link_url, base_url)
        
        assert result == "unknown"
    
    @pytest.mark.asyncio
    async def test_extract_links_from_page_success(self, mock_asyncwebcrawler):
        """Test extracting links from a page for crawling."""
        engine = CrawlEngine()
        
        with patch.object(engine, 'scrape_single') as mock_scrape:
            mock_scrape.return_value = {
                "success": True,
                "links": [
                    {"url": "https://example.com/page1", "text": "Page 1"},
                    {"url": "/page2", "text": "Page 2"},
                    {"url": "https://external.com/page", "text": "External"}
                ]
            }
            
            url = "https://example.com"
            include_patterns = [r".*example\.com.*"]
            exclude_patterns = [r".*external.*"]
            
            discovered_urls = await engine.extract_links_from_page(
                url, include_patterns=include_patterns, exclude_patterns=exclude_patterns
            )
            
            # Should include absolute internal URL and relative URL (converted to absolute)
            # Should exclude external URL based on pattern
            assert "https://example.com/page1" in discovered_urls
            assert "https://example.com/page2" in discovered_urls
            assert "https://external.com/page" not in discovered_urls
    
    @pytest.mark.asyncio
    async def test_extract_links_from_page_failed_scrape(self, mock_asyncwebcrawler):
        """Test extracting links from page when scraping fails."""
        engine = CrawlEngine()
        
        with patch.object(engine, 'scrape_single') as mock_scrape:
            mock_scrape.return_value = {"success": False, "error": "Failed"}
            
            discovered_urls = await engine.extract_links_from_page("https://example.com")
            
            assert discovered_urls == []
    
    @pytest.mark.asyncio
    async def test_extract_links_from_page_exception(self, mock_asyncwebcrawler):
        """Test extracting links from page with exception."""
        engine = CrawlEngine()
        engine.logger = Mock()
        
        with patch.object(engine, 'scrape_single', side_effect=Exception("Scrape failed")):
            discovered_urls = await engine.extract_links_from_page("https://example.com")
            
            assert discovered_urls == []
            engine.logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_engine(self):
        """Test closing the crawl engine."""
        engine = CrawlEngine()
        engine.logger = Mock()
        
        # Mock crawler
        mock_crawler = AsyncMock()
        engine._crawler = mock_crawler
        
        await engine.close()
        
        mock_crawler.close.assert_called_once()
        assert engine._crawler is None
        engine.logger.info.assert_called_with("Crawl engine closed")
    
    @pytest.mark.asyncio
    async def test_close_engine_exception(self):
        """Test closing engine with exception."""
        engine = CrawlEngine()
        engine.logger = Mock()
        
        # Mock crawler that raises exception on close
        mock_crawler = AsyncMock()
        mock_crawler.close.side_effect = Exception("Close failed")
        engine._crawler = mock_crawler
        
        await engine.close()
        
        engine.logger.error.assert_called_with("Error closing crawl engine: Close failed")


class TestCrawlEngineSingleton:
    """Test crawl engine singleton behavior."""
    
    def test_get_crawl_engine_singleton(self):
        """Test that get_crawl_engine returns singleton instance."""
        # Reset singleton for clean test
        import src.crawler.core.engine as engine_module
        engine_module._crawl_engine = None
        
        engine1 = get_crawl_engine()
        engine2 = get_crawl_engine()
        
        assert engine1 is engine2
        assert isinstance(engine1, CrawlEngine)


@pytest.mark.integration
class TestCrawlEngineIntegration:
    """Integration tests for crawl engine."""
    
    @pytest.mark.asyncio
    async def test_full_scraping_workflow(self, mock_asyncwebcrawler):
        """Test complete scraping workflow from URL to storage."""
        engine = CrawlEngine()
        
        # Use a simple mock storage manager for this test
        mock_storage_manager = Mock()
        mock_storage_manager.initialize = AsyncMock()
        mock_storage_manager.get_cached_result = AsyncMock(return_value=None)
        mock_storage_manager.store_cached_result = AsyncMock()
        engine.storage_manager = mock_storage_manager
        
        # Mock successful crawl
        mock_result = Mock()
        mock_result.success = True
        mock_result.status_code = 200
        mock_result.markdown = "# Test Page"
        mock_result.html = "<html><h1>Test Page</h1></html>"
        mock_result.cleaned_html = "Test Page"
        mock_result.metadata = {"title": "Test Page"}
        mock_result.links = []
        mock_result.media = []
        mock_asyncwebcrawler.arun.return_value = mock_result
        
        await engine.initialize()
        
        url = "https://example.com"
        result = await engine.scrape_single(url)
        
        assert result["success"] is True
        assert result["url"] == url
        assert result["title"] == "Test Page"
        assert "content" in result
        assert "metadata" in result
        
    @pytest.mark.asyncio
    async def test_batch_scraping_with_mixed_results(self, mock_asyncwebcrawler):
        """Test batch scraping with mix of successful and failed requests."""
        engine = CrawlEngine()
        engine.config_manager = Mock()
        engine.config_manager.get_setting.return_value = 3
        engine.metrics = Mock()
        engine.metrics.record_metric = Mock()
        
        urls = [
            "https://example.com/1",
            "https://example.com/2", 
            "https://example.com/3",
            "https://invalid-url.test"
        ]
        
        # Mock different responses for different URLs
        def mock_scrape_single(url, *args, **kwargs):
            if "invalid" in url:
                raise NetworkError("Domain not found")
            return {"url": url, "success": True, "content": "Test content"}
        
        with patch.object(engine, 'scrape_single', side_effect=mock_scrape_single):
            results = await engine.scrape_batch(urls)
            
            assert len(results) == 4
            assert results[0]["success"] is True
            assert results[1]["success"] is True
            assert results[2]["success"] is True
            assert results[3]["success"] is False
            assert "error" in results[3]
            
    @pytest.mark.asyncio
    async def test_link_discovery_and_filtering(self, mock_asyncwebcrawler):
        """Test link discovery with include/exclude patterns."""
        engine = CrawlEngine()
        
        # Mock page with various links
        with patch.object(engine, 'scrape_single') as mock_scrape:
            mock_scrape.return_value = {
                "success": True,
                "links": [
                    {"url": "https://example.com/blog/post1", "text": "Blog Post 1"},
                    {"url": "https://example.com/blog/post2", "text": "Blog Post 2"},
                    {"url": "https://example.com/admin/panel", "text": "Admin Panel"},
                    {"url": "https://example.com/contact", "text": "Contact"},
                    {"url": "https://external.com/page", "text": "External Page"}
                ]
            }
            
            include_patterns = [r".*blog.*", r".*contact.*"]
            exclude_patterns = [r".*admin.*"]
            
            discovered_urls = await engine.extract_links_from_page(
                "https://example.com",
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns
            )
            
            # Should include blog posts and contact, exclude admin and external
            assert "https://example.com/blog/post1" in discovered_urls
            assert "https://example.com/blog/post2" in discovered_urls
            assert "https://example.com/contact" in discovered_urls
            assert "https://example.com/admin/panel" not in discovered_urls
            assert "https://external.com/page" not in discovered_urls
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, mock_asyncwebcrawler):
        """Test error handling and recovery mechanisms."""
        engine = CrawlEngine()
        engine.storage_manager = Mock()
        engine.storage_manager.get_cached_result = AsyncMock(return_value=None)
        engine.metrics = Mock()
        engine.metrics.increment_counter = Mock()
        
        # Test timeout error
        mock_asyncwebcrawler.arun.side_effect = asyncio.TimeoutError()
        
        with pytest.raises(TimeoutError):
            await engine.scrape_single("https://slow-site.com")
        
        # Test network error
        mock_asyncwebcrawler.arun.side_effect = Exception("Connection failed")
        
        with pytest.raises(NetworkError):
            await engine.scrape_single("https://down-site.com")
        
        # Verify error metrics were recorded (cache_misses + timeout + cache_misses + error)
        assert engine.metrics.increment_counter.call_count >= 4
        
        # Verify specific metric calls
        engine.metrics.increment_counter.assert_any_call("crawl_engine.scrapes.timeout")
        engine.metrics.increment_counter.assert_any_call("crawl_engine.scrapes.error")