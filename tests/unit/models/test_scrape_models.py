"""Tests for scraping data models."""

import pytest
from datetime import datetime
from pydantic import ValidationError, HttpUrl

from src.crawler.models.scrape import (
    ScrapeOptions, ScrapeRequest, ScrapeResult,
    ExtractionStrategy, OutputFormat, CSSExtractionConfig,
    LLMExtractionConfig, ExtractionStrategyConfig,
    LinkInfo, ImageInfo, ScrapingMetadata
)


class TestScrapeOptions:
    """Test suite for ScrapeOptions model."""
    
    def test_default_values(self):
        """Test ScrapeOptions with default values."""
        options = ScrapeOptions()
        
        assert options.headless is True
        assert options.timeout == 30
        assert options.user_agent is None
        assert options.viewport_width == 1920
        assert options.viewport_height == 1080
        assert options.cache_enabled is True
        assert options.screenshot is False
        assert options.pdf is False
    
    def test_custom_values(self):
        """Test ScrapeOptions with custom values."""
        options = ScrapeOptions(
            headless=False,
            timeout=60,
            user_agent="Custom Agent",
            viewport_width=1024,
            viewport_height=768,
            cache_enabled=False,
            screenshot=True
        )
        
        assert options.headless is False
        assert options.timeout == 60
        assert options.user_agent == "Custom Agent"
        assert options.viewport_width == 1024
        assert options.viewport_height == 768
        assert options.cache_enabled is False
        assert options.screenshot is True
    
    def test_timeout_validation(self):
        """Test timeout value validation."""
        # Valid timeout
        options = ScrapeOptions(timeout=10)
        assert options.timeout == 10
        
        # Invalid timeout (too low)
        with pytest.raises(ValidationError):
            ScrapeOptions(timeout=0)
        
        # Invalid timeout (too high)
        with pytest.raises(ValidationError):
            ScrapeOptions(timeout=500)
    
    def test_viewport_validation(self):
        """Test viewport size validation."""
        # Valid viewport
        options = ScrapeOptions(viewport_width=800, viewport_height=600)
        assert options.viewport_width == 800
        assert options.viewport_height == 600
        
        # Invalid viewport (too small)
        with pytest.raises(ValidationError):
            ScrapeOptions(viewport_width=50)
        
        with pytest.raises(ValidationError):
            ScrapeOptions(viewport_height=50)


class TestExtractionStrategyConfig:
    """Test suite for ExtractionStrategyConfig model."""
    
    def test_auto_strategy(self):
        """Test auto extraction strategy."""
        strategy = ExtractionStrategyConfig(type=ExtractionStrategy.AUTO)
        
        assert strategy.type == ExtractionStrategy.AUTO
        assert strategy.css is None
        assert strategy.llm is None
    
    def test_css_strategy_valid(self):
        """Test CSS extraction strategy with valid config."""
        css_config = CSSExtractionConfig(selectors=".content")
        strategy = ExtractionStrategyConfig(type=ExtractionStrategy.CSS, css=css_config)
        
        assert strategy.type == ExtractionStrategy.CSS
        assert strategy.css.selectors == ".content"
    
    def test_css_strategy_invalid(self):
        """Test CSS extraction strategy without config."""
        with pytest.raises(ValidationError):
            ExtractionStrategyConfig(type=ExtractionStrategy.CSS)
    
    def test_llm_strategy(self):
        """Test LLM extraction strategy."""
        llm_config = LLMExtractionConfig(model="openai/gpt-4")
        strategy = ExtractionStrategyConfig(type=ExtractionStrategy.LLM, llm=llm_config)
        
        assert strategy.type == ExtractionStrategy.LLM
        assert strategy.llm.model == "openai/gpt-4"


