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
def unique_db_path(temp_dir):
    """Generate unique database path per test to prevent conflicts."""
    import uuid
    return temp_dir / f"test_{uuid.uuid4().hex[:8]}.db"


@pytest.fixture
def unique_test_id():
    """Generate unique test ID for resource isolation."""
    import uuid
    return uuid.uuid4().hex[:8]


@pytest.fixture
def cli_runner():
    """Create a Click CLI runner for testing."""
    from click.testing import CliRunner
    
    class TestingCliRunner(CliRunner):
        def invoke(self, cli, args=None, **kwargs):
            # Set up proper test environment
            kwargs.setdefault('catch_exceptions', False)  # Let exceptions propagate in tests
            if 'obj' not in kwargs:
                kwargs['obj'] = {}
            if kwargs['obj'] is None:
                kwargs['obj'] = {}
            
            return super().invoke(cli, args, **kwargs)
    
    return TestingCliRunner()


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
    import uuid
    unique_id = str(uuid.uuid4())[:8]
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
            "database_path": ":memory:",
            "session_timeout": 300,
        },
        "logging": {
            "level": "DEBUG",
            "file": str(temp_dir / f"test_{unique_id}.log"),
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
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    config_file = temp_dir / f"config_{unique_id}.yaml"
    
    # Create config manager with test configuration
    config_manager = ConfigManager(config_path=config_file)
    config_manager._config = test_config
    
    # Use in-memory database for all tests to avoid lock issues
    config_manager.set_setting("storage.database_path", ":memory:")
    
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
    """Create a test database manager with in-memory database."""
    # Create database manager with test config (in-memory database)
    db_manager = DatabaseManager(config_manager=config_manager)
    
    try:
        # Initialize with in-memory database
        await db_manager.initialize()
        yield db_manager
    finally:
        # Guaranteed cleanup
        try:
            if hasattr(db_manager, '_engine') and db_manager._engine:
                await db_manager._engine.dispose()
            await db_manager.shutdown()
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
async def storage_manager(database_manager, config_manager):
    """Create a test storage manager with in-memory database."""
    # Use in-memory database (no file path needed)
    storage_manager = StorageManager(db_path=":memory:")
    storage_manager.config_manager = config_manager
    storage_manager.db_manager = database_manager
    
    try:
        await storage_manager.initialize()
        yield storage_manager
    finally:
        # Guaranteed cleanup
        try:
            if hasattr(storage_manager, '_engine') and storage_manager._engine:
                await storage_manager._engine.dispose()
            await storage_manager.cleanup()
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
async def job_manager(storage_manager, config_manager):
    """Create a test job manager with in-memory database."""
    # Use in-memory database
    job_manager = JobManager(db_path=":memory:")
    job_manager.config_manager = config_manager
    job_manager.storage_manager = storage_manager
    
    try:
        await job_manager.initialize()
        yield job_manager
    finally:
        # Guaranteed cleanup
        try:
            # Cancel any running jobs
            if hasattr(job_manager, '_running_jobs'):
                for job_id, job_task in job_manager._running_jobs.items():
                    if not job_task.done():
                        job_task.cancel()
            await job_manager.stop()
            await job_manager.close()
        except Exception:
            pass  # Ignore cleanup errors


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
        
        # Mock job manager
        from unittest.mock import Mock, AsyncMock
        mock_job_manager = Mock()
        mock_job_manager.initialize = AsyncMock()
        mock_job_manager.register_handler = AsyncMock()
        mock_job_manager.submit_job = AsyncMock()
        service.job_manager = mock_job_manager
        
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
    """Create a test session service with guaranteed cleanup."""
    service = SessionService()
    service.config_manager = config_manager
    service.storage_manager = storage_manager
    
    try:
        await service.initialize()
        yield service
    finally:
        # Guaranteed cleanup
        try:
            await service.shutdown()
        except Exception:
            pass  # Ignore cleanup errors


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
def mock_scrape_service():
    """Create a mock scrape service for testing."""
    service = Mock()
    service.initialize = AsyncMock()
    service.shutdown = AsyncMock()
    service.scrape_single = AsyncMock()
    service.scrape_single_async = AsyncMock()
    service.scrape_batch = AsyncMock()
    return service


@pytest.fixture
def mock_crawl4ai():
    """Mock crawl4ai for testing."""
    with patch('crawl4ai.AsyncWebCrawler') as mock_crawler_class:
        mock_crawler = AsyncMock()
        mock_crawler_class.return_value = mock_crawler
        
        # Default mock result
        mock_result = Mock()
        mock_result.success = True
        mock_result.html = "<html><body>Mock content</body></html>"
        mock_result.markdown = "Mock content"
        mock_result.cleaned_html = "<body>Mock content</body>"
        mock_result.extracted_content = "Mock content"
        mock_result.status_code = 200
        mock_result.response_headers = {}
        mock_result.links = []
        mock_result.media = []
        mock_result.metadata = {}
        mock_result.error_message = None
        mock_crawler.arun.return_value = mock_result
        
        yield mock_crawler


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
def mock_crawl4ai(mock_scrape_service):
    """Create a mock crawl engine for tests."""
    # Mock the scrape service to prevent real database/network calls
    with patch('src.crawler.services.get_scrape_service', return_value=mock_scrape_service):
        # Mock the crawl4ai library instead of the engine methods
        with patch('src.crawler.core.engine.AsyncWebCrawler') as mock_crawler_class:
            # Store the current user_agent from the crawler constructor
            current_user_agent = "Crawler/1.0"  # Default
            
            def mock_constructor(**kwargs):
                nonlocal current_user_agent
                # Capture user_agent from the constructor arguments
                if "user_agent" in kwargs:
                    current_user_agent = kwargs.get("user_agent", "Crawler/1.0")
                elif "config" in kwargs and getattr(kwargs["config"], "user_agent", None):
                    current_user_agent = getattr(kwargs["config"], "user_agent")
                else:
                    current_user_agent = "Crawler/1.0"
            
                mock_crawler = AsyncMock()
                
                def create_mock_result(url, arun_kwargs=None):
                    if arun_kwargs is None:
                        arun_kwargs = {}

                    run_config = arun_kwargs.get("config")
                    page_timeout = arun_kwargs.get("page_timeout")
                    if page_timeout is None and run_config is not None:
                        page_timeout = getattr(run_config, "page_timeout", None)
                    if page_timeout is None:
                        page_timeout = 30000
                    
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
                    elif "delay" in url and page_timeout < 5000:
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
    """Reset singleton instances before and after each test."""
    # Reset BEFORE the test runs to ensure clean state
    from src.crawler.core import storage, jobs, engine
    from src.crawler.services import scrape, crawl, session
    from src.crawler.foundation import config, metrics
    from src.crawler.database import connection
    
    # Stop any existing session service cleanup loop
    if hasattr(session, '_session_service') and session._session_service is not None:
        session_service = session._session_service
        session_service._should_cleanup = False
        # Cancel cleanup task if it exists and event loop is running
        if hasattr(session_service, '_cleanup_task') and session_service._cleanup_task is not None:
            try:
                session_service._cleanup_task.cancel()
            except RuntimeError:
                pass  # Event loop is closed
    
    # Clear singleton instances BEFORE test
    storage._storage_manager = None
    jobs._job_manager = None
    engine._crawl_engine = None
    config._config_manager = None
    scrape._scrape_service = None
    crawl._crawl_service = None
    session._session_service = None
    metrics._metrics_collector = None
    connection._db_manager = None  # Reset database manager singleton
    
    yield  # Let the test run
    
    # Additional cleanup AFTER the test
    if hasattr(session, '_session_service') and session._session_service is not None:
        session_service = session._session_service
        session_service._should_cleanup = False
        # Cancel cleanup task if it exists and event loop is running
        if hasattr(session_service, '_cleanup_task') and session_service._cleanup_task is not None:
            try:
                session_service._cleanup_task.cancel()
            except RuntimeError:
                pass  # Event loop is closed
    
    # Clear singleton instances AFTER test
    storage._storage_manager = None
    jobs._job_manager = None
    engine._crawl_engine = None
    config._config_manager = None
    scrape._scrape_service = None
    crawl._crawl_service = None
    session._session_service = None
    metrics._metrics_collector = None
    connection._db_manager = None  # Reset database manager singleton


@pytest.fixture
def async_mock():
    """Create an AsyncMock for testing."""
    return AsyncMock()


@pytest.fixture
def mock_scrape_service():
    """Create a mock scrape service that returns successful results."""
    from unittest.mock import AsyncMock, Mock
    service = Mock()
    service.initialize = AsyncMock()
    service.scrape_single = AsyncMock()
    service.scrape_single_async = AsyncMock()
    
    # Configure default return values
    service.scrape_single.return_value = {
        "success": True,
        "url": "https://example.com",
        "title": "Example Domain",
        "content": "This domain is for use in illustrative examples in documents.",
        "metadata": {
            "status_code": 200,
            "load_time": 0.5,
            "size": 1024,
            "timestamp": "2025-01-01T00:00:00Z"
        }
    }
    
    service.scrape_single_async.return_value = "test-job-id"
    
    return service


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
        
        # Allow the mock to be customized for specific tests
        mock_crawler.configure_mock = lambda **kwargs: mock_result.configure_mock(**kwargs)
        
        yield mock_crawler


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
