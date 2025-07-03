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
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[ErrorContext] = None,
        retryable: bool = False,
        retry_after: Optional[float] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.code = code
        self.details = details or {}
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
            code=self.code,
            details=self.details,
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
            code="VALIDATION_ERROR",
            retryable=False,
            **kwargs
        )
        if field:
            self.details["field"] = field


class NetworkError(CrawlerError):
    """Error raised when network operations fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            code="NETWORK_ERROR",
            retryable=True,
            **kwargs
        )
        if status_code:
            self.details["status_code"] = status_code


class TimeoutError(CrawlerError):
    """Error raised when operations timeout."""
    
    def __init__(self, message: str, timeout_duration: Optional[float] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            code="TIMEOUT_ERROR",
            retryable=True,
            **kwargs
        )
        if timeout_duration:
            self.details["timeout_duration"] = timeout_duration


class ExtractionError(CrawlerError):
    """Error raised when content extraction fails."""
    
    def __init__(self, message: str, extraction_type: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.EXTRACTION,
            severity=ErrorSeverity.MEDIUM,
            code="EXTRACTION_ERROR",
            retryable=False,
            **kwargs
        )
        if extraction_type:
            self.details["extraction_type"] = extraction_type


class AuthenticationError(CrawlerError):
    """Error raised when authentication fails."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            code="AUTHENTICATION_ERROR",
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
            code="RATE_LIMIT_ERROR",
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
            code="CONFIGURATION_ERROR",
            retryable=False,
            **kwargs
        )
        if config_key:
            self.details["config_key"] = config_key


class ResourceError(CrawlerError):
    """Error raised when system resources are exhausted."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            code="RESOURCE_ERROR",
            retryable=True,
            **kwargs
        )
        if resource_type:
            self.details["resource_type"] = resource_type


class ErrorHandler:
    """Centralized error handling and recovery."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
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
        error_key = f"{error_info.category}:{error_info.error_type}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = error_info.timestamp
    
    def _log_error(self, error_info: ErrorInfo) -> None:
        """Log error based on severity."""
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
            self.logger.critical(log_message, extra={"error_info": error_info})
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, extra={"error_info": error_info})
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra={"error_info": error_info})
        else:
            self.logger.info(log_message, extra={"error_info": error_info})
        
        # Log traceback for debugging if available
        if error_info.traceback and error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.debug(f"Traceback for {error_info.error_type}:\n{error_info.traceback}")
    
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
        
        # Add jitter to avoid thundering herd
        if config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
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


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def handle_error(
    error: Union[Exception, ErrorInfo],
    context: Optional[ErrorContext] = None
) -> ErrorInfo:
    """Convenience function to handle an error."""
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