"""
Utilities Module
================
Common utility functions and logging setup for the automation system.
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


# Global logger instance
_logger: Optional[logging.Logger] = None


def setup_logging(
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    name: str = "my_automation"
) -> logging.Logger:
    """
    Set up logging to both file and console.

    Args:
        log_file: Path to log file. Defaults to './logs/actions.log'
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        name: Logger name

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging()
        >>> logger.info("Starting download...")
    """
    global _logger

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        fmt='%(levelname)-8s | %(message)s'
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_file is None:
        log_file = "./logs/actions.log"

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """
    Get the configured logger instance.
    If not already set up, creates a default logger.

    Returns:
        Logger instance
    """
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


def extract_shortcode_from_url(url: str) -> Optional[str]:
    """
    Extract the shortcode from an Instagram post URL.

    Supports various Instagram URL formats:
    - https://www.instagram.com/p/SHORTCODE/
    - https://instagram.com/p/SHORTCODE/
    - https://www.instagram.com/reel/SHORTCODE/
    - https://instagr.am/p/SHORTCODE/

    Args:
        url: Instagram post URL

    Returns:
        Shortcode string or None if not found

    Example:
        >>> extract_shortcode_from_url("https://www.instagram.com/p/ABC123xyz/")
        'ABC123xyz'
    """
    # Patterns for different Instagram URL formats
    patterns = [
        r'instagram\.com/p/([A-Za-z0-9_-]+)',
        r'instagram\.com/reel/([A-Za-z0-9_-]+)',
        r'instagr\.am/p/([A-Za-z0-9_-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """
    Sanitize a string to be safe for use as a filename.

    Args:
        name: Original string
        max_length: Maximum length of output string

    Returns:
        Sanitized filename-safe string

    Example:
        >>> sanitize_filename("Hello/World:Test")
        'Hello_World_Test'
    """
    # Replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove or replace other unsafe characters
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    # Replace multiple underscores with single
    name = re.sub(r'_+', '_', name)
    # Trim and limit length
    name = name.strip('_')[:max_length]
    return name or 'unnamed'


def get_timestamp() -> str:
    """
    Get current timestamp in a consistent format.

    Returns:
        Timestamp string in format 'YYYYMMDD_HHMMSS'

    Example:
        >>> get_timestamp()
        '20240115_143052'
    """
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Path to directory

    Returns:
        The same path (for chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_extension(path: str) -> str:
    """
    Get the file extension from a path or URL.

    Args:
        path: File path or URL

    Returns:
        Extension including the dot (e.g., '.jpg') or empty string

    Example:
        >>> get_file_extension("image.jpg")
        '.jpg'
        >>> get_file_extension("https://example.com/photo.png?query=1")
        '.png'
    """
    # Remove query string if present
    path = path.split('?')[0]
    ext = os.path.splitext(path)[1].lower()
    return ext


def is_image_file(path: str) -> bool:
    """
    Check if a file path appears to be an image based on extension.

    Args:
        path: File path or URL

    Returns:
        True if the extension suggests an image file
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    ext = get_file_extension(path)
    return ext in image_extensions


def is_video_file(path: str) -> bool:
    """
    Check if a file path appears to be a video based on extension.

    Args:
        path: File path or URL

    Returns:
        True if the extension suggests a video file
    """
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
    ext = get_file_extension(path)
    return ext in video_extensions


def format_size(size_bytes: int) -> str:
    """
    Format a file size in bytes to a human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., '1.5 MB')

    Example:
        >>> format_size(1536000)
        '1.46 MB'
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


class ProgressTracker:
    """
    Simple progress tracker for batch operations.

    Example:
        >>> tracker = ProgressTracker(total=100, description="Downloading")
        >>> for i in range(100):
        ...     tracker.update()
        >>> tracker.complete()
    """

    def __init__(self, total: int, description: str = "Processing"):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items
            description: Description of the operation
        """
        self.total = total
        self.current = 0
        self.description = description
        self.logger = get_logger()
        self.start_time = datetime.now()

    def update(self, increment: int = 1, message: str = "") -> None:
        """
        Update progress.

        Args:
            increment: Number of items to add to current count
            message: Optional additional message
        """
        self.current += increment
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0

        log_msg = f"{self.description}: {self.current}/{self.total} ({percentage:.1f}%)"
        if message:
            log_msg += f" - {message}"

        self.logger.info(log_msg)

    def complete(self) -> None:
        """Log completion of the operation."""
        elapsed = datetime.now() - self.start_time
        self.logger.info(
            f"{self.description} complete: {self.current} items in {elapsed.total_seconds():.1f}s"
        )
