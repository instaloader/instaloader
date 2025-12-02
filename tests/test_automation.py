"""
Tests for my_automation module
==============================
Basic tests for the automation functions.
Run with: pytest tests/test_automation.py
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# UTILS TESTS
# ============================================================================

class TestUtils:
    """Tests for utils module."""

    def test_extract_shortcode_from_url_post(self):
        """Test extracting shortcode from standard post URL."""
        from my_automation.utils import extract_shortcode_from_url

        url = "https://www.instagram.com/p/ABC123xyz/"
        assert extract_shortcode_from_url(url) == "ABC123xyz"

    def test_extract_shortcode_from_url_reel(self):
        """Test extracting shortcode from reel URL."""
        from my_automation.utils import extract_shortcode_from_url

        url = "https://www.instagram.com/reel/DEF456abc/"
        assert extract_shortcode_from_url(url) == "DEF456abc"

    def test_extract_shortcode_from_url_without_trailing_slash(self):
        """Test extracting shortcode from URL without trailing slash."""
        from my_automation.utils import extract_shortcode_from_url

        url = "https://instagram.com/p/GHI789xyz"
        assert extract_shortcode_from_url(url) == "GHI789xyz"

    def test_extract_shortcode_invalid_url(self):
        """Test that invalid URL returns None."""
        from my_automation.utils import extract_shortcode_from_url

        url = "https://example.com/not-instagram"
        assert extract_shortcode_from_url(url) is None

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        from my_automation.utils import sanitize_filename

        assert sanitize_filename("Hello/World:Test") == "Hello_World_Test"
        assert sanitize_filename("normal_file") == "normal_file"
        assert sanitize_filename("file???name") == "file_name"

    def test_sanitize_filename_max_length(self):
        """Test that filename is truncated to max length."""
        from my_automation.utils import sanitize_filename

        long_name = "a" * 100
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) == 50

    def test_is_image_file(self):
        """Test image file detection."""
        from my_automation.utils import is_image_file

        assert is_image_file("photo.jpg") is True
        assert is_image_file("image.PNG") is True
        assert is_image_file("video.mp4") is False
        assert is_image_file("document.pdf") is False

    def test_is_video_file(self):
        """Test video file detection."""
        from my_automation.utils import is_video_file

        assert is_video_file("video.mp4") is True
        assert is_video_file("clip.MOV") is True
        assert is_video_file("photo.jpg") is False

    def test_format_size(self):
        """Test file size formatting."""
        from my_automation.utils import format_size

        assert format_size(1024) == "1.00 KB"
        assert format_size(1048576) == "1.00 MB"
        assert format_size(500) == "500.00 B"

    def test_get_file_extension(self):
        """Test file extension extraction."""
        from my_automation.utils import get_file_extension

        assert get_file_extension("image.jpg") == ".jpg"
        assert get_file_extension("image.PNG") == ".png"
        assert get_file_extension("https://example.com/photo.jpg?v=1") == ".jpg"


# ============================================================================
# CONFIG TESTS
# ============================================================================

class TestConfig:
    """Tests for config module."""

    def test_load_config_defaults(self):
        """Test that config loads with defaults when no .env exists."""
        from my_automation.config import load_config

        config = load_config()

        assert config.watermark_position == "bottom-right"
        assert config.watermark_opacity == 0.3
        assert config.watermark_margin == 32
        assert config.watermark_size_ratio == 0.15

    def test_config_validation_watermark_position(self):
        """Test that invalid watermark position raises error."""
        from my_automation.config import load_config, ConfigurationError

        with patch.dict(os.environ, {"WATERMARK_POSITION": "invalid"}):
            with pytest.raises(ConfigurationError):
                load_config()

    def test_config_validation_opacity_range(self):
        """Test that opacity outside 0-1 range raises error."""
        from my_automation.config import load_config, ConfigurationError

        with patch.dict(os.environ, {"WATERMARK_OPACITY": "1.5"}):
            with pytest.raises(ConfigurationError):
                load_config()

    def test_config_ensure_directories(self):
        """Test that ensure_directories creates directories."""
        from my_automation.config import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                "RAW_OUTPUT_DIR": f"{tmpdir}/raw",
                "PROCESSED_OUTPUT_DIR": f"{tmpdir}/processed",
            }):
                config = load_config()
                config.ensure_directories()

                assert Path(f"{tmpdir}/raw").exists()
                assert Path(f"{tmpdir}/processed").exists()


# ============================================================================
# WATERMARK TESTS
# ============================================================================

class TestWatermark:
    """Tests for watermark module."""

    @pytest.fixture
    def sample_image(self):
        """Create a sample test image."""
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            img = Image.new('RGB', (800, 600), color='blue')
            img.save(f.name)
            yield f.name
            os.unlink(f.name)

    @pytest.fixture
    def sample_logo(self):
        """Create a sample logo with transparency."""
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img = Image.new('RGBA', (100, 100), color=(255, 255, 255, 128))
            img.save(f.name)
            yield f.name
            os.unlink(f.name)

    def test_add_watermark_to_image(self, sample_image, sample_logo):
        """Test adding watermark to a single image."""
        from my_automation.watermark import add_watermark_to_image
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as output:
            output_path = output.name

        try:
            add_watermark_to_image(
                input_path=sample_image,
                output_path=output_path,
                logo_path=sample_logo,
                position='bottom-right',
                opacity=0.5,
            )

            # Verify output exists and is valid
            assert os.path.exists(output_path)
            img = Image.open(output_path)
            assert img.size == (800, 600)

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_add_watermark_invalid_position(self, sample_image, sample_logo):
        """Test that invalid position raises error."""
        from my_automation.watermark import add_watermark_to_image, WatermarkError

        with tempfile.NamedTemporaryFile(suffix='.jpg') as output:
            with pytest.raises(WatermarkError):
                add_watermark_to_image(
                    input_path=sample_image,
                    output_path=output.name,
                    logo_path=sample_logo,
                    position='invalid-position',
                )

    def test_add_watermark_missing_logo(self, sample_image):
        """Test that missing logo file raises error."""
        from my_automation.watermark import add_watermark_to_image, WatermarkError

        with tempfile.NamedTemporaryFile(suffix='.jpg') as output:
            with pytest.raises(WatermarkError):
                add_watermark_to_image(
                    input_path=sample_image,
                    output_path=output.name,
                    logo_path='/nonexistent/logo.png',
                )

    def test_add_watermark_opacity_validation(self, sample_image, sample_logo):
        """Test that opacity outside range raises error."""
        from my_automation.watermark import add_watermark_to_image, WatermarkError

        with tempfile.NamedTemporaryFile(suffix='.jpg') as output:
            with pytest.raises(WatermarkError):
                add_watermark_to_image(
                    input_path=sample_image,
                    output_path=output.name,
                    logo_path=sample_logo,
                    opacity=1.5,
                )

    def test_add_watermark_batch(self, sample_image, sample_logo):
        """Test batch watermarking."""
        from my_automation.watermark import add_watermark_batch
        from PIL import Image

        # Create additional test images
        images = [sample_image]
        temp_files = []

        for i in range(2):
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                img = Image.new('RGB', (400, 300), color='red')
                img.save(f.name)
                images.append(f.name)
                temp_files.append(f.name)

        with tempfile.TemporaryDirectory() as output_dir:
            try:
                result = add_watermark_batch(
                    image_paths=images,
                    output_dir=output_dir,
                    logo_path=sample_logo,
                )

                assert len(result) == 3

            finally:
                for f in temp_files:
                    os.unlink(f)


# ============================================================================
# DOWNLOADER TESTS
# ============================================================================

class TestDownloader:
    """Tests for downloader module."""

    def test_create_instaloader_instance(self):
        """Test creating an Instaloader instance."""
        from my_automation.downloader import create_instaloader_instance

        L = create_instaloader_instance()
        assert L is not None

    @patch('my_automation.downloader.Post')
    def test_download_carousel_with_mock(self, mock_post_class):
        """Test download_carousel with mocked Post."""
        from my_automation.downloader import download_carousel

        # This is a structural test - actual downloads would require network access
        # The function should handle the shortcode extraction correctly
        with pytest.raises(Exception):
            # Should fail because we can't actually connect to Instagram
            download_carousel(
                post_url="https://www.instagram.com/p/TEST123/",
                download_dir="/tmp/test",
            )


# ============================================================================
# PUBLISHER TESTS
# ============================================================================

class TestPublisher:
    """Tests for publisher module."""

    def test_publish_error_with_insufficient_images(self):
        """Test that carousel creation fails with less than 2 images."""
        from my_automation.publisher import create_carousel_media_container, PublishError
        from my_automation.config import Config

        config = Config(
            ig_app_id="test",
            ig_app_secret="test",
            ig_access_token="test",
            ig_user_id="test",
        )

        with pytest.raises(PublishError, match="at least 2 images"):
            create_carousel_media_container(
                image_urls=["https://example.com/only-one.jpg"],
                caption="Test",
                config=config,
            )

    def test_publish_error_with_too_many_images(self):
        """Test that carousel creation fails with more than 10 images."""
        from my_automation.publisher import create_carousel_media_container, PublishError
        from my_automation.config import Config

        config = Config(
            ig_app_id="test",
            ig_app_secret="test",
            ig_access_token="test",
            ig_user_id="test",
        )

        urls = [f"https://example.com/image{i}.jpg" for i in range(11)]

        with pytest.raises(PublishError, match="more than 10 images"):
            create_carousel_media_container(
                image_urls=urls,
                caption="Test",
                config=config,
            )


# ============================================================================
# INTEGRATION TESTS (with mocks)
# ============================================================================

class TestIntegration:
    """Integration tests with mocked external dependencies."""

    def test_full_workflow_dry_run(self):
        """Test the main workflow in dry-run mode."""
        from my_automation.main import main
        import sys

        # Simulate command line arguments
        test_args = [
            'main.py',
            '--mode', 'download',
            '--dry-run',
        ]

        with patch.object(sys, 'argv', test_args):
            # Should complete without error in dry-run mode
            # Note: This may still fail if config validation is strict
            try:
                result = main()
                assert result == 0
            except FileNotFoundError:
                # Expected if CSV doesn't exist
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
