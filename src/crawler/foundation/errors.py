"""Error handling and exception management for the Crawler system."""

import time
import traceback
from enum import Enum
from typing import Any, Dict, Optional, List, Type, Union
from dataclasses import dataclass, field
from datetime import datetime

from .logging import get_logger


class ErrorCategory(str, Enum):
    """Categories of errors that can occur in the system."""
    VALIDATION = "validation"
    NETWORK = "network"
    EXTRACTION = "extraction"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RESOURCE = "resource"
    SYSTEM = "system"
    CONFIGURATION = "configuration"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    operation: str
    url: Optional[str] = None
    session_id: Optional[str] = None
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation,
            "url": self.url,
            "session_id": self.session_id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class ErrorInfo:
    """Detailed error information."""
    error_type: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    code: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    context: Optional[ErrorContext] = None
    traceback: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retryable: bool = False
    retry_after: Optional[float] = None


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class CrawlerError(Exception):
    """Base exception class for all Crawler errors."""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[ErrorContext] = None,
        retryable: bool = False,
        retry_after: Optional[float] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.error_code = error_code
        self.details = details
        self.context = context
        self.retryable = retryable
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow()
    
    def to_error_info(self) -> ErrorInfo:
        """Convert exception to ErrorInfo."""
        return ErrorInfo(
            error_type=self.__class__.__name__,
            message=self.message,
            category=self.category,
            severity=self.severity,
            code=self.error_code,
            details=self.details or {},
            context=self.context,
            traceback=traceback.format_exc(),
            timestamp=self.timestamp,
            retryable=self.retryable,
            retry_after=self.retry_after
        )


class ValidationError(CrawlerError):
    """Error raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            error_code="VALIDATION_ERROR",
            retryable=False,
            **kwargs
        )
        self.field = field
        if field:
            if self.details is None:
                self.details = {}
            self.details["field"] = field


class NetworkError(CrawlerError):
    """Error raised when network operations fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, url: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            error_code="NETWORK_ERROR",
            retryable=True,
            **kwargs
        )
        self.status_code = status_code
        self.url = url
        if status_code or url:
            if self.details is None:
                self.details = {}
            if status_code:
                self.details["status_code"] = status_code
            if url:
                self.details["url"] = url


class TimeoutError(CrawlerError):
    """Error raised when operations timeout."""
    
    def __init__(self, message: str, timeout_duration: Optional[float] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            error_code="TIMEOUT_ERROR",
            retryable=True,
            **kwargs
        )
        if timeout_duration:
            if self.details is None:
                self.details = {}
            self.details["timeout_duration"] = timeout_duration


class ExtractionError(CrawlerError):
    """Error raised when content extraction fails."""
    
    def __init__(self, message: str, strategy: Optional[str] = None, selector: Optional[str] = None, extraction_type: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.EXTRACTION,
            severity=ErrorSeverity.MEDIUM,
            error_code="EXTRACTION_ERROR",
            retryable=False,
            **kwargs
        )
        self.strategy = strategy
        self.selector = selector
        if strategy or selector or extraction_type:
            if self.details is None:
                self.details = {}
            if strategy:
                self.details["strategy"] = strategy
            if selector:
                self.details["selector"] = selector
            if extraction_type:
                self.details["extraction_type"] = extraction_type


class AuthenticationError(CrawlerError):
    """Error raised when authentication fails."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            error_code="AUTHENTICATION_ERROR",
            retryable=False,
            **kwargs
        )


class RateLimitError(CrawlerError):
    """Error raised when rate limits are exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[float] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            error_code="RATE_LIMIT_ERROR",
            retryable=True,
            retry_after=retry_after,
            **kwargs
        )


class ConfigurationError(CrawlerError):
    """Error raised when configuration is invalid."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            error_code="CONFIGURATION_ERROR",
            retryable=False,
            **kwargs
        )
        if config_key:
            if self.details is None:
                self.details = {}
            self.details["config_key"] = config_key


class ResourceError(CrawlerError):
    """Error raised when system resources are exhausted."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            error_code="RESOURCE_ERROR",
            retryable=True,
            **kwargs
        )
        self.resource_type = resource_type
        if resource_type:
            if self.details is None:
                self.details = {}
            self.details["resource_type"] = resource_type


