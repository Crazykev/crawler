"""Tests for error handling."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.crawler.foundation.errors import (
    CrawlerError, NetworkError, ValidationError, ExtractionError,
    ResourceError, RateLimitError, ErrorHandler, ErrorContext, ErrorInfo,
    ErrorCategory, ErrorSeverity, handle_error
)


class TestCrawlerError:
    """Test suite for CrawlerError and its subclasses."""
    
    def test_crawler_error_basic(self):
        """Test basic CrawlerError creation."""
        error = CrawlerError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code is None
        assert error.details is None
    
    def test_crawler_error_with_code_and_details(self):
        """Test CrawlerError with error code and details."""
        details = {"key": "value", "number": 42}
        error = CrawlerError("Test error", error_code="TEST001", details=details)
        
        assert error.message == "Test error"
        assert error.error_code == "TEST001"
        assert error.details == details
    
    def test_network_error(self):
        """Test NetworkError creation."""
        error = NetworkError("Connection failed", status_code=500)
        assert isinstance(error, CrawlerError)
        assert error.message == "Connection failed"
        assert error.status_code == 500
        assert error.url is None
    
    def test_network_error_with_url(self):
        """Test NetworkError with URL."""
        error = NetworkError("Request failed", url="https://example.com", status_code=404)
        assert error.url == "https://example.com"
        assert error.status_code == 404
    
    def test_validation_error(self):
        """Test ValidationError creation."""
        error = ValidationError("Invalid input", field="username")
        assert isinstance(error, CrawlerError)
        assert error.message == "Invalid input"
        assert error.field == "username"
    
    def test_extraction_error(self):
        """Test ExtractionError creation."""
        error = ExtractionError("Failed to extract", strategy="css", selector=".content")
        assert isinstance(error, CrawlerError)
        assert error.message == "Failed to extract"
        assert error.strategy == "css"
        assert error.selector == ".content"
    
    def test_resource_error(self):
        """Test ResourceError creation."""
        error = ResourceError("Resource not found", resource_type="session")
        assert isinstance(error, CrawlerError)
        assert error.message == "Resource not found"
        assert error.resource_type == "session"


class TestErrorContext:
    """Test suite for ErrorContext."""
    
    def test_error_context_basic(self):
        """Test basic ErrorContext creation."""
        context = ErrorContext(operation="test_operation")
        assert context.operation == "test_operation"
        assert context.url is None
        assert context.session_id is None
        assert context.metadata == {}
    
    def test_error_context_full(self):
        """Test ErrorContext with all fields."""
        metadata = {"key": "value"}
        context = ErrorContext(
            operation="scrape_page",
            url="https://example.com",
            session_id="session123",
            metadata=metadata
        )
        
        assert context.operation == "scrape_page"
        assert context.url == "https://example.com"
        assert context.session_id == "session123"
        assert context.metadata == metadata
    
    def test_error_context_to_dict(self):
        """Test ErrorContext to_dict method."""
        context = ErrorContext(
            operation="test_op",
            url="https://test.com",
            metadata={"test": True}
        )
        
        context_dict = context.to_dict()
        
        assert context_dict["operation"] == "test_op"
        assert context_dict["url"] == "https://test.com"
        assert context_dict["session_id"] is None
        assert context_dict["metadata"] == {"test": True}


class TestErrorHandler:
    """Test suite for ErrorHandler."""
    
    def test_error_handler_init(self):
        """Test ErrorHandler initialization."""
        handler = ErrorHandler()
        assert handler.error_count == 0
        assert len(handler.recent_errors) == 0
    
    def test_handle_crawler_error(self):
        """Test handling CrawlerError."""
        handler = ErrorHandler()
        error = NetworkError("Connection failed", status_code=500)
        context = ErrorContext(operation="test")
        
        with patch('src.crawler.foundation.errors.get_logger') as mock_logger:
            mock_log = Mock()
            mock_logger.return_value = mock_log
            
            handler.handle_error(error, context)
            
            assert handler.error_count == 1
            assert len(handler.recent_errors) == 1
            
            recorded_error = handler.recent_errors[0]
            assert recorded_error["error_type"] == "NetworkError"
            assert recorded_error["message"] == "Connection failed"
            assert recorded_error["context"]["operation"] == "test"
            
            # Check logging was called
            mock_log.error.assert_called()
    
    def test_handle_generic_exception(self):
        """Test handling generic Exception."""
        handler = ErrorHandler()
        error = ValueError("Invalid value")
        context = ErrorContext(operation="validation")
        
        with patch('src.crawler.foundation.errors.get_logger') as mock_logger:
            mock_log = Mock()
            mock_logger.return_value = mock_log
            
            handler.handle_error(error, context)
            
            assert handler.error_count == 1
            recorded_error = handler.recent_errors[0]
            assert recorded_error["error_type"] == "ValueError"
            assert recorded_error["message"] == "Invalid value"
    
    def test_get_error_statistics(self):
        """Test getting error statistics."""
        handler = ErrorHandler()
        
        # Add some errors
        handler.handle_error(NetworkError("Error 1"), ErrorContext("op1"))
        handler.handle_error(NetworkError("Error 2"), ErrorContext("op1"))
        handler.handle_error(ValidationError("Error 3"), ErrorContext("op2"))
        
        stats = handler.get_error_statistics()
        
        assert stats["total_errors"] == 3
        assert stats["error_types"]["NetworkError"] == 2
        assert stats["error_types"]["ValidationError"] == 1
        assert stats["operations"]["op1"] == 2
        assert stats["operations"]["op2"] == 1
    
    def test_clear_errors(self):
        """Test clearing error history."""
        handler = ErrorHandler()
        
        # Add some errors
        handler.handle_error(NetworkError("Error 1"), ErrorContext("op1"))
        handler.handle_error(ValidationError("Error 2"), ErrorContext("op2"))
        
        assert handler.error_count == 2
        assert len(handler.recent_errors) == 2
        
        # Clear errors
        handler.clear_errors()
        
        assert handler.error_count == 0
        assert len(handler.recent_errors) == 0
    
    def test_recent_errors_limit(self):
        """Test that recent errors list is limited."""
        handler = ErrorHandler(max_recent_errors=3)
        
        # Add more errors than the limit
        for i in range(5):
            handler.handle_error(NetworkError(f"Error {i}"), ErrorContext(f"op{i}"))
        
        assert handler.error_count == 5
        assert len(handler.recent_errors) == 3
        
        # Should contain the 3 most recent errors
        assert handler.recent_errors[0]["message"] == "Error 4"
        assert handler.recent_errors[1]["message"] == "Error 3"
        assert handler.recent_errors[2]["message"] == "Error 2"
    
    def test_get_recent_errors_by_type(self):
        """Test filtering recent errors by type."""
        handler = ErrorHandler()
        
        # Add mixed error types
        handler.handle_error(NetworkError("Network 1"), ErrorContext("op1"))
        handler.handle_error(ValidationError("Validation 1"), ErrorContext("op2"))
        handler.handle_error(NetworkError("Network 2"), ErrorContext("op3"))
        
        network_errors = handler.get_recent_errors_by_type("NetworkError")
        validation_errors = handler.get_recent_errors_by_type("ValidationError")
        
        assert len(network_errors) == 2
        assert len(validation_errors) == 1
        assert network_errors[0]["message"] == "Network 2"
        assert validation_errors[0]["message"] == "Validation 1"
    
    def test_should_retry_network_error(self):
        """Test retry decision for network errors."""
        handler = ErrorHandler()
        
        # Retryable network error
        retryable_error = NetworkError("Connection timeout", status_code=408)
        assert handler.should_retry(retryable_error, attempt=1) is True
        
        # Non-retryable network error
        non_retryable_error = NetworkError("Not found", status_code=404)
        assert handler.should_retry(non_retryable_error, attempt=1) is False
    
    def test_should_retry_max_attempts(self):
        """Test retry decision with max attempts reached."""
        handler = ErrorHandler()
        
        error = NetworkError("Connection timeout", status_code=408)
        
        # Should retry on early attempts
        assert handler.should_retry(error, attempt=1) is True
        assert handler.should_retry(error, attempt=2) is True
        
        # Should not retry when max attempts reached
        assert handler.should_retry(error, attempt=3) is False
    
    def test_should_retry_validation_error(self):
        """Test retry decision for validation errors."""
        handler = ErrorHandler()
        
        error = ValidationError("Invalid input")
        assert handler.should_retry(error, attempt=1) is False
    
    def test_get_retry_delay(self):
        """Test retry delay calculation."""
        handler = ErrorHandler()
        
        # Test exponential backoff
        delay1 = handler.get_retry_delay(attempt=1)
        delay2 = handler.get_retry_delay(attempt=2)
        delay3 = handler.get_retry_delay(attempt=3)
        
        assert delay1 < delay2 < delay3
        assert delay1 >= 1.0  # Base delay
        assert delay3 <= 60.0  # Max delay


class TestGlobalErrorHandling:
    """Test suite for global error handling functions."""
    
    def test_handle_error_function(self):
        """Test global handle_error function."""
        error = NetworkError("Test error")
        context = ErrorContext(operation="test")
        
        with patch('src.crawler.foundation.errors.get_error_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_get_handler.return_value = mock_handler
            
            handle_error(error, context)
            
            mock_handler.handle_error.assert_called_once_with(error, context)
    
    def test_handle_error_without_context(self):
        """Test handle_error without explicit context."""
        error = NetworkError("Test error")
        
        with patch('src.crawler.foundation.errors.get_error_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_get_handler.return_value = mock_handler
            
            handle_error(error)
            
            # Should create default context
            args, kwargs = mock_handler.handle_error.call_args
            assert len(args) == 2
            assert isinstance(args[1], ErrorContext)
    
    def test_handle_error_with_string(self):
        """Test handle_error with string error."""
        with patch('src.crawler.foundation.errors.get_error_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_get_handler.return_value = mock_handler
            
            handle_error("String error message")
            
            # Should convert to CrawlerError
            args, kwargs = mock_handler.handle_error.call_args
            assert isinstance(args[0], CrawlerError)
            assert args[0].message == "String error message"


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling."""
    
    def test_error_chain_handling(self):
        """Test handling chained errors."""
        handler = ErrorHandler()
        
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise NetworkError("Network wrapper") from e
        except NetworkError as network_error:
            handler.handle_error(network_error, ErrorContext("chain_test"))
        
        assert handler.error_count == 1
        error_record = handler.recent_errors[0]
        assert error_record["error_type"] == "NetworkError"
        assert error_record["message"] == "Network wrapper"
    
    def test_concurrent_error_handling(self):
        """Test error handling with concurrent access."""
        import threading
        import time
        
        handler = ErrorHandler()
        errors = []
        
        def add_error(index):
            try:
                error = NetworkError(f"Error {index}")
                handler.handle_error(error, ErrorContext(f"thread_{index}"))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=add_error, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0  # No exceptions during concurrent access
        assert handler.error_count == 10
        assert len(handler.recent_errors) <= handler.max_recent_errors


