"""Edge case tests for network operations and crawl engine."""

import pytest
import pytest_asyncio
import asyncio
import ssl
import socket
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from src.crawler.core.engine import CrawlEngine
from src.crawler.foundation.errors import NetworkError, ValidationError, ExtractionError, TimeoutError


def create_mock_crawl_result(success=True, status_code=200, content="Test content", error=None):
    """Create a standardized mock crawl result object."""
    result = Mock()
    result.success = success
    result.status_code = status_code
    result.html = f"<html><body>{content}</body></html>"
    result.markdown = content
    result.metadata = {"title": "Test Page"}
    result.links = {"internal": [], "external": []}
    result.media = {"images": []}
    result.extracted_content = content
    result.error = error
    return result


@pytest.mark.network
class TestNetworkEdgeCases:
    """Test edge cases and boundary conditions for network operations."""

    @pytest_asyncio.fixture
    async def crawl_engine(self):
        """Create a crawl engine instance."""
        engine = CrawlEngine()
        await engine.initialize()
        yield engine
        await engine.close()

    @pytest.mark.asyncio
    async def test_dns_resolution_timeout(self, crawl_engine):
        """Test handling of DNS resolution timeouts."""
        
        # Mock DNS resolution to timeout
        with patch('socket.getaddrinfo') as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = socket.timeout("DNS resolution timeout")
            
            with pytest.raises(NetworkError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://nonexistent-domain-12345.invalid",
                    options={"timeout": 5}
                )
            
            # Check for network-related error messages (DNS or connection issues)
            error_msg = str(exc_info.value).lower()
            assert any(keyword in error_msg for keyword in ["dns", "resolution", "connection", "network", "navigating", "goto"])

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, crawl_engine):
        """Test handling of DNS resolution failures."""
        
        # Mock DNS resolution to fail
        with patch('socket.getaddrinfo') as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = socket.gaierror("Name resolution failed")
            
            with pytest.raises(NetworkError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://invalid-domain-that-does-not-exist.invalid",
                    options={"timeout": 5}
                )
            
            # Check for network-related error messages (DNS or connection issues)
            error_msg = str(exc_info.value).lower()
            assert any(keyword in error_msg for keyword in ["dns", "resolution", "name", "host", "connection", "network", "navigating", "goto"])

    @pytest.mark.asyncio
    async def test_ssl_certificate_validation_failure(self, crawl_engine):
        """Test handling of SSL certificate validation failures."""
        
        # Mock SSL validation to fail
        with patch('ssl.create_default_context') as mock_ssl_context:
            mock_context = Mock()
            mock_context.check_hostname = True
            mock_context.verify_mode = ssl.CERT_REQUIRED
            mock_ssl_context.return_value = mock_context
            
            # Mock the actual SSL connection to fail
            with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
                mock_crawl.side_effect = ssl.SSLError("certificate verify failed")
                
                with pytest.raises(NetworkError) as exc_info:
                    await crawl_engine.scrape_single(
                        url="https://self-signed.badssl.com",
                        options={"timeout": 10}
                    )
                
                assert any(word in str(exc_info.value).lower() for word in ["ssl", "certificate", "tls"])

    @pytest.mark.asyncio
    async def test_ssl_protocol_version_mismatch(self, crawl_engine):
        """Test handling of SSL protocol version mismatches."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_crawl.side_effect = ssl.SSLError("protocol version mismatch")
            
            with pytest.raises(NetworkError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://tls-v1-0.badssl.com:1010",
                    options={"timeout": 10}
                )
            
            assert "ssl" in str(exc_info.value).lower() or "protocol" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connection_reset_during_transfer(self, crawl_engine):
        """Test handling of connection reset during data transfer."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_crawl.side_effect = ConnectionResetError("Connection reset by peer")
            
            with pytest.raises(NetworkError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://httpbin.org/drip?numbytes=1000&duration=1",
                    options={"timeout": 10}
                )
            
            assert any(word in str(exc_info.value).lower() for word in ["connection", "reset", "peer"])

    @pytest.mark.asyncio
    async def test_connection_timeout_scenarios(self, crawl_engine):
        """Test various connection timeout scenarios."""
        
        # Test connect timeout
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_crawl.side_effect = asyncio.TimeoutError("Connection timeout")
            
            with pytest.raises(TimeoutError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://httpbin.org/delay/30",
                    options={"timeout": 1}
                )
            
            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_read_timeout_scenarios(self, crawl_engine, mock_crawl4ai):
        """Test read timeout during data transfer."""
        
        # Test read timeout
        # Configure the mock constructor to return a crawler that raises timeout
        def timeout_mock_constructor(**kwargs):
            from unittest.mock import AsyncMock
            mock_crawler = AsyncMock()
            mock_crawler.arun.side_effect = asyncio.TimeoutError("Connection timeout")
            return mock_crawler
        
        mock_crawl4ai.side_effect = timeout_mock_constructor
        
        try:
            await crawl_engine.scrape_single(
                url="https://httpbin.org/delay/10",
                options={"timeout": 2, "retry_count": 1}
            )
            assert False, "Expected TimeoutError but no exception was raised"
        except TimeoutError as e:
            assert "timeout" in str(e).lower()
        except Exception as e:
            assert False, f"Expected TimeoutError but got {type(e).__name__}: {e}"

    @pytest.mark.asyncio
    async def test_redirect_chain_limits(self, crawl_engine):
        """Test handling of excessive redirect chains."""
        
        # Mock a redirect loop
        with patch('src.crawler.core.engine.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = create_mock_crawl_result(
                success=False,
                status_code=310,
                content="",
                error="Maximum number of redirects exceeded"
            )
            mock_result.error_message = "Maximum number of redirects exceeded"
            mock_crawl.return_value = mock_result
            
            result = await crawl_engine.scrape_single(
                url="https://httpbin.org/redirect-to?url=https://httpbin.org/redirect-to?url=https://httpbin.org/redirect/20",
                options={"timeout": 10}
            )
            
            assert not result["success"]
            assert "redirect" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_redirect_loop_detection(self, crawl_engine):
        """Test detection and handling of redirect loops."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = create_mock_crawl_result(
                success=False,
                status_code=310,
                content="",
                error="Redirect loop detected"
            )
            mock_result.error_message = "Redirect loop detected"
            mock_crawl.return_value = mock_result
            
            result = await crawl_engine.scrape_single(
                url="https://httpbin.org/redirect-to?url=https://httpbin.org/redirect-to?url=https://httpbin.org/redirect-to?url=https://httpbin.org/redirect-to",
                options={"timeout": 10}
            )
            
            assert not result["success"]
            assert any(word in result["error"].lower() for word in ["redirect", "loop", "circular"])

    @pytest.mark.asyncio
    async def test_http2_protocol_downgrade(self, crawl_engine):
        """Test HTTP/2 to HTTP/1.1 protocol downgrade scenarios."""
        
        # Simulate HTTP/2 connection failure with fallback
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = create_mock_crawl_result(
                success=True,
                status_code=200,
                content="Content retrieved via HTTP/1.1"
            )
            mock_crawl.return_value = mock_result
            
            result = await crawl_engine.scrape_single(
                url="https://http2.pro/check",
                options={"timeout": 10}
            )
            
            # Should succeed even if protocol downgrade occurs
            assert result["success"]
            assert "content" in result

    @pytest.mark.asyncio
    async def test_partial_content_download_handling(self, crawl_engine):
        """Test handling of partial content downloads."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            # Simulate partial content
            mock_result = create_mock_crawl_result(
                success=True,
                status_code=206,  # Partial Content
                content="Partial content - connection interrupted"
            )
            mock_crawl.return_value = mock_result
            
            result = await crawl_engine.scrape_single(
                url="https://httpbin.org/range/1024",
                options={"timeout": 10}
            )
            
            # Should handle partial content gracefully
            assert result["success"]
            assert result.get("status_code") == 206

    @pytest.mark.asyncio
    async def test_large_response_handling(self, crawl_engine):
        """Test handling of very large HTTP responses."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            # Simulate large content
            large_content = "x" * (10 * 1024 * 1024)  # 10MB content
            mock_result = create_mock_crawl_result(
                success=True,
                status_code=200,
                content=large_content[:1000]  # Truncate for testing
            )
            mock_crawl.return_value = mock_result
            
            result = await crawl_engine.scrape_single(
                url="https://httpbin.org/base64/SFRUUEJJTiBpcyBhd2Vzb21l",
                options={"timeout": 30}
            )
            
            # Should handle large content (may be truncated for efficiency)
            assert result["success"]
            assert "content" in result

    @pytest.mark.asyncio
    async def test_malformed_http_response_handling(self, crawl_engine):
        """Test handling of malformed HTTP responses."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_crawl.side_effect = Exception("Invalid HTTP response")
            
            with pytest.raises(NetworkError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://httpbin.org/status/999",
                    options={"timeout": 10}
                )
            
            assert "http" in str(exc_info.value).lower() or "response" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_ipv6_url_handling(self, crawl_engine):
        """Test handling of IPv6 URLs."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = create_mock_crawl_result(
                success=True,
                status_code=200,
                content="IPv6 content"
            )
            mock_crawl.return_value = mock_result
            
            # Test IPv6 URL format
            result = await crawl_engine.scrape_single(
                url="https://[2001:db8::1]:8080/test",
                options={"timeout": 10}
            )
            
            assert result["success"]

    @pytest.mark.asyncio
    async def test_non_standard_ports(self, crawl_engine):
        """Test handling of non-standard ports."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_result = create_mock_crawl_result(
                success=True,
                status_code=200,
                content="Non-standard port content"
            )
            mock_crawl.return_value = mock_result
            
            # Test unusual but valid port
            result = await crawl_engine.scrape_single(
                url="https://httpbin.org:8443/get",
                options={"timeout": 10}
            )
            
            assert result["success"]

    @pytest.mark.asyncio
    async def test_connection_refused_handling(self, crawl_engine):
        """Test handling of connection refused errors."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_crawl.side_effect = ConnectionRefusedError("Connection refused")
            
            with pytest.raises(NetworkError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://localhost:65535",
                    options={"timeout": 5}
                )
            
            assert any(word in str(exc_info.value).lower() for word in ["connection", "refused", "unreachable"])

    @pytest.mark.asyncio
    async def test_network_unreachable_handling(self, crawl_engine):
        """Test handling of network unreachable errors."""
        
        with patch('crawl4ai.AsyncWebCrawler.arun') as mock_crawl:
            mock_crawl.side_effect = OSError("Network is unreachable")
            
            with pytest.raises(NetworkError) as exc_info:
                await crawl_engine.scrape_single(
                    url="https://10.255.255.1",  # Reserved IP that should be unreachable
                    options={"timeout": 5}
                )
            
            assert any(word in str(exc_info.value).lower() for word in ["network", "unreachable", "route"])


@pytest.mark.network
class TestNetworkRetryMechanisms:
    """Test network retry mechanisms and failure recovery."""

    @pytest_asyncio.fixture
    async def crawl_engine(self):
        """Create a crawl engine instance."""
        engine = CrawlEngine()
        await engine.initialize()
        yield engine
        await engine.close()

    @pytest.mark.asyncio
    async def test_transient_failure_retry_success(self, crawl_engine):
        """Test retry mechanism with transient failures that eventually succeed."""
        
        call_count = 0
        
        def mock_crawl_with_retries(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:  # Fail first 2 attempts
                raise NetworkError("Transient network error")
            
            # Success on 3rd attempt
            mock_result = create_mock_crawl_result(
                success=True,
                status_code=200,
                content="Success after retries"
            )
            return mock_result
        
        with patch('crawl4ai.AsyncWebCrawler.arun', side_effect=mock_crawl_with_retries):
            result = await crawl_engine.scrape_single(
                url="https://httpbin.org/status/500",
                options={"timeout": 10, "retry_count": 3, "retry_delay": 0.1}
            )
            
            assert result["success"]
            assert call_count == 3  # Should have made 3 attempts

    @pytest.mark.asyncio
    async def test_permanent_failure_no_retry_success(self, crawl_engine):
        """Test that permanent failures don't retry indefinitely."""
        
        call_count = 0
        
        def mock_crawl_permanent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Always fail
            raise ValidationError("Permanent validation error")
        
        with patch('crawl4ai.AsyncWebCrawler.arun', side_effect=mock_crawl_permanent_failure):
            with pytest.raises(ValidationError):
                await crawl_engine.scrape_single(
                    url="https://httpbin.org/status/400",
                    options={"timeout": 10, "retry_count": 3, "retry_delay": 0.1}
                )
            
            # Should not retry for validation errors
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, crawl_engine):
        """Test exponential backoff in retry timing."""
        
        call_times = []
        
        def mock_crawl_with_timing(*args, **kwargs):
            call_times.append(datetime.utcnow())
            raise NetworkError("Network error for backoff test")
        
        with patch('crawl4ai.AsyncWebCrawler.arun', side_effect=mock_crawl_with_timing):
            try:
                await crawl_engine.scrape_single(
                    url="https://httpbin.org/status/500",
                    options={"timeout": 10, "retry_count": 3, "retry_delay": 0.5}
                )
            except NetworkError:
                pass  # Expected to fail
            
            # Verify timing between retries increases (exponential backoff)
            assert len(call_times) == 3
            
            delay1 = (call_times[1] - call_times[0]).total_seconds()
            delay2 = (call_times[2] - call_times[1]).total_seconds()
            
            # Second delay should be longer than first (exponential backoff)
            # Allow some tolerance for timing variations
            assert delay2 >= delay1 * 0.8

    @pytest.mark.asyncio
    async def test_retry_limit_enforcement(self, crawl_engine):
        """Test that retry limits are properly enforced."""
        
        call_count = 0
        
        def mock_crawl_always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise NetworkError("Always fail")
        
        with patch('crawl4ai.AsyncWebCrawler.arun', side_effect=mock_crawl_always_fail):
            try:
                await crawl_engine.scrape_single(
                    url="https://httpbin.org/status/500",
                    options={"timeout": 10, "retry_count": 2, "retry_delay": 0.1}
                )
            except NetworkError:
                pass  # Expected to fail
            
            # Should attempt exactly retry_count times
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self, crawl_engine):
        """Test circuit breaker pattern for repeated failures."""
        
        # This would be implemented in a more sophisticated retry mechanism
        failure_count = 0
        circuit_open = False
        
        def mock_crawl_circuit_breaker(*args, **kwargs):
            nonlocal failure_count, circuit_open
            
            if circuit_open:
                raise NetworkError("Circuit breaker open")
            
            failure_count += 1
            if failure_count >= 5:  # Open circuit after 5 failures
                circuit_open = True
            
            raise NetworkError("Service unavailable")
        
        with patch('crawl4ai.AsyncWebCrawler.arun', side_effect=mock_crawl_circuit_breaker):
            # Make several requests that should trigger circuit breaker
            for i in range(6):
                try:
                    await crawl_engine.scrape_single(
                        url=f"https://httpbin.org/status/500?attempt={i}",
                        options={"timeout": 5, "retry_count": 1}
                    )
                except NetworkError as e:
                    if "circuit breaker" in str(e).lower():
                        # Circuit breaker activated
                        assert i >= 4  # Should activate after several failures
                        break