class ErrorHandler:
    """Centralized error handling and recovery."""
    
    def __init__(self, max_recent_errors: int = 100):
        self.error_count: int = 0
        self.recent_errors: List[Dict[str, Any]] = []
        self.max_recent_errors = max_recent_errors
        self.error_counts: Dict[str, int] = {}
        self.last_errors: Dict[str, datetime] = {}
    
    def handle_error(
        self,
        error: Union[Exception, ErrorInfo],
        context: Optional[ErrorContext] = None
    ) -> ErrorInfo:
        """Handle and categorize an error.
        
        Args:
            error: Exception or ErrorInfo to handle
            context: Optional error context
            
        Returns:
            ErrorInfo with details
        """
        if isinstance(error, ErrorInfo):
            error_info = error
        elif isinstance(error, CrawlerError):
            error_info = error.to_error_info()
            if context and not error_info.context:
                error_info.context = context
        else:
            # Convert generic exception to ErrorInfo
            error_info = self._categorize_generic_error(error, context)
        
        # Update error tracking
        self._track_error(error_info)
        
        # Log the error
        self._log_error(error_info)
        
        # Report to monitoring (if configured)
        self._report_error(error_info)
        
        return error_info
    
    def _categorize_generic_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None
    ) -> ErrorInfo:
        """Categorize a generic exception."""
        error_type = error.__class__.__name__
        message = str(error)
        
        # Determine category based on exception type and message
        category = ErrorCategory.SYSTEM
        severity = ErrorSeverity.MEDIUM
        retryable = False
        
        if "timeout" in message.lower() or "TimeoutError" in error_type:
            category = ErrorCategory.TIMEOUT
            retryable = True
        elif "connection" in message.lower() or "ConnectionError" in error_type:
            category = ErrorCategory.NETWORK
            retryable = True
        elif "permission" in message.lower() or "PermissionError" in error_type:
            category = ErrorCategory.AUTHORIZATION
            severity = ErrorSeverity.HIGH
        elif "memory" in message.lower() or "MemoryError" in error_type:
            category = ErrorCategory.RESOURCE
            severity = ErrorSeverity.HIGH
            retryable = True
        elif "value" in message.lower() or "ValueError" in error_type:
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.LOW
        
        return ErrorInfo(
            error_type=error_type,
            message=message,
            category=category,
            severity=severity,
            context=context,
            traceback=traceback.format_exc(),
            retryable=retryable
        )
    
    def _track_error(self, error_info: ErrorInfo) -> None:
        """Track error occurrences."""
        # Increment total error count
        self.error_count += 1
        
        # Add to recent errors list (newest first)
        error_record = {
            "error_type": error_info.error_type,
            "message": error_info.message,
            "category": error_info.category.value,
            "severity": error_info.severity.value,
            "context": error_info.context.to_dict() if error_info.context else None,
            "timestamp": error_info.timestamp.isoformat(),
            "retryable": error_info.retryable,
        }
        
        self.recent_errors.insert(0, error_record)
        
        # Limit the size of recent_errors
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[:self.max_recent_errors]
        
        # Legacy tracking for compatibility
        error_key = f"{error_info.category}:{error_info.error_type}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = error_info.timestamp
    
    def _log_error(self, error_info: ErrorInfo) -> None:
        """Log error based on severity."""
        logger = get_logger(__name__)
        log_message = f"{error_info.error_type}: {error_info.message}"
        
        if error_info.context:
            context_info = f" (operation: {error_info.context.operation}"
            if error_info.context.url:
                context_info += f", url: {error_info.context.url}"
            if error_info.context.job_id:
                context_info += f", job: {error_info.context.job_id}"
            context_info += ")"
            log_message += context_info
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, extra={"error_info": error_info})
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(log_message, extra={"error_info": error_info})
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.error(log_message, extra={"error_info": error_info})
        else:
            logger.info(log_message, extra={"error_info": error_info})
        
        # Log traceback for debugging if available
        if error_info.traceback and error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.debug(f"Traceback for {error_info.error_type}:\n{error_info.traceback}")
    
    def _report_error(self, error_info: ErrorInfo) -> None:
        """Report error to monitoring system (placeholder)."""
        # TODO: Implement integration with monitoring systems
        # (e.g., Sentry, DataDog, custom metrics endpoint)
        pass
    
    def should_retry(
        self,
        error: Union[Exception, ErrorInfo],
        attempt: int,
        max_attempts: int = 3
    ) -> bool:
        """Determine if an operation should be retried.
        
        Args:
            error: Error that occurred
            attempt: Current attempt number (1-based)
            max_attempts: Maximum number of attempts
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= max_attempts:
            return False
        
        if isinstance(error, ErrorInfo):
            return error.retryable
        elif isinstance(error, CrawlerError):
            # Special handling for NetworkError
            if isinstance(error, NetworkError) and error.status_code:
                # Non-retryable status codes
                non_retryable_codes = [400, 401, 403, 404, 405, 410, 422]
                if error.status_code in non_retryable_codes:
                    return False
                # Retryable status codes
                retryable_codes = [408, 429, 500, 502, 503, 504]
                if error.status_code in retryable_codes:
                    return True
            return error.retryable
        else:
            # For generic exceptions, check if they're typically retryable
            error_type = error.__class__.__name__
            message = str(error).lower()
            
            retryable_patterns = [
                "timeout", "connection", "network", "temporary",
                "rate limit", "503", "502", "504"
            ]
            
            return any(pattern in message for pattern in retryable_patterns)
    
    def calculate_retry_delay(
        self,
        attempt: int,
        config: Optional[RetryConfig] = None,
        error: Optional[Union[Exception, ErrorInfo]] = None
    ) -> float:
        """Calculate delay before retry.
        
        Args:
            attempt: Current attempt number (1-based)
            config: Retry configuration
            error: Error that occurred (may specify retry_after)
            
        Returns:
            Delay in seconds
        """
        if config is None:
            config = RetryConfig()
        
        # Check if error specifies retry_after
        if error:
            if isinstance(error, (CrawlerError, ErrorInfo)) and error.retry_after:
                return error.retry_after
        
        # Calculate exponential backoff
        delay = config.base_delay * (config.exponential_base ** (attempt - 1))
        delay = min(delay, config.max_delay)
        
        # Add jitter to avoid thundering herd, but ensure minimum delay
        if config.jitter:
            import random
            jitter_factor = (0.5 + random.random() * 0.5)
            delay *= jitter_factor
            # Ensure minimum delay is always base_delay
            delay = max(delay, config.base_delay)
        
        return delay
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics.
        
        Returns:
            Dictionary with error statistics
        """
        return {
            "error_counts": dict(self.error_counts),
            "last_errors": {
                key: timestamp.isoformat()
                for key, timestamp in self.last_errors.items()
            },
            "total_errors": sum(self.error_counts.values())
        }
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        error_types = {}
        operations = {}
        
        for error_record in self.recent_errors:
            error_type = error_record["error_type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            if error_record["context"] and error_record["context"]["operation"]:
                operation = error_record["context"]["operation"]
                operations[operation] = operations.get(operation, 0) + 1
        
        return {
            "total_errors": self.error_count,
            "error_types": error_types,
            "operations": operations,
        }
    
    def clear_errors(self) -> None:
        """Clear error history."""
        self.error_count = 0
        self.recent_errors.clear()
        self.error_counts.clear()
        self.last_errors.clear()
    
    def get_recent_errors_by_type(self, error_type: str) -> List[Dict[str, Any]]:
        """Get recent errors filtered by type."""
        return [
            error for error in self.recent_errors
            if error["error_type"] == error_type
        ]
    
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff."""
        return self.calculate_retry_delay(attempt)


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def handle_error(
    error: Union[Exception, ErrorInfo, str],
    context: Optional[ErrorContext] = None
) -> ErrorInfo:
    """Convenience function to handle an error."""
    # Convert string error to CrawlerError
    if isinstance(error, str):
        error = CrawlerError(error)
    
    # Create default context if none provided
    if context is None:
        context = ErrorContext(operation="unknown")
    
    return get_error_handler().handle_error(error, context)


def should_retry(
    error: Union[Exception, ErrorInfo],
    attempt: int,
    max_attempts: int = 3
) -> bool:
    """Convenience function to check if operation should be retried."""
    return get_error_handler().should_retry(error, attempt, max_attempts)


def calculate_retry_delay(
    attempt: int,
    config: Optional[RetryConfig] = None,
    error: Optional[Union[Exception, ErrorInfo]] = None
) -> float:
    """Convenience function to calculate retry delay."""
    return get_error_handler().calculate_retry_delay(attempt, config, error)