class TestErrorHandlerEdgeCases:
    """Edge case tests for ErrorHandler."""
    
    def test_handle_error_info_direct(self):
        """Test handling ErrorInfo object directly."""
        handler = ErrorHandler()
        
        error_info = ErrorInfo(
            error_type="TestError",
            message="Direct error info",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            retryable=True
        )
        
        result = handler.handle_error(error_info)
        assert result == error_info
        assert handler.error_count == 1
    
    def test_handle_very_large_error_message(self):
        """Test handling error with extremely large message."""
        handler = ErrorHandler()
        
        large_message = "x" * 10000  # 10KB message
        error = CrawlerError(large_message)
        
        handler.handle_error(error)
        assert handler.error_count == 1
        assert handler.recent_errors[0]["message"] == large_message
    
    def test_error_context_with_none_values(self):
        """Test error context with None values."""
        context = ErrorContext(
            operation="test",
            url=None,
            session_id=None,
            job_id=None,
            user_id=None
        )
        
        context_dict = context.to_dict()
        assert context_dict["url"] is None
        assert context_dict["session_id"] is None
        assert context_dict["operation"] == "test"
    
    def test_categorize_generic_error_special_types(self):
        """Test categorizing special Python exception types."""
        handler = ErrorHandler()
        
        # Test different exception types
        test_cases = [
            (MemoryError("Out of memory"), ErrorCategory.RESOURCE, ErrorSeverity.HIGH),
            (PermissionError("Access denied"), ErrorCategory.AUTHORIZATION, ErrorSeverity.HIGH),
            (ValueError("Invalid value"), ErrorCategory.VALIDATION, ErrorSeverity.LOW),
            (ConnectionError("Connection lost"), ErrorCategory.NETWORK, True),  # Should be retryable
            (RuntimeError("Generic runtime error"), ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM)
        ]
        
        for exception, expected_category, expected_attr in test_cases:
            error_info = handler._categorize_generic_error(exception)
            assert error_info.category == expected_category
            
            if isinstance(expected_attr, ErrorSeverity):
                assert error_info.severity == expected_attr
            elif isinstance(expected_attr, bool):
                assert error_info.retryable == expected_attr
    
    def test_recent_errors_overflow(self):
        """Test recent errors list with overflow beyond max limit."""
        handler = ErrorHandler(max_recent_errors=3)
        
        # Add more errors than limit
        for i in range(5):
            error = CrawlerError(f"Error {i}")
            handler.handle_error(error)
        
        assert len(handler.recent_errors) == 3
        assert handler.error_count == 5
        
        # Check that most recent errors are kept (newest first)
        assert handler.recent_errors[0]["message"] == "Error 4"
        assert handler.recent_errors[1]["message"] == "Error 3"
        assert handler.recent_errors[2]["message"] == "Error 2"
    
    def test_should_retry_complex_scenarios(self):
        """Test retry logic with complex error scenarios."""
        handler = ErrorHandler()
        
        # Test NetworkError with specific status codes
        non_retryable_codes = [400, 401, 403, 404, 405, 410, 422]
        for code in non_retryable_codes:
            error = NetworkError("Test error", status_code=code)
            assert not handler.should_retry(error, 1, 3)
        
        retryable_codes = [408, 429, 500, 502, 503, 504]
        for code in retryable_codes:
            error = NetworkError("Test error", status_code=code)
            assert handler.should_retry(error, 1, 3)
        
        # Test max attempts
        error = NetworkError("Test error", status_code=503)
        assert not handler.should_retry(error, 3, 3)  # At max attempts
        assert not handler.should_retry(error, 4, 3)  # Beyond max attempts
    
    def test_retry_delay_with_specific_retry_after(self):
        """Test retry delay calculation with specific retry_after value."""
        handler = ErrorHandler()
        
        # Error with specific retry_after
        error = RateLimitError("Rate limited", retry_after=60.0)
        delay = handler.calculate_retry_delay(1, error=error)
        assert delay == 60.0
        
        # Error info with retry_after
        error_info = ErrorInfo(
            error_type="RateLimitError",
            message="Rate limited",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            retry_after=45.0
        )
        delay = handler.calculate_retry_delay(2, error=error_info)
        assert delay == 45.0
    
    def test_retry_delay_exponential_backoff_edge_cases(self):
        """Test exponential backoff with edge cases."""
        from crawler.foundation.errors import RetryConfig
        handler = ErrorHandler()
        
        # Test with very high attempt number
        config = RetryConfig(max_delay=10.0)
        delay = handler.calculate_retry_delay(20, config)
        assert delay <= config.max_delay
        
        # Test with jitter disabled
        config = RetryConfig(jitter=False, base_delay=2.0, exponential_base=2.0)
        delay1 = handler.calculate_retry_delay(3, config)
        delay2 = handler.calculate_retry_delay(3, config)
        assert delay1 == delay2  # Should be deterministic without jitter
        
        # Test with zero base delay
        config = RetryConfig(base_delay=0.0)
        delay = handler.calculate_retry_delay(1, config)
        assert delay >= 0.0
    
    def test_error_statistics_edge_cases(self):
        """Test error statistics with edge cases."""
        handler = ErrorHandler()
        
        # Empty handler
        stats = handler.get_error_statistics()
        assert stats["total_errors"] == 0
        assert stats["error_types"] == {}
        assert stats["operations"] == {}
        
        # Add errors with missing context
        error_no_context = CrawlerError("No context")
        handler.handle_error(error_no_context)
        
        # Add error with context missing operation
        context_no_op = ErrorContext(operation="", url="https://test.com")
        error_with_empty_context = CrawlerError("Empty context")
        handler.handle_error(error_with_empty_context, context_no_op)
        
        stats = handler.get_error_statistics()
        assert stats["total_errors"] == 2
        assert "CrawlerError" in stats["error_types"]
    
    def test_specific_error_type_fields(self):
        """Test that specific error types have their expected fields."""
        # ValidationError with field
        val_error = ValidationError("Invalid field", field="username")
        assert val_error.field == "username"
        assert val_error.details["field"] == "username"
        
        # NetworkError with URL and status
        net_error = NetworkError("Network failed", status_code=500, url="https://test.com")
        assert net_error.status_code == 500
        assert net_error.url == "https://test.com"
        assert net_error.details["status_code"] == 500
        assert net_error.details["url"] == "https://test.com"
        
        # ExtractionError with strategy and selector
        ext_error = ExtractionError("Extraction failed", strategy="css", selector=".content", extraction_type="text")
        assert ext_error.strategy == "css"
        assert ext_error.selector == ".content"
        assert ext_error.details["strategy"] == "css"
        assert ext_error.details["selector"] == ".content"
        assert ext_error.details["extraction_type"] == "text"
        
        # ResourceError with resource type
        res_error = ResourceError("Resource exhausted", resource_type="memory")
        assert res_error.resource_type == "memory"
        assert res_error.details["resource_type"] == "memory"
    
    def test_error_handler_clear_comprehensive(self):
        """Test comprehensive clearing of error handler state."""
        handler = ErrorHandler()
        
        # Add various errors
        errors = [
            CrawlerError("Error 1"),
            NetworkError("Network error"),
            ValidationError("Validation error"),
            ExtractionError("Extraction error")
        ]
        
        for error in errors:
            handler.handle_error(error)
        
        # Verify state before clear
        assert handler.error_count > 0
        assert len(handler.recent_errors) > 0
        assert len(handler.error_counts) > 0
        assert len(handler.last_errors) > 0
        
        # Clear all errors
        handler.clear_errors()
        
        # Verify complete clear
        assert handler.error_count == 0
        assert len(handler.recent_errors) == 0
        assert len(handler.error_counts) == 0
        assert len(handler.last_errors) == 0
    
    def test_get_recent_errors_by_type_edge_cases(self):
        """Test getting recent errors by type with edge cases."""
        handler = ErrorHandler()
        
        # Empty handler
        results = handler.get_recent_errors_by_type("NonExistentError")
        assert results == []
        
        # Add mixed error types
        errors = [
            CrawlerError("Generic 1"),
            NetworkError("Network 1"),
            CrawlerError("Generic 2"),
            ValidationError("Validation 1"),
            NetworkError("Network 2")
        ]
        
        for error in errors:
            handler.handle_error(error)
        
        # Test filtering
        network_errors = handler.get_recent_errors_by_type("NetworkError")
        assert len(network_errors) == 2
        
        crawler_errors = handler.get_recent_errors_by_type("CrawlerError")
        assert len(crawler_errors) == 2
        
        validation_errors = handler.get_recent_errors_by_type("ValidationError")
        assert len(validation_errors) == 1
        
        # Non-existent type
        missing_errors = handler.get_recent_errors_by_type("MissingError")
        assert len(missing_errors) == 0
    
    def test_error_context_metadata_complex(self):
        """Test error context with complex metadata."""
        complex_metadata = {
            "nested": {
                "data": {
                    "level": 3,
                    "items": ["a", "b", "c"]
                }
            },
            "numbers": [1, 2, 3, 4, 5],
            "mixed": {"str": "value", "int": 42, "bool": True}
        }
        
        context = ErrorContext(
            operation="complex_test",
            url="https://example.com/complex",
            metadata=complex_metadata
        )
        
        context_dict = context.to_dict()
        assert context_dict["metadata"]["nested"]["data"]["level"] == 3
        assert context_dict["metadata"]["numbers"] == [1, 2, 3, 4, 5]
        assert context_dict["metadata"]["mixed"]["bool"] is True
    
    def test_global_error_functions_edge_cases(self):
        """Test global error handling functions with edge cases."""
        from crawler.foundation.errors import should_retry, calculate_retry_delay
        
        # Test should_retry with generic exception containing retryable patterns
        generic_timeout = Exception("Request timeout occurred")
        assert should_retry(generic_timeout, 1, 3)
        
        generic_network = Exception("Network connection failed")
        assert should_retry(generic_network, 1, 3)
        
        generic_503 = Exception("Server returned 503 error")
        assert should_retry(generic_503, 1, 3)
        
        # Test should_retry with non-retryable generic exception
        generic_other = Exception("Something else happened")
        assert not should_retry(generic_other, 1, 3)
        
        # Test calculate_retry_delay without config
        delay = calculate_retry_delay(2)
        assert delay > 0
    
    def test_error_to_error_info_conversion(self):
        """Test conversion of various error types to ErrorInfo."""
        handler = ErrorHandler()
        
        # Test CrawlerError with all fields
        crawler_error = NetworkError(
            "Network failure",
            status_code=503,
            url="https://api.example.com",
            details={"custom": "data"},
            context=ErrorContext("api_call", url="https://api.example.com"),
            retry_after=30.0
        )
        
        error_info = crawler_error.to_error_info()
        assert error_info.error_type == "NetworkError"
        assert error_info.message == "Network failure"
        assert error_info.category == ErrorCategory.NETWORK
        assert error_info.code == "NETWORK_ERROR"  # Default NetworkError code
        assert error_info.details["custom"] == "data"
        assert error_info.retryable is True
        assert error_info.retry_after == 30.0
        assert error_info.context.operation == "api_call"