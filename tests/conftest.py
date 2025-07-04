"""Pytest configuration and shared fixtures."""

import asyncio
import tempfile
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from crawler.foundation.config import ConfigManager
from crawler.foundation.errors import ErrorHandler
from crawler.foundation.metrics import MetricsCollector
from crawler.core import StorageManager, JobManager
from crawler.services import ScrapeService, CrawlService, SessionService
from crawler.database.connection import DatabaseManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


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
    await db_manager.shutdown()


@pytest.fixture
async def storage_manager(database_manager, config_manager):
    """Create a test storage manager."""
    storage_manager = StorageManager()
    storage_manager.config_manager = config_manager
    storage_manager.db_manager = database_manager
    
    await storage_manager.initialize()
    
    yield storage_manager
    
    await storage_manager.shutdown()


@pytest.fixture
async def job_manager(storage_manager, config_manager):
    """Create a test job manager."""
    job_manager = JobManager()
    job_manager.config_manager = config_manager
    job_manager.storage_manager = storage_manager
    
    await job_manager.initialize()
    
    yield job_manager
    
    await job_manager.shutdown()


@pytest.fixture
def mock_crawl_engine():
    """Create a mock crawl engine."""
    engine = Mock()
    engine.initialize = AsyncMock()
    engine.shutdown = AsyncMock()
    engine.scrape_page = AsyncMock()
    engine.get_page_links = AsyncMock()
    engine.classify_links = AsyncMock()
    
    return engine


@pytest.fixture
async def scrape_service(config_manager, storage_manager, mock_crawl_engine):
    """Create a test scrape service."""
    service = ScrapeService()
    service.config_manager = config_manager
    service.storage_manager = storage_manager
    service.crawl_engine = mock_crawl_engine
    
    await service.initialize()
    
    yield service


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
        "content": "This is example content.",
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
    """Create a mock crawl4ai AsyncWebCrawler instance."""
    with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
        mock_crawler = Mock()
        mock_crawler.arun = AsyncMock()
        mock_crawler.close = AsyncMock()
        
        # Ensure the async context manager returns the same mock instance
        async def mock_aenter(self):
            return mock_crawler
        
        async def mock_aexit(self, exc_type, exc_val, exc_tb):
            return None
        
        mock_crawler.__aenter__ = mock_aenter
        mock_crawler.__aexit__ = mock_aexit
        
        mock_crawler_class.return_value = mock_crawler
        
        yield mock_crawler


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
    scrape._scrape_service = None
    crawl._crawl_service = None
    session._session_service = None
    config._config_manager = None
    metrics._metrics_collector = None


@pytest.fixture
def async_mock():
    """Create an AsyncMock for testing."""
    return AsyncMock()


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow