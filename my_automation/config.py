"""
Configuration Module
====================
Handles loading and validation of environment variables and configuration settings.
Uses python-dotenv to load variables from a .env file.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
except ImportError:
    raise ImportError(
        "python-dotenv is required. Install it with: pip install python-dotenv"
    )


@dataclass
class Config:
    """
    Configuration container with all settings for the automation system.

    Attributes:
        ig_app_id: Instagram/Facebook App ID for Graph API
        ig_app_secret: Instagram/Facebook App Secret
        ig_access_token: Long-lived access token for Graph API
        ig_user_id: Instagram Business/Creator Account ID
        logo_path: Path to the watermark logo file
        raw_output_dir: Directory for downloaded raw images
        processed_output_dir: Directory for watermarked images
        csv_input_path: Path to CSV file with Instagram URLs
        ig_username: Instagram username (for downloading private content)
        ig_password: Instagram password (for downloading private content)
        watermark_position: Position of watermark on image
        watermark_opacity: Opacity of watermark (0.0 to 1.0)
        watermark_margin: Margin from edge in pixels
        watermark_size_ratio: Size of watermark relative to image width (0.0 to 1.0)
    """
    # Instagram Graph API settings
    ig_app_id: Optional[str] = None
    ig_app_secret: Optional[str] = None
    ig_access_token: Optional[str] = None
    ig_user_id: Optional[str] = None

    # Paths
    logo_path: Path = field(default_factory=lambda: Path("./assets/logo.png"))
    raw_output_dir: Path = field(default_factory=lambda: Path("./output/raw"))
    processed_output_dir: Path = field(default_factory=lambda: Path("./output/processed"))
    csv_input_path: Path = field(default_factory=lambda: Path("./posts.csv"))

    # Instagram credentials for downloading
    ig_username: Optional[str] = None
    ig_password: Optional[str] = None

    # Watermark settings
    watermark_position: str = "bottom-right"
    watermark_opacity: float = 0.3
    watermark_margin: int = 32
    watermark_size_ratio: float = 0.15

    def validate_for_download(self) -> None:
        """
        Validates that all required settings for downloading are present.
        Raises ConfigurationError if any required setting is missing.
        """
        # For public posts, no credentials are needed
        # For private posts, username and password are required
        pass

    def validate_for_watermark(self) -> None:
        """
        Validates that all required settings for watermarking are present.
        Raises ConfigurationError if the logo file doesn't exist.
        """
        if not self.logo_path.exists():
            raise ConfigurationError(
                f"Logo file not found at: {self.logo_path}\n"
                "Please ensure the logo file exists or update LOGO_PATH in .env"
            )

    def validate_for_publish(self) -> None:
        """
        Validates that all required settings for publishing are present.
        Raises ConfigurationError if any Graph API credentials are missing.
        """
        missing = []

        if not self.ig_app_id:
            missing.append("IG_APP_ID")
        if not self.ig_app_secret:
            missing.append("IG_APP_SECRET")
        if not self.ig_access_token:
            missing.append("IG_ACCESS_TOKEN")
        if not self.ig_user_id:
            missing.append("IG_USER_ID")

        if missing:
            raise ConfigurationError(
                f"Missing required Graph API credentials: {', '.join(missing)}\n"
                "Please set these in your .env file. See .env.example for reference."
            )

    def ensure_directories(self) -> None:
        """Creates output directories if they don't exist."""
        self.raw_output_dir.mkdir(parents=True, exist_ok=True)
        self.processed_output_dir.mkdir(parents=True, exist_ok=True)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required values."""
    pass


def load_config(env_path: Optional[str] = None) -> Config:
    """
    Load configuration from environment variables and .env file.

    Args:
        env_path: Optional path to .env file. If not provided, searches in:
                  1. Current directory
                  2. my_automation directory
                  3. Project root

    Returns:
        Config object with all settings loaded

    Raises:
        ConfigurationError: If required configuration is missing or invalid

    Example:
        >>> config = load_config()
        >>> print(config.logo_path)
        ./assets/logo.png
    """
    # Try to find .env file
    if env_path:
        env_file = Path(env_path)
    else:
        # Search for .env in common locations
        possible_paths = [
            Path(".env"),
            Path("my_automation/.env"),
            Path(__file__).parent / ".env",
            Path(__file__).parent.parent / ".env",
        ]
        env_file = None
        for path in possible_paths:
            if path.exists():
                env_file = path
                break

    # Load .env file if found
    if env_file and env_file.exists():
        load_dotenv(env_file)

    # Helper to get path with default
    def get_path(key: str, default: str) -> Path:
        value = os.getenv(key, default)
        return Path(value)

    # Helper to get float with default
    def get_float(key: str, default: float) -> float:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            raise ConfigurationError(f"Invalid float value for {key}: {value}")

    # Helper to get int with default
    def get_int(key: str, default: int) -> int:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError(f"Invalid integer value for {key}: {value}")

    # Build config object
    config = Config(
        # Graph API credentials
        ig_app_id=os.getenv("IG_APP_ID") or None,
        ig_app_secret=os.getenv("IG_APP_SECRET") or None,
        ig_access_token=os.getenv("IG_ACCESS_TOKEN") or None,
        ig_user_id=os.getenv("IG_USER_ID") or None,

        # Paths
        logo_path=get_path("LOGO_PATH", "./assets/logo.png"),
        raw_output_dir=get_path("RAW_OUTPUT_DIR", "./output/raw"),
        processed_output_dir=get_path("PROCESSED_OUTPUT_DIR", "./output/processed"),
        csv_input_path=get_path("CSV_INPUT_PATH", "./posts.csv"),

        # Instagram credentials
        ig_username=os.getenv("IG_USERNAME") or None,
        ig_password=os.getenv("IG_PASSWORD") or None,

        # Watermark settings
        watermark_position=os.getenv("WATERMARK_POSITION", "bottom-right"),
        watermark_opacity=get_float("WATERMARK_OPACITY", 0.3),
        watermark_margin=get_int("WATERMARK_MARGIN", 32),
        watermark_size_ratio=get_float("WATERMARK_SIZE_RATIO", 0.15),
    )

    # Validate watermark position
    valid_positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']
    if config.watermark_position not in valid_positions:
        raise ConfigurationError(
            f"Invalid WATERMARK_POSITION: {config.watermark_position}\n"
            f"Valid options: {', '.join(valid_positions)}"
        )

    # Validate opacity range
    if not 0.0 <= config.watermark_opacity <= 1.0:
        raise ConfigurationError(
            f"WATERMARK_OPACITY must be between 0.0 and 1.0, got: {config.watermark_opacity}"
        )

    # Validate size ratio
    if not 0.0 < config.watermark_size_ratio <= 1.0:
        raise ConfigurationError(
            f"WATERMARK_SIZE_RATIO must be between 0.0 and 1.0, got: {config.watermark_size_ratio}"
        )

    return config


# Convenience function to get config as a dictionary
def get_config_dict(env_path: Optional[str] = None) -> dict:
    """
    Load configuration and return as a dictionary.
    Useful for debugging or logging configuration.

    Args:
        env_path: Optional path to .env file

    Returns:
        Dictionary with all configuration values
    """
    config = load_config(env_path)
    return {
        "ig_app_id": "***" if config.ig_app_id else None,
        "ig_app_secret": "***" if config.ig_app_secret else None,
        "ig_access_token": "***" if config.ig_access_token else None,
        "ig_user_id": config.ig_user_id,
        "logo_path": str(config.logo_path),
        "raw_output_dir": str(config.raw_output_dir),
        "processed_output_dir": str(config.processed_output_dir),
        "csv_input_path": str(config.csv_input_path),
        "ig_username": config.ig_username,
        "watermark_position": config.watermark_position,
        "watermark_opacity": config.watermark_opacity,
        "watermark_margin": config.watermark_margin,
        "watermark_size_ratio": config.watermark_size_ratio,
    }
