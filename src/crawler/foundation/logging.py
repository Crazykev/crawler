"""Logging configuration for the Crawler system."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from .config import get_config_manager


# ANSI color codes for console output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'


class ColorFormatter(logging.Formatter):
    """Formatter that adds colors to log levels."""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BRIGHT_RED + Colors.BOLD,
    }
    
    def __init__(self, fmt: Optional[str] = None, use_colors: bool = True):
        if fmt is None:
            fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        super().__init__(fmt)
        self.use_colors = use_colors and hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            # Add color to the level name
            color = self.LEVEL_COLORS.get(record.levelno, Colors.WHITE)
            record.levelname = f"{color}{record.levelname}{Colors.RESET}"
            
            # Add color to logger name
            if record.name.startswith('crawler'):
                record.name = f"{Colors.BLUE}{record.name}{Colors.RESET}"
        
        return super().format(record)


class CrawlerLogger:
    """Custom logger configuration for the Crawler system."""
    
    def __init__(self):
        self._loggers = {}
        self._setup_root_logger()
    
    def _setup_root_logger(self) -> None:
        """Set up the root logger configuration."""
        root_logger = logging.getLogger()
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Set default level
        root_logger.setLevel(logging.INFO)
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(ColorFormatter())
        root_logger.addHandler(console_handler)
        
        # Configure specific loggers
        self._configure_external_loggers()
    
    def _configure_external_loggers(self) -> None:
        """Configure external library loggers."""
        # Reduce verbosity of external libraries
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
        logging.getLogger('alembic').setLevel(logging.INFO)
        logging.getLogger('crawl4ai').setLevel(logging.INFO)
        
        # Set crawler loggers to appropriate levels
        logging.getLogger('crawler').setLevel(logging.INFO)
    
    def setup_logging(
        self, 
        level: str = "INFO",
        log_file: Optional[str] = None,
        use_colors: bool = True
    ) -> None:
        """Set up logging configuration.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path
            use_colors: Whether to use colors in console output
        """
        # Convert string level to logging constant
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_formatter = ColorFormatter(use_colors=use_colors)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            log_path = Path(log_file).expanduser()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)
        
        # Configure external loggers
        self._configure_external_loggers()
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with the specified name.
        
        Args:
            name: Logger name
            
        Returns:
            Configured logger instance
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]


# Global logger instance
_crawler_logger: Optional[CrawlerLogger] = None


def get_crawler_logger() -> CrawlerLogger:
    """Get the global CrawlerLogger instance."""
    global _crawler_logger
    if _crawler_logger is None:
        _crawler_logger = CrawlerLogger()
    return _crawler_logger


def setup_logging(level: Optional[str] = None, log_file: Optional[str] = None) -> None:
    """Set up logging configuration using config manager.
    
    Args:
        level: Override log level from config
        log_file: Override log file from config
    """
    config_manager = get_config_manager()
    
    # Use provided values or get from config
    if level is None:
        level = config_manager.get_setting("global.log_level", "WARNING")
    if log_file is None:
        log_file = config_manager.get_setting("global.log_file")
    
    # Set up logging
    crawler_logger = get_crawler_logger()
    crawler_logger.setup_logging(level=level, log_file=log_file)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    crawler_logger = get_crawler_logger()
    return crawler_logger.get_logger(name)


# Convenience function for module-level usage
def configure_logging_from_config() -> None:
    """Configure logging using settings from ConfigManager."""
    try:
        config_manager = get_config_manager()
        level = config_manager.get_setting("global.log_level", "WARNING")
        log_file = config_manager.get_setting("global.log_file")
        setup_logging(level=level, log_file=log_file)
    except Exception as e:
        # Fallback to basic logging if config fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[logging.StreamHandler(sys.stderr)]
        )
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to configure logging from config: {e}")


# Initialize logging when module is imported
try:
    configure_logging_from_config()
except Exception:
    # Fallback to basic configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )