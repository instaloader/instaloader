"""
Watermark Module
================
Functions for adding watermarks/logos to images using Pillow (PIL).
Supports various positions, opacity levels, and batch processing.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Literal

try:
    from PIL import Image, ImageEnhance
except ImportError:
    raise ImportError(
        "Pillow is required. Install it with: pip install Pillow"
    )

from .utils import get_logger, ensure_directory, is_image_file, ProgressTracker


# Type alias for position options
PositionType = Literal['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']


class WatermarkError(Exception):
    """Raised when a watermark operation fails."""
    pass


def add_watermark_to_image(
    input_path: str,
    output_path: str,
    logo_path: str,
    position: PositionType = 'bottom-right',
    opacity: float = 0.3,
    margin: int = 32,
    size_ratio: float = 0.15,
) -> None:
    """
    Add a watermark/logo to a single image.

    The logo is resized proportionally based on the image width and positioned
    according to the specified position parameter. Opacity is applied to make
    the watermark semi-transparent.

    Args:
        input_path: Path to the input image
        output_path: Path where the watermarked image will be saved
        logo_path: Path to the logo/watermark image (PNG with transparency recommended)
        position: Where to place the watermark. Options:
                  'top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'
        opacity: Opacity of the watermark (0.0 = invisible, 1.0 = fully opaque)
        margin: Margin from the edge in pixels (not used for 'center' position)
        size_ratio: Size of logo relative to image width (0.15 = 15% of image width)

    Raises:
        WatermarkError: If the operation fails

    Example:
        >>> add_watermark_to_image(
        ...     "input.jpg",
        ...     "output.jpg",
        ...     "logo.png",
        ...     position='bottom-right',
        ...     opacity=0.3
        ... )
    """
    logger = get_logger()

    # Validate inputs
    if not Path(input_path).exists():
        raise WatermarkError(f"Input image not found: {input_path}")
    if not Path(logo_path).exists():
        raise WatermarkError(f"Logo file not found: {logo_path}")
    if not 0.0 <= opacity <= 1.0:
        raise WatermarkError(f"Opacity must be between 0.0 and 1.0, got: {opacity}")
    if not 0.0 < size_ratio <= 1.0:
        raise WatermarkError(f"Size ratio must be between 0.0 and 1.0, got: {size_ratio}")

    valid_positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']
    if position not in valid_positions:
        raise WatermarkError(f"Invalid position: {position}. Valid options: {valid_positions}")

    try:
        # Open images
        base_image = Image.open(input_path).convert('RGBA')
        logo = Image.open(logo_path).convert('RGBA')

        # Calculate new logo size based on image width
        base_width, base_height = base_image.size
        target_logo_width = int(base_width * size_ratio)

        # Maintain aspect ratio when resizing logo
        logo_width, logo_height = logo.size
        aspect_ratio = logo_height / logo_width
        target_logo_height = int(target_logo_width * aspect_ratio)

        # Resize logo using high-quality resampling
        logo = logo.resize(
            (target_logo_width, target_logo_height),
            Image.Resampling.LANCZOS
        )

        # Apply opacity to logo
        if opacity < 1.0:
            logo = _apply_opacity(logo, opacity)

        # Calculate position
        x, y = _calculate_position(
            base_size=(base_width, base_height),
            logo_size=(target_logo_width, target_logo_height),
            position=position,
            margin=margin
        )

        # Create a transparent layer for the watermark
        watermark_layer = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
        watermark_layer.paste(logo, (x, y), logo)

        # Composite the images
        result = Image.alpha_composite(base_image, watermark_layer)

        # Ensure output directory exists
        ensure_directory(Path(output_path).parent)

        # Convert to RGB if saving as JPEG (no alpha channel)
        output_ext = Path(output_path).suffix.lower()
        if output_ext in ['.jpg', '.jpeg']:
            result = result.convert('RGB')

        # Save the result
        result.save(output_path, quality=95)

        logger.info(f"Watermark added: {input_path} -> {output_path}")

    except Exception as e:
        raise WatermarkError(f"Failed to add watermark to {input_path}: {e}")


def _apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    """
    Apply opacity/transparency to an image.

    Args:
        image: PIL Image with RGBA mode
        opacity: Opacity value (0.0 to 1.0)

    Returns:
        New image with adjusted opacity
    """
    # Split into channels
    r, g, b, a = image.split()

    # Adjust alpha channel
    a = a.point(lambda x: int(x * opacity))

    # Merge back
    return Image.merge('RGBA', (r, g, b, a))


def _calculate_position(
    base_size: Tuple[int, int],
    logo_size: Tuple[int, int],
    position: PositionType,
    margin: int
) -> Tuple[int, int]:
    """
    Calculate the x, y position for the watermark.

    Args:
        base_size: (width, height) of the base image
        logo_size: (width, height) of the logo
        position: Position specification
        margin: Margin from edge in pixels

    Returns:
        (x, y) position tuple
    """
    base_width, base_height = base_size
    logo_width, logo_height = logo_size

    if position == 'top-left':
        return (margin, margin)

    elif position == 'top-right':
        return (base_width - logo_width - margin, margin)

    elif position == 'bottom-left':
        return (margin, base_height - logo_height - margin)

    elif position == 'bottom-right':
        return (base_width - logo_width - margin, base_height - logo_height - margin)

    elif position == 'center':
        return (
            (base_width - logo_width) // 2,
            (base_height - logo_height) // 2
        )

    else:
        # Default to bottom-right
        return (base_width - logo_width - margin, base_height - logo_height - margin)


def add_watermark_batch(
    image_paths: List[str],
    output_dir: str,
    logo_path: str,
    position: PositionType = 'bottom-right',
    opacity: float = 0.3,
    margin: int = 32,
    size_ratio: float = 0.15,
    preserve_structure: bool = True,
) -> List[str]:
    """
    Add watermarks to multiple images in batch.

    Args:
        image_paths: List of input image paths
        output_dir: Base directory for output files
        logo_path: Path to the logo/watermark image
        position: Where to place the watermark
        opacity: Opacity of the watermark (0.0 to 1.0)
        margin: Margin from edge in pixels
        size_ratio: Size of logo relative to image width
        preserve_structure: If True, maintains subdirectory structure from input paths

    Returns:
        List of paths to watermarked images

    Example:
        >>> processed = add_watermark_batch(
        ...     ["./raw/post1/image1.jpg", "./raw/post1/image2.jpg"],
        ...     "./processed",
        ...     "./logo.png"
        ... )
        >>> print(processed)
        ['./processed/post1/image1.jpg', './processed/post1/image2.jpg']
    """
    logger = get_logger()

    if not image_paths:
        logger.warning("No images provided for watermarking")
        return []

    # Validate logo exists
    if not Path(logo_path).exists():
        raise WatermarkError(f"Logo file not found: {logo_path}")

    # Ensure output directory exists
    output_base = Path(output_dir)
    ensure_directory(output_base)

    # Filter to only image files
    valid_images = [p for p in image_paths if is_image_file(p)]

    if len(valid_images) < len(image_paths):
        skipped = len(image_paths) - len(valid_images)
        logger.info(f"Skipping {skipped} non-image files")

    # Track processed files
    processed_files: List[str] = []
    failed_count = 0

    # Progress tracking
    tracker = ProgressTracker(len(valid_images), "Adding watermarks")

    for input_path in valid_images:
        try:
            # Determine output path
            if preserve_structure:
                # Try to preserve subdirectory structure
                input_file = Path(input_path)
                # Get relative path from common parent
                output_path = output_base / input_file.parent.name / input_file.name
            else:
                # Flat structure - all files in output_dir
                output_path = output_base / Path(input_path).name

            # Ensure the output subdirectory exists
            ensure_directory(output_path.parent)

            # Add watermark
            add_watermark_to_image(
                input_path=input_path,
                output_path=str(output_path),
                logo_path=logo_path,
                position=position,
                opacity=opacity,
                margin=margin,
                size_ratio=size_ratio,
            )

            processed_files.append(str(output_path))

        except WatermarkError as e:
            logger.error(f"Failed to watermark {input_path}: {e}")
            failed_count += 1

        except Exception as e:
            logger.error(f"Unexpected error watermarking {input_path}: {e}")
            failed_count += 1

        tracker.update(message=Path(input_path).name)

    tracker.complete()

    # Log summary
    logger.info(
        f"Watermark batch complete: {len(processed_files)} processed, {failed_count} failed"
    )

    return processed_files


def add_watermark_to_folder(
    input_folder: str,
    output_folder: str,
    logo_path: str,
    position: PositionType = 'bottom-right',
    opacity: float = 0.3,
    margin: int = 32,
    size_ratio: float = 0.15,
    recursive: bool = True,
) -> List[str]:
    """
    Add watermarks to all images in a folder.

    Args:
        input_folder: Path to folder containing images
        output_folder: Path to output folder
        logo_path: Path to the logo/watermark image
        position: Where to place the watermark
        opacity: Opacity of the watermark
        margin: Margin from edge in pixels
        size_ratio: Size of logo relative to image width
        recursive: If True, process subdirectories as well

    Returns:
        List of paths to watermarked images

    Example:
        >>> processed = add_watermark_to_folder(
        ...     "./output/raw",
        ...     "./output/processed",
        ...     "./assets/logo.png"
        ... )
    """
    logger = get_logger()

    input_path = Path(input_folder)
    if not input_path.exists():
        raise WatermarkError(f"Input folder not found: {input_folder}")
    if not input_path.is_dir():
        raise WatermarkError(f"Input path is not a directory: {input_folder}")

    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

    if recursive:
        image_files = [
            str(f) for f in input_path.rglob('*')
            if f.suffix.lower() in image_extensions
        ]
    else:
        image_files = [
            str(f) for f in input_path.glob('*')
            if f.suffix.lower() in image_extensions
        ]

    logger.info(f"Found {len(image_files)} images in {input_folder}")

    if not image_files:
        logger.warning("No images found in folder")
        return []

    return add_watermark_batch(
        image_paths=image_files,
        output_dir=output_folder,
        logo_path=logo_path,
        position=position,
        opacity=opacity,
        margin=margin,
        size_ratio=size_ratio,
        preserve_structure=True,
    )


def preview_watermark(
    input_path: str,
    logo_path: str,
    position: PositionType = 'bottom-right',
    opacity: float = 0.3,
    margin: int = 32,
    size_ratio: float = 0.15,
) -> Image.Image:
    """
    Create a preview of the watermarked image without saving.

    Useful for testing watermark settings before batch processing.

    Args:
        input_path: Path to the input image
        logo_path: Path to the logo/watermark image
        position: Where to place the watermark
        opacity: Opacity of the watermark
        margin: Margin from edge in pixels
        size_ratio: Size of logo relative to image width

    Returns:
        PIL Image object with the watermark applied

    Example:
        >>> preview = preview_watermark("test.jpg", "logo.png")
        >>> preview.show()  # Opens in default image viewer
    """
    # Validate inputs
    if not Path(input_path).exists():
        raise WatermarkError(f"Input image not found: {input_path}")
    if not Path(logo_path).exists():
        raise WatermarkError(f"Logo file not found: {logo_path}")

    # Open images
    base_image = Image.open(input_path).convert('RGBA')
    logo = Image.open(logo_path).convert('RGBA')

    # Calculate and apply transformations (same as add_watermark_to_image)
    base_width, base_height = base_image.size
    target_logo_width = int(base_width * size_ratio)
    logo_width, logo_height = logo.size
    aspect_ratio = logo_height / logo_width
    target_logo_height = int(target_logo_width * aspect_ratio)

    logo = logo.resize(
        (target_logo_width, target_logo_height),
        Image.Resampling.LANCZOS
    )

    if opacity < 1.0:
        logo = _apply_opacity(logo, opacity)

    x, y = _calculate_position(
        base_size=(base_width, base_height),
        logo_size=(target_logo_width, target_logo_height),
        position=position,
        margin=margin
    )

    watermark_layer = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
    watermark_layer.paste(logo, (x, y), logo)

    return Image.alpha_composite(base_image, watermark_layer)