class TestLLMExtractionConfig:
    """Test suite for LLMExtractionConfig model."""
    
    def test_valid_model_format(self):
        """Test valid model format validation."""
        config = LLMExtractionConfig(model="openai/gpt-4")
        assert config.model == "openai/gpt-4"
        
        config = LLMExtractionConfig(model="anthropic/claude-3")
        assert config.model == "anthropic/claude-3"
    
    def test_invalid_model_format(self):
        """Test invalid model format validation."""
        with pytest.raises(ValidationError):
            LLMExtractionConfig(model="gpt-4")  # Missing provider
    
    def test_default_values(self):
        """Test default values for LLM config."""
        config = LLMExtractionConfig(model="openai/gpt-4")
        
        assert config.model == "openai/gpt-4"
        assert config.prompt is None
        assert config.temperature == 0.1
        assert config.max_tokens is None
    
    def test_temperature_validation(self):
        """Test temperature validation."""
        # Valid temperature
        config = LLMExtractionConfig(model="openai/gpt-4", temperature=0.5)
        assert config.temperature == 0.5
        
        # Invalid temperature (too low)
        with pytest.raises(ValidationError):
            LLMExtractionConfig(model="openai/gpt-4", temperature=-0.1)
        
        # Invalid temperature (too high)
        with pytest.raises(ValidationError):
            LLMExtractionConfig(model="openai/gpt-4", temperature=2.1)


class TestScrapeRequest:
    """Test suite for ScrapeRequest model."""
    
    def test_valid_request(self):
        """Test valid scrape request."""
        request = ScrapeRequest(url="https://example.com")
        
        assert str(request.url) == "https://example.com/"
        assert request.options is None
        assert request.extraction_strategy is None
        assert request.output_format == OutputFormat.MARKDOWN
        assert request.store_result is True
    
    def test_invalid_url(self):
        """Test invalid URL validation."""
        with pytest.raises(ValidationError):
            ScrapeRequest(url="not-a-url")
    
    def test_with_options(self):
        """Test scrape request with options."""
        options = ScrapeOptions(timeout=60, headless=False)
        request = ScrapeRequest(
            url="https://example.com",
            options=options,
            output_format=OutputFormat.JSON
        )
        
        assert request.options.timeout == 60
        assert request.options.headless is False
        assert request.output_format == OutputFormat.JSON
    
    def test_with_extraction_strategy(self):
        """Test scrape request with extraction strategy."""
        css_config = CSSExtractionConfig(selectors=".content")
        strategy = ExtractionStrategyConfig(type=ExtractionStrategy.CSS, css=css_config)
        
        request = ScrapeRequest(
            url="https://example.com",
            extraction_strategy=strategy
        )
        
        assert request.extraction_strategy.type == ExtractionStrategy.CSS
        assert request.extraction_strategy.css.selectors == ".content"


class TestScrapeResult:
    """Test suite for ScrapeResult model."""
    
    def test_successful_result(self):
        """Test successful scrape result."""
        result = ScrapeResult(
            success=True,
            url="https://example.com",
            title="Example Page",
            content="Page content",
            links=[
                LinkInfo(url="https://example.com/link1", text="Link 1"),
                LinkInfo(url="https://example.com/link2", text="Link 2")
            ],
            images=[
                ImageInfo(url="https://example.com/image1.jpg", alt="Image 1")
            ]
        )
        
        assert result.success is True
        assert str(result.url) == "https://example.com/"
        assert result.title == "Example Page"
        assert result.content == "Page content"
        assert len(result.links) == 2
        assert len(result.images) == 1
        assert result.error is None
    
    def test_failed_result(self):
        """Test failed scrape result."""
        result = ScrapeResult(
            success=False,
            url="https://example.com",
            error="Connection failed"
        )
        
        assert result.success is False
        assert str(result.url) == "https://example.com/"
        assert result.error == "Connection failed"
        assert result.title is None
        assert result.content is None
    
    def test_with_metadata(self):
        """Test scrape result with metadata."""
        metadata = ScrapingMetadata(
            url="https://example.com",
            status_code=200,
            load_time=1.5,
            size=1024,
            timestamp=datetime.utcnow(),
            output_format=OutputFormat.MARKDOWN
        )
        
        result = ScrapeResult(
            success=True,
            url="https://example.com",
            metadata=metadata
        )
        
        assert result.metadata.status_code == 200
        assert result.metadata.load_time == 1.5
        assert result.metadata.size == 1024


class TestLinkInfo:
    """Test suite for LinkInfo model."""
    
    def test_basic_link(self):
        """Test basic link information."""
        link = LinkInfo(url="https://example.com", text="Example")
        
        assert str(link.url) == "https://example.com/"
        assert link.text == "Example"
        assert link.title is None
        assert link.rel is None
    
    def test_full_link(self):
        """Test link with all information."""
        link = LinkInfo(
            url="https://example.com",
            text="Example Link",
            title="Example Website",
            rel="nofollow",
            type="text/html"
        )
        
        assert str(link.url) == "https://example.com/"
        assert link.text == "Example Link"
        assert link.title == "Example Website"
        assert link.rel == "nofollow"
        assert link.type == "text/html"
    
    def test_invalid_url(self):
        """Test link with invalid URL."""
        with pytest.raises(ValidationError):
            LinkInfo(url="not-a-url", text="Invalid")


class TestImageInfo:
    """Test suite for ImageInfo model."""
    
    def test_basic_image(self):
        """Test basic image information."""
        image = ImageInfo(url="https://example.com/image.jpg")
        
        assert str(image.url) == "https://example.com/image.jpg"
        assert image.alt is None
        assert image.title is None
        assert image.width is None
        assert image.height is None
    
    def test_full_image(self):
        """Test image with all information."""
        image = ImageInfo(
            url="https://example.com/image.jpg",
            alt="Example Image",
            title="An example image",
            width=800,
            height=600
        )
        
        assert str(image.url) == "https://example.com/image.jpg"
        assert image.alt == "Example Image"
        assert image.title == "An example image"
        assert image.width == 800
        assert image.height == 600


class TestScrapingMetadata:
    """Test suite for ScrapingMetadata model."""
    
    def test_basic_metadata(self):
        """Test basic scraping metadata."""
        metadata = ScrapingMetadata(
            url="https://example.com",
            status_code=200,
            load_time=1.5,
            size=1024,
            timestamp=datetime.utcnow(),
            output_format=OutputFormat.MARKDOWN
        )
        
        assert str(metadata.url) == "https://example.com/"
        assert metadata.status_code == 200
        assert metadata.load_time == 1.5
        assert metadata.size == 1024
        assert metadata.output_format == OutputFormat.MARKDOWN
    
    def test_metadata_with_headers(self):
        """Test metadata with response headers."""
        headers = {
            "content-type": "text/html",
            "server": "nginx",
            "content-length": "1024"
        }
        
        metadata = ScrapingMetadata(
            url="https://example.com",
            status_code=200,
            load_time=1.5,
            size=1024,
            timestamp=datetime.utcnow(),
            output_format=OutputFormat.MARKDOWN,
            response_headers=headers
        )
        
        assert metadata.response_headers == headers
        assert metadata.response_headers["content-type"] == "text/html"
    
    def test_load_time_validation(self):
        """Test load time validation."""
        # Valid load time
        metadata = ScrapingMetadata(
            url="https://example.com",
            status_code=200,
            load_time=0.5,
            size=1024,
            timestamp=datetime.utcnow(),
            output_format=OutputFormat.MARKDOWN
        )
        assert metadata.load_time == 0.5
        
        # Invalid load time (negative)
        with pytest.raises(ValidationError):
            ScrapingMetadata(
                url="https://example.com",
                status_code=200,
                load_time=-1.0,
                size=1024,
                timestamp=datetime.utcnow(),
                output_format=OutputFormat.MARKDOWN
            )
    
    def test_size_validation(self):
        """Test size validation."""
        # Valid size
        metadata = ScrapingMetadata(
            url="https://example.com",
            status_code=200,
            load_time=1.0,
            size=1024,
            timestamp=datetime.utcnow(),
            output_format=OutputFormat.MARKDOWN
        )
        assert metadata.size == 1024
        
        # Invalid size (negative)
        with pytest.raises(ValidationError):
            ScrapingMetadata(
                url="https://example.com",
                status_code=200,
                load_time=1.0,
                size=-1,
                timestamp=datetime.utcnow(),
                output_format=OutputFormat.MARKDOWN
            )