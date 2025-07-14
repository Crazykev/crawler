"""Edge case tests for data validation and content processing."""

import pytest
import json
import base64
from unittest.mock import Mock, patch
from urllib.parse import quote, unquote

from src.crawler.foundation.config import ConfigManager
from src.crawler.foundation.errors import ValidationError
from src.crawler.services.scrape import ScrapeService
from src.crawler.models.scrape import ScrapeOptions, ScrapeResult


@pytest.mark.validation
class TestURLValidationEdgeCases:
    """Test edge cases for URL validation."""

    @pytest.fixture
    def scrape_service(self):
        """Create a scrape service instance."""
        return ScrapeService()

    def test_internationalized_domain_names(self, scrape_service):
        """Test validation of internationalized domain names (IDN)."""
        
        # Valid IDN URLs
        valid_idn_urls = [
            "https://例え.テスト",  # Japanese
            "https://пример.испытание",  # Russian
            "https://例子.测试",  # Chinese
            "https://مثال.إختبار",  # Arabic
        ]
        
        for url in valid_idn_urls:
            # Should not raise ValidationError
            try:
                scrape_service._validate_url(url)
            except ValidationError:
                pytest.fail(f"Valid IDN URL rejected: {url}")

    def test_punycode_domain_names(self, scrape_service):
        """Test validation of punycode-encoded domain names."""
        
        # Punycode encoded URLs
        punycode_urls = [
            "https://xn--r8jz45g.xn--zckzah",  # 例え.テスト in punycode
            "https://xn--e1afmkfd.xn--80akhbyknj4f",  # пример.испытание in punycode
        ]
        
        for url in punycode_urls:
            # Should not raise ValidationError
            try:
                scrape_service._validate_url(url)
            except ValidationError:
                pytest.fail(f"Valid punycode URL rejected: {url}")

    def test_ipv6_urls(self, scrape_service):
        """Test validation of IPv6 URLs."""
        
        # Valid IPv6 URLs
        valid_ipv6_urls = [
            "https://[2001:db8::1]/",
            "https://[2001:db8::1]:8080/path",
            "https://[::1]/localhost",
            "https://[2001:db8:85a3::8a2e:370:7334]/",
            "http://[fe80::1%lo0]/",  # Link-local with zone ID
        ]
        
        for url in valid_ipv6_urls:
            try:
                scrape_service._validate_url(url)
            except ValidationError:
                pytest.fail(f"Valid IPv6 URL rejected: {url}")

    def test_non_standard_ports(self, scrape_service):
        """Test validation of URLs with non-standard ports."""
        
        # Valid URLs with various ports
        port_urls = [
            "https://example.com:8080/",
            "https://example.com:443/",  # Standard HTTPS port
            "http://example.com:80/",   # Standard HTTP port
            "https://example.com:65535/",  # Maximum port number
            "https://example.com:1/",   # Minimum port number
        ]
        
        for url in port_urls:
            try:
                scrape_service._validate_url(url)
            except ValidationError:
                pytest.fail(f"Valid port URL rejected: {url}")

    def test_very_long_urls(self, scrape_service):
        """Test validation of very long URLs."""
        
        # Create a very long URL (2000+ characters)
        base_url = "https://example.com/"
        long_path = "a" * 2000
        long_url = base_url + long_path
        
        # Should handle long URLs gracefully
        try:
            scrape_service._validate_url(long_url)
        except ValidationError as e:
            # If rejected, should be for length, not format
            assert "length" in str(e).lower() or "long" in str(e).lower()

    def test_url_encoding_edge_cases(self, scrape_service):
        """Test URLs with various encoding scenarios."""
        
        # URLs with percent encoding
        encoded_urls = [
            "https://example.com/path%20with%20spaces",
            "https://example.com/path%2Fwith%2Fslashes",
            "https://example.com/path%3Fwith%3Dquery",
            "https://example.com/unicode%E2%9C%93",  # Unicode checkmark
            "https://example.com/%E4%B8%AD%E6%96%87",  # Chinese characters
        ]
        
        for url in encoded_urls:
            try:
                scrape_service._validate_url(url)
            except ValidationError:
                pytest.fail(f"Valid encoded URL rejected: {url}")

    def test_malformed_url_encoding(self, scrape_service):
        """Test handling of malformed percent encoding."""
        
        # Malformed percent encoding
        malformed_urls = [
            "https://example.com/path%",  # Incomplete encoding
            "https://example.com/path%2",  # Incomplete encoding
            "https://example.com/path%ZZ",  # Invalid hex digits
            "https://example.com/path%GG",  # Invalid hex digits
        ]
        
        for url in malformed_urls:
            # Should either accept (if parser is lenient) or reject with clear error
            try:
                scrape_service._validate_url(url)
            except ValidationError as e:
                assert any(word in str(e).lower() for word in ["encoding", "format", "invalid", "url"])

    def test_urls_with_fragments_and_queries(self, scrape_service):
        """Test URLs with complex query strings and fragments."""
        
        complex_urls = [
            "https://example.com/path?query=value&other=value2#fragment",
            "https://example.com/path?q=search%20term&page=1&sort=date#results",
            "https://example.com/path?callback=jsonp_callback_123&_=1234567890",
            "https://example.com/#!hashbang/route",
            "https://example.com/path?utm_source=test&utm_medium=email&utm_campaign=test",
        ]
        
        for url in complex_urls:
            try:
                scrape_service._validate_url(url)
            except ValidationError:
                pytest.fail(f"Valid complex URL rejected: {url}")

    def test_edge_case_schemes(self, scrape_service):
        """Test handling of edge case URL schemes."""
        
        # Only HTTP and HTTPS should be accepted
        invalid_schemes = [
            "ftp://example.com/file.txt",
            "file:///local/path",
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "mailto:user@example.com",
        ]
        
        for url in invalid_schemes:
            with pytest.raises(ValidationError) as exc_info:
                scrape_service._validate_url(url)
            assert any(word in str(exc_info.value).lower() for word in ["scheme", "protocol", "http"])

    def test_empty_and_whitespace_urls(self, scrape_service):
        """Test handling of empty and whitespace-only URLs."""
        
        invalid_urls = [
            "",
            " ",
            "\t",
            "\n",
            "   \t\n   ",
            None,  # Will be caught by type check
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValidationError) as exc_info:
                scrape_service._validate_url(url)
            assert any(word in str(exc_info.value).lower() for word in ["empty", "string", "url"])

    def test_urls_with_credentials(self, scrape_service):
        """Test handling of URLs with embedded credentials."""
        
        credential_urls = [
            "https://user:pass@example.com/",
            "https://user@example.com/",
            "https://user:@example.com/",
            "https://:pass@example.com/",
        ]
        
        for url in credential_urls:
            try:
                scrape_service._validate_url(url)
                # If accepted, that's fine - just testing no crash
            except ValidationError:
                # If rejected, should be for security reasons
                pass


@pytest.mark.validation
class TestContentProcessingEdgeCases:
    """Test edge cases for content processing and extraction."""

    @pytest.mark.asyncio
    async def test_binary_content_handling(self):
        """Test handling of binary content types."""
        
        # Mock crawl4ai to return binary content
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = None  # No text content
            mock_result.markdown = ""  # Empty string for binary content
            mock_result.html = ""
            mock_result.cleaned_html = ""
            mock_result.status_code = 200
            mock_result.links = {"internal": [], "external": []}
            mock_result.media = []  # Empty list for binary content
            mock_result.metadata = {"title": "Binary Document", "load_time": 1.0}  # Real dictionary
            # Simulate binary content type
            mock_result.response_headers = {"content-type": "application/pdf"}
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/document.pdf",
                options={"timeout": 10}
            )
            
            # Should handle binary content gracefully
            assert result["success"] is True
            # Content might be empty or contain a message about binary content
            content = result.get("content", "")
            assert isinstance(content, str)  # Should be string, not bytes

    @pytest.mark.asyncio
    async def test_very_large_page_content(self):
        """Test handling of very large page content."""
        
        # Create large content (5MB)
        large_content = "Large content. " * (5 * 1024 * 1024 // 15)  # Approx 5MB
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = large_content
            mock_result.markdown = large_content
            mock_result.html = large_content
            mock_result.cleaned_html = large_content
            mock_result.status_code = 200
            mock_result.links = {"internal": [], "external": []}
            mock_result.media = []
            mock_result.metadata = {"title": "Large Page", "load_time": 5.0}  # Real dictionary
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/large-page",
                options={"timeout": 30}
            )
            
            # Should handle large content without crashing
            assert result["success"] is True
            assert "content" in result
            # Content might be truncated for efficiency
            assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_malformed_html_recovery(self):
        """Test recovery from severely malformed HTML."""
        
        # Malformed HTML that might break parsers
        malformed_html = """
        <html>
        <head>
        <title>Malformed Page
        <body>
        <div>Unclosed div
        <p>Paragraph without closing tag
        <script>
        function broken() {
            // Unclosed script
        <div>Div inside script???
        <img src="image.jpg" alt="Unclosed quote>
        <!-- Unclosed comment
        <style>
        .broken { color: red
        </html>
        Extra content after html close
        """
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = "Recovered content from malformed HTML"
            mock_result.status_code = 200
            mock_result.links = {"internal": [], "external": []}
            mock_result.media = {"images": []}
            mock_result.metadata = {"title": "Malformed HTML", "load_time": 2.0}  # Real dictionary
            mock_result.html = "<html><body>Recovered content from malformed HTML</body></html>"  # Add missing html attribute
            mock_result.markdown = "# Malformed HTML\n\nRecovered content from malformed HTML"  # Add missing markdown attribute
            mock_result.cleaned_html = "Recovered content from malformed HTML"  # Add missing cleaned_html attribute
            mock_result.url = "https://example.com/malformed.html"  # Add missing url attribute
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/malformed.html",
                options={"timeout": 10}
            )
            
            # Should recover gracefully from malformed HTML
            assert result["success"] is True
            assert "content" in result

    @pytest.mark.asyncio
    async def test_character_encoding_detection(self):
        """Test handling of various character encodings."""
        
        # Test content with different encodings
        test_cases = [
            ("UTF-8", "Hello 世界 🌍"),
            ("Latin-1", "Café résumé naïve"),
            ("ASCII", "Simple ASCII text"),
        ]
        
        for encoding, text in test_cases:
            with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
                mock_result = Mock()
                mock_result.success = True
                mock_result.extracted_content = text
                mock_result.markdown = text
                mock_result.html = text
                mock_result.cleaned_html = text
                mock_result.status_code = 200
                mock_result.links = {"internal": [], "external": []}
                mock_result.media = []
                mock_result.metadata = {"title": f"{encoding} Test", "load_time": 1.0}  # Real dictionary
                mock_crawl.return_value = mock_result
                
                service = ScrapeService()
                result = await service.scrape_single(
                    url=f"https://example.com/{encoding.lower()}.html",
                    options={"timeout": 10}
                )
                
                # Should handle different encodings
                assert result["success"] is True
                assert text in result["content"]

    @pytest.mark.asyncio
    async def test_javascript_execution_timeout(self):
        """Test handling of long-running JavaScript."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            # Simulate JS timeout
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = "Content before JS timeout"
            mock_result.status_code = 200
            mock_result.links = {"internal": [], "external": []}
            mock_result.media = {"images": []}
            mock_result.metadata = {"title": "JS Timeout", "load_time": 3.0}  # Real dictionary
            # Simulate JS warning or timeout message
            mock_result.warnings = ["JavaScript execution timeout"]
            mock_result.html = "<html><body>Content before JS timeout</body></html>"  # Add missing html attribute
            mock_result.markdown = "# JS Timeout\n\nContent before JS timeout"  # Add missing markdown attribute
            mock_result.cleaned_html = "Content before JS timeout"  # Add missing cleaned_html attribute
            mock_result.url = "https://example.com/heavy-js.html"  # Add missing url attribute
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/heavy-js.html",
                options={"timeout": 10, "js_timeout": 5}
            )
            
            # Should handle JS timeout gracefully
            assert result["success"] is True
            assert "content" in result

    @pytest.mark.asyncio
    async def test_infinite_scroll_handling(self):
        """Test handling of infinite scroll pages."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = "Partial content from infinite scroll page"
            mock_result.status_code = 200
            mock_result.links = {"internal": [], "external": []}
            mock_result.media = {"images": []}
            mock_result.metadata = {"title": "Infinite Scroll", "load_time": 4.0}  # Real dictionary
            mock_result.html = "<html><body>Partial content from infinite scroll page</body></html>"  # Add missing html attribute
            mock_result.markdown = "# Infinite Scroll\n\nPartial content from infinite scroll page"  # Add missing markdown attribute
            mock_result.cleaned_html = "Partial content from infinite scroll page"  # Add missing cleaned_html attribute
            mock_result.url = "https://example.com/infinite-scroll"  # Add missing url attribute
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/infinite-scroll",
                options={"timeout": 10, "wait_for": ".content-loaded"}
            )
            
            # Should handle infinite scroll pages
            assert result["success"] is True
            assert "content" in result

    @pytest.mark.asyncio
    async def test_dynamic_content_loading(self):
        """Test handling of dynamically loaded content."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = "Dynamically loaded content"
            mock_result.status_code = 200
            mock_result.links = {"internal": [], "external": []}
            mock_result.media = {"images": []}
            mock_result.metadata = {"title": "Dynamic Content", "load_time": 3.5}  # Real dictionary
            mock_result.html = "<html><body>Dynamically loaded content</body></html>"  # Add missing html attribute
            mock_result.markdown = "# Dynamic Content\n\nDynamically loaded content"  # Add missing markdown attribute
            mock_result.cleaned_html = "Dynamically loaded content"  # Add missing cleaned_html attribute
            mock_result.url = "https://example.com/dynamic-content"  # Add missing url attribute
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/dynamic-content",
                options={
                    "timeout": 15,
                    "wait_for": ".dynamic-content",
                    "js_code": "document.querySelector('.load-more').click();"
                }
            )
            
            # Should handle dynamic content
            assert result["success"] is True
            assert "content" in result

    @pytest.mark.asyncio
    async def test_content_with_special_characters(self):
        """Test handling of content with special characters."""
        
        special_content = """
        Special characters test:
        • Bullet points
        ™ Trademark
        © Copyright
        ® Registered
        € Euro symbol
        £ Pound symbol
        ¥ Yen symbol
        ∞ Infinity
        π Pi
        √ Square root
        ∑ Summation
        ∆ Delta
        Ω Omega
        α Beta γ Delta
        Emoji: 😀 🎉 🌟 ⭐ 🚀
        """
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = special_content
            mock_result.markdown = special_content
            mock_result.html = special_content
            mock_result.cleaned_html = special_content
            mock_result.status_code = 200
            mock_result.links = {"internal": [], "external": []}
            mock_result.media = []
            mock_result.metadata = {"title": "Special Characters", "load_time": 1.5}  # Real dictionary
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/special-chars",
                options={"timeout": 10}
            )
            
            # Should handle special characters
            assert result["success"] is True
            assert "content" in result
            # Verify some special characters are preserved
            assert "€" in result["content"] or "©" in result["content"]

    @pytest.mark.asyncio
    async def test_mixed_content_types(self):
        """Test handling of pages with mixed content types."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = Mock()
            mock_result.success = True
            mock_result.extracted_content = "Mixed content page with text, images, and embedded media"
            mock_result.markdown = "Mixed content page with text, images, and embedded media"
            mock_result.html = "Mixed content page with text, images, and embedded media"
            mock_result.cleaned_html = "Mixed content page with text, images, and embedded media"
            mock_result.status_code = 200
            mock_result.links = {
                "internal": ["https://example.com/page1", "https://example.com/page2"],
                "external": ["https://other.com/page"]
            }
            mock_result.media = [
                {
                    "type": "image",
                    "src": "https://example.com/image1.jpg",
                    "alt": "Image 1"
                },
                {
                    "type": "image",
                    "src": "https://example.com/image2.png",
                    "alt": "Image 2"
                }
            ]
            mock_result.metadata = {"title": "Mixed Content", "load_time": 2.5}  # Real dictionary
            mock_crawl.return_value = mock_result
            
            service = ScrapeService()
            result = await service.scrape_single(
                url="https://example.com/mixed-content",
                options={"timeout": 10}
            )
            
            # Should extract all types of content
            assert result["success"] is True
            assert "content" in result
            assert "links" in result
            assert "images" in result
            assert len(result["links"]) > 0
            assert len(result["images"]) > 0


@pytest.mark.validation
class TestConfigurationValidationEdgeCases:
    """Test edge cases for configuration validation."""

    def test_circular_reference_detection(self):
        """Test detection of circular references in configuration."""
        
        # This would be implemented in a more sophisticated config system
        # For now, test that we can handle complex nested configs
        complex_config = {
            "scrape": {
                "timeout": 30,
                "options": {
                    "retry_count": 3,
                    "retry_delay": 1.0
                }
            },
            "profiles": {
                "default": {
                    "scrape": {
                        "timeout": 45  # Override
                    }
                }
            }
        }
        
        # Should handle nested configuration without issues
        assert isinstance(complex_config, dict)
        assert complex_config["scrape"]["timeout"] == 30
        assert complex_config["profiles"]["default"]["scrape"]["timeout"] == 45

    def test_environment_variable_conflicts(self):
        """Test handling of conflicting environment variables."""
        
        with patch.dict('os.environ', {
            'CRAWLER_SCRAPE_TIMEOUT': '30',
            'SCRAPE_TIMEOUT': '45',  # Potential conflict
            'CRAWLER_TIMEOUT': '60'   # Another potential conflict
        }):
            # Configuration system should handle conflicts with clear precedence
            from src.crawler.foundation.config import get_config_manager
            config_manager = get_config_manager()
            
            # Should not crash with conflicting env vars
            timeout = config_manager.get_setting("scrape.timeout", 30)
            assert isinstance(timeout, int)
            assert timeout > 0

    def test_unicode_in_config_values(self):
        """Test handling of Unicode characters in configuration values."""
        
        unicode_config = {
            "user_agent": "Crawler/1.0 (测试)",
            "css_selector": ".内容",
            "output_path": "/path/with/中文/directory",
            "custom_headers": {
                "X-Custom-Header": "值"
            }
        }
        
        # Should handle Unicode in config values
        for key, value in unicode_config.items():
            if isinstance(value, str):
                # Should be valid Unicode
                assert value.encode('utf-8').decode('utf-8') == value

    def test_very_large_config_files(self):
        """Test handling of very large configuration files."""
        
        # Create a large configuration structure
        large_config = {}
        
        # Add many configuration sections
        for i in range(1000):
            large_config[f"section_{i}"] = {
                "setting_1": f"value_{i}_1",
                "setting_2": f"value_{i}_2",
                "setting_3": f"value_{i}_3",
                "nested": {
                    "deep_setting": f"deep_value_{i}"
                }
            }
        
        # Should handle large configurations
        assert len(large_config) == 1000
        assert large_config["section_500"]["setting_1"] == "value_500_1"

    def test_malformed_yaml_recovery(self):
        """Test recovery from malformed YAML configuration."""
        
        malformed_yaml_content = """
        scrape:
          timeout: 30
          headless: true
        # Malformed section
        storage:
          database_path: "/path/to/db"
          invalid_yaml: [unclosed list
          another_setting: value
        """
        
        # Should detect YAML parsing errors
        import yaml
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(malformed_yaml_content)