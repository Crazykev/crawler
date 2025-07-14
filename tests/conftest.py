"""Pytest configuration and shared fixtures."""

import asyncio
import tempfile
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from src.crawler.foundation.config import ConfigManager
from src.crawler.foundation.errors import ErrorHandler
from src.crawler.foundation.metrics import MetricsCollector
from src.crawler.core import StorageManager, JobManager
from src.crawler.services import ScrapeService, CrawlService, SessionService
from src.crawler.database.connection import DatabaseManager



@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner for testing."""
    from click.testing import CliRunner
    return CliRunner()


@pytest.fixture
def temp_config_file(temp_dir):
    """Create a temporary config file for testing."""
    config_file = temp_dir / "test_config.yaml"
    config_content = """
version: "1.0"
scrape:
  timeout: 30
  headless: true
crawl:
  max_depth: 3
  max_pages: 100
storage:
  database_path: "test.db"
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration."""
    config_data = {
        "scrape": {
            "timeout": 10,
            "headless": True,
            "user_agent": "Test-Agent/1.0",
            "cache_enabled": False,
        },
        "crawl": {
            "max_depth": 2,
            "max_pages": 10,
            "delay": 0.1,
            "concurrent_requests": 2,
        },
        "storage": {
            "database_url": f"sqlite:///{temp_dir}/test.db",
            "session_timeout": 300,
        },
        "logging": {
            "level": "DEBUG",
            "file": str(temp_dir / "test.log"),
        },
        "metrics": {
            "enabled": False,
        },
        "jobs": {
            "max_concurrent": 2,
            "retry_attempts": 1,
        }
    }
    return config_data


@pytest.fixture
def config_manager(test_config, temp_dir):
    """Create a test configuration manager."""
    config_file = temp_dir / "config.yaml"
    
    # Create config manager with test configuration
    config_manager = ConfigManager(config_path=config_file)
    config_manager._config = test_config
    
    return config_manager


@pytest.fixture
def error_handler():
    """Create an error handler for testing."""
    return ErrorHandler()


@pytest.fixture
def metrics_collector(config_manager):
    """Create a metrics collector for testing."""
    collector = MetricsCollector()
    collector.config_manager = config_manager
    return collector


@pytest.fixture
async def database_manager(config_manager):
    """Create a test database manager."""
    db_manager = DatabaseManager()
    db_manager.config_manager = config_manager
    
    # Initialize with test database
    await db_manager.initialize()
    
    yield db_manager
    
    # Cleanup
    await db_manager.close()


@pytest.fixture
async def storage_manager(database_manager, config_manager):
    """Create a test storage manager."""
    storage_manager = StorageManager()
    storage_manager.config_manager = config_manager
    storage_manager.db_manager = database_manager
    
    await storage_manager.initialize()
    
    yield storage_manager
    
    await storage_manager.cleanup()


@pytest.fixture
async def job_manager(storage_manager, config_manager):
    """Create a test job manager."""
    job_manager = JobManager()
    job_manager.config_manager = config_manager
    job_manager.storage_manager = storage_manager
    
    await job_manager.initialize()
    
    yield job_manager
    
    await job_manager.stop()


@pytest.fixture
def mock_crawl_engine():
    """Create a mock crawl engine."""
    engine = Mock()
    engine.initialize = AsyncMock()
    engine.shutdown = AsyncMock()
    engine.scrape_page = AsyncMock()
    engine.scrape_single = AsyncMock()
    engine.scrape_batch = AsyncMock()
    engine.get_page_links = AsyncMock()
    engine.classify_links = AsyncMock()
    
    return engine


@pytest.fixture
def scrape_service_factory(config_manager, mock_crawl_engine):
    """Create a factory for scrape service instances."""
    def _create_service(storage_manager=None):
        service = ScrapeService()
        service.config_manager = config_manager
        service.storage_manager = storage_manager
        service.crawl_engine = mock_crawl_engine
        return service
    return _create_service


@pytest.fixture
def mock_storage_manager():
    """Create a mock storage manager for testing."""
    storage = Mock()
    storage.initialize = AsyncMock()
    storage.shutdown = AsyncMock()
    storage.store_crawl_result = AsyncMock()
    storage.store_scrape_result = AsyncMock()
    storage.get_cached_result = AsyncMock(return_value=None)  # No cache by default
    storage.store_cached_result = AsyncMock()
    return storage


@pytest.fixture
def scrape_service(config_manager, mock_crawl_engine, mock_storage_manager):
    """Create a ready-to-use scrape service instance for testing."""
    service = ScrapeService()
    service.config_manager = config_manager
    service.storage_manager = mock_storage_manager
    service.crawl_engine = mock_crawl_engine
    return service


@pytest.fixture
async def session_service(config_manager, storage_manager):
    """Create a test session service."""
    service = SessionService()
    service.config_manager = config_manager
    service.storage_manager = storage_manager
    
    await service.initialize()
    
    yield service
    
    await service.shutdown()


@pytest.fixture
def sample_urls():
    """Sample URLs for testing."""
    return [
        "https://example.com",
        "https://test.com/page1",
        "https://test.com/page2",
        "https://subdomain.test.com",
    ]


@pytest.fixture
def sample_scrape_result():
    """Sample scrape result for testing."""
    return {
        "success": True,
        "url": "https://example.com",
        "title": "Example Page",
        "content": {
            "markdown": "This is example content.",
            "html": "<p>This is example content.</p>",
            "text": "This is example content."
        },
        "links": [
            {"url": "https://example.com/page1", "text": "Page 1"},
            {"url": "https://example.com/page2", "text": "Page 2"},
        ],
        "images": [
            {"url": "https://example.com/image1.jpg", "alt": "Image 1"},
        ],
        "metadata": {
            "status_code": 200,
            "load_time": 1.5,
            "size": 1024,
            "timestamp": "2025-01-01T00:00:00Z",
        }
    }


@pytest.fixture
def sample_crawl_rules():
    """Sample crawl rules for testing."""
    from crawler.services.crawl import CrawlRule
    
    return CrawlRule(
        max_depth=2,
        max_pages=10,
        max_duration=300,
        delay=0.1,
        concurrent_requests=2,
        respect_robots=False,
        allow_external_links=False,
        allow_subdomains=True,
    )


@pytest.fixture
def sample_session_config():
    """Sample session configuration for testing."""
    from crawler.services.session import SessionConfig
    
    return SessionConfig(
        browser_type="chromium",
        headless=True,
        timeout=10,
        user_agent="Test-Agent/1.0",
        viewport_width=1024,
        viewport_height=768,
    )


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""
    response = Mock()
    response.status_code = 200
    response.headers = {"content-type": "text/html"}
    response.text = "<html><head><title>Test</title></head><body>Test content</body></html>"
    response.url = "https://example.com"
    
    return response


@pytest.fixture
def mock_async_response():
    """Create a mock async HTTP response."""
    response = Mock()
    response.status = 200
    response.headers = {"content-type": "text/html"}
    response.text = AsyncMock(return_value="<html><head><title>Test</title></head><body>Test content</body></html>")
    response.url = "https://example.com"
    
    return response


@pytest.fixture
def mock_crawl4ai():
    """Create a mock crawl engine for tests."""
    # Mock the crawl4ai library instead of the engine methods
    with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
        # Store the current user_agent from the crawler constructor
        current_user_agent = "Crawler/1.0"  # Default
        
        def mock_constructor(**kwargs):
            nonlocal current_user_agent
            # Capture user_agent from the constructor arguments
            current_user_agent = kwargs.get("user_agent", "Crawler/1.0")
            
            mock_crawler = AsyncMock()
            
            def create_mock_result(url, arun_kwargs=None):
                if arun_kwargs is None:
                    arun_kwargs = {}
                
                mock_result = Mock()
                mock_result.links = []
                mock_result.media = []
                
                # Configure mock result based on URL and options
                if "nonexistent-domain" in url or "invalid" in url:
                    mock_result.success = False
                    mock_result.status_code = None
                    mock_result.error_message = "Domain not found"
                    mock_result.markdown = ""
                    mock_result.html = ""
                    mock_result.cleaned_html = ""
                    mock_result.metadata = {}
                    mock_result.extracted_content = None
                elif "delay" in url and arun_kwargs.get("page_timeout", 30000) < 5000:
                    mock_result.success = False
                    mock_result.status_code = None
                    mock_result.error_message = "Request timeout"
                    mock_result.markdown = ""
                    mock_result.html = ""
                    mock_result.cleaned_html = ""
                    mock_result.metadata = {}
                    mock_result.extracted_content = None
                elif "user-agent" in url:
                    # Use the user_agent from the constructor
                    user_agent = current_user_agent
                    mock_result.success = True
                    mock_result.status_code = 200
                    mock_result.markdown = f"# User Agent Test\n\nYour user agent is: {user_agent}"
                    mock_result.html = f"<html><head><title>User Agent Test</title></head><body><h1>User Agent Test</h1><p>Your user agent is: {user_agent}</p></body></html>"
                    mock_result.cleaned_html = f"User Agent Test\n\nYour user agent is: {user_agent}"
                    mock_result.metadata = {"title": "User Agent Test"}
                    mock_result.extracted_content = None
                else:
                    # Default successful result
                    mock_result.success = True
                    mock_result.status_code = 200
                    mock_result.markdown = "# Example Domain\n\nThis domain is for examples."
                    mock_result.html = "<html><head><title>Example</title></head><body><h1>Example Domain</h1></body></html>"
                    mock_result.cleaned_html = "Example Domain\n\nThis domain is for examples."
                    mock_result.metadata = {"title": "Example Domain"}
                    mock_result.extracted_content = None
                
                return mock_result
            
            def mock_arun(**arun_kwargs):
                # Extract URL from kwargs
                url = arun_kwargs.get('url', '')
                return create_mock_result(url, arun_kwargs)
            
            mock_crawler.arun.side_effect = mock_arun
            return mock_crawler
        
        mock_crawler_class.side_effect = mock_constructor
        
        yield mock_crawler_class


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Reset any singleton instances
    from crawler.core import storage, jobs, engine
    from crawler.services import scrape, crawl, session
    from crawler.foundation import config, metrics
    
    # Clear singleton instances
    storage._storage_manager = None
    jobs._job_manager = None
    engine._crawl_engine = None
    
    # Reset config manager singleton to avoid cross-test pollution
    config._config_manager = None
    scrape._scrape_service = None
    crawl._crawl_service = None
    session._session_service = None
    config._config_manager = None
    metrics._metrics_collector = None


@pytest.fixture
def async_mock():
    """Create an AsyncMock for testing."""
    return AsyncMock()


@pytest.fixture
def mock_asyncwebcrawler():
    """Create a mock AsyncWebCrawler for core engine tests."""
    with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
        # Create a mock instance that will be returned by the constructor
        mock_crawler = AsyncMock()
        mock_crawler_class.return_value = mock_crawler
        
        # Mock the arun method to return a proper result
        mock_result = Mock()
        mock_result.success = True
        mock_result.status_code = 200
        mock_result.markdown = "# Test Page\n\nContent"
        mock_result.html = "<html><head><title>Test</title></head><body><h1>Test Page</h1><p>Content</p></body></html>"
        mock_result.cleaned_html = "Test Page\n\nContent"
        mock_result.metadata = {"title": "Test Page"}
        mock_result.links = []
        mock_result.media = []
        mock_crawler.arun = AsyncMock(return_value=mock_result)
        
        yield mock_crawler


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow