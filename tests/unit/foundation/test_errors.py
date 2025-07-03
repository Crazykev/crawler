"""Tests for error handling."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from crawler.foundation.errors import (
    CrawlerError, NetworkError, ValidationError, ExtractionError,
    ResourceError, ErrorHandler, ErrorContext, handle_error
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
        
        with patch('crawler.foundation.errors.get_logger') as mock_logger:
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
        
        with patch('crawler.foundation.errors.get_logger') as mock_logger:
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
        
        with patch('crawler.foundation.errors.get_error_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_get_handler.return_value = mock_handler
            
            handle_error(error, context)
            
            mock_handler.handle_error.assert_called_once_with(error, context)
    
    def test_handle_error_without_context(self):
        """Test handle_error without explicit context."""
        error = NetworkError("Test error")
        
        with patch('crawler.foundation.errors.get_error_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_get_handler.return_value = mock_handler
            
            handle_error(error)
            
            # Should create default context
            args, kwargs = mock_handler.handle_error.call_args
            assert len(args) == 2
            assert isinstance(args[1], ErrorContext)
    
    def test_handle_error_with_string(self):
        """Test handle_error with string error."""
        with patch('crawler.foundation.errors.get_error_handler') as mock_get_handler:
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