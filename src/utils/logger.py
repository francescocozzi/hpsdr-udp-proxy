"""
Logging configuration for HPSDR Proxy
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from pythonjsonlogger import jsonlogger

from .config import LoggingConfig


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m',       # Reset
    }

    def format(self, record):
        # Add color to log level
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        return super().format(record)


def setup_logger(
    name: str,
    config: LoggingConfig,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Setup logger with file and console handlers

    Args:
        name: Logger name
        config: Logging configuration
        log_to_file: Enable file logging
        log_to_console: Enable console logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(config.level)
    logger.propagate = False

    # Remove existing handlers
    logger.handlers.clear()

    # File handler
    if log_to_file and config.file:
        log_path = Path(config.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if config.json_format:
            # JSON formatter for structured logging
            json_formatter = jsonlogger.JsonFormatter(
                '%(timestamp)s %(level)s %(name)s %(message)s',
                rename_fields={
                    'levelname': 'level',
                    'asctime': 'timestamp'
                }
            )
            file_handler = RotatingFileHandler(
                config.file,
                maxBytes=config.max_file_size * 1024 * 1024,  # Convert MB to bytes
                backupCount=config.backup_count
            )
            file_handler.setFormatter(json_formatter)
        else:
            # Standard text formatter
            file_formatter = logging.Formatter(config.format)
            file_handler = RotatingFileHandler(
                config.file,
                maxBytes=config.max_file_size * 1024 * 1024,
                backupCount=config.backup_count
            )
            file_handler.setFormatter(file_formatter)

        file_handler.setLevel(config.level)
        logger.addHandler(file_handler)

    # Console handler
    if log_to_console and config.console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = ColoredFormatter(config.format)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(config.level)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance by name

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerContext:
    """Context manager for temporary log level changes"""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self.original_level = None

    def __enter__(self):
        self.original_level = self.logger.level
        self.logger.setLevel(self.level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)


def log_with_context(logger: logging.Logger, level: int):
    """
    Decorator to temporarily change log level

    Args:
        logger: Logger instance
        level: Temporary log level

    Example:
        @log_with_context(logger, logging.DEBUG)
        def debug_function():
            logger.debug("This will be logged even if logger level is INFO")
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with LoggerContext(logger, level):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Performance monitoring decorator
def log_performance(logger: logging.Logger, threshold_ms: float = 100.0):
    """
    Decorator to log function execution time

    Args:
        logger: Logger instance
        threshold_ms: Log warning if execution exceeds this threshold (milliseconds)
    """
    import time
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if elapsed_ms > threshold_ms:
                    logger.warning(
                        f"{func.__name__} took {elapsed_ms:.2f}ms (threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"{func.__name__} took {elapsed_ms:.2f}ms")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if elapsed_ms > threshold_ms:
                    logger.warning(
                        f"{func.__name__} took {elapsed_ms:.2f}ms (threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"{func.__name__} took {elapsed_ms:.2f}ms")

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Exception logging decorator
def log_exceptions(logger: logging.Logger, reraise: bool = True):
    """
    Decorator to log exceptions

    Args:
        logger: Logger instance
        reraise: Whether to re-raise the exception after logging
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Exception in {func.__name__}: {str(e)}")
                if reraise:
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Exception in {func.__name__}: {str(e)}")
                if reraise:
                    raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
