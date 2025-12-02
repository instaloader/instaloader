"""
Main Orchestration Module
=========================
Command-line interface for the Instagram automation system.
Orchestrates downloading, watermarking, and publishing workflows.

Usage:
    python -m my_automation.main --mode download
    python -m my_automation.main --mode download_and_watermark
    python -m my_automation.main --mode watermark
    python -m my_automation.main --mode full --publish
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import load_config, Config, ConfigurationError
from .downloader import download_from_csv, download_carousel, create_instaloader_instance
from .watermark import add_watermark_batch, add_watermark_to_folder
from .publisher import publish_carousel_from_urls, PublishError
from .utils import setup_logging, get_logger


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Instagram Carousel Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Download carousels from CSV:
    python -m my_automation.main --mode download

    # Download and add watermarks:
    python -m my_automation.main --mode download_and_watermark

    # Only add watermarks to already downloaded images:
    python -m my_automation.main --mode watermark

    # Full workflow with publishing (requires Graph API setup):
    python -m my_automation.main --mode full --publish

    # Download a single post:
    python -m my_automation.main --mode single --url "https://instagram.com/p/ABC123/"

    # Use custom .env file:
    python -m my_automation.main --mode download --env ./custom.env
        """
    )

    parser.add_argument(
        "--mode",
        choices=["download", "watermark", "download_and_watermark", "full", "single"],
        default="download_and_watermark",
        help="Operation mode (default: download_and_watermark)"
    )

    parser.add_argument(
        "--url",
        type=str,
        help="Instagram post URL (required for 'single' mode)"
    )

    parser.add_argument(
        "--csv",
        type=str,
        help="Path to CSV file with URLs (overrides config)"
    )

    parser.add_argument(
        "--env",
        type=str,
        help="Path to .env file (default: auto-detect)"
    )

    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish carousels to Instagram (requires Graph API setup)"
    )

    parser.add_argument(
        "--caption",
        type=str,
        default="",
        help="Caption for published posts"
    )

    parser.add_argument(
        "--image-host-url",
        type=str,
        default="",
        help="Base URL where images are hosted (required for publishing)"
    )

    parser.add_argument(
        "--download-videos",
        action="store_true",
        help="Also download videos from carousels"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    return parser.parse_args()


def mode_download(config: Config, args: argparse.Namespace) -> dict:
    """
    Execute download-only mode.

    Downloads all carousels from CSV to raw output directory.
    """
    logger = get_logger()
    logger.info("=== DOWNLOAD MODE ===")

    csv_path = args.csv or str(config.csv_input_path)

    if args.dry_run:
        logger.info(f"[DRY RUN] Would download posts from: {csv_path}")
        logger.info(f"[DRY RUN] Output directory: {config.raw_output_dir}")
        return {"dry_run": True}

    # Ensure output directory exists
    config.ensure_directories()

    # Create Instaloader instance
    L = create_instaloader_instance(
        username=config.ig_username,
        password=config.ig_password,
        download_videos=args.download_videos,
    )

    # Download from CSV
    result = download_from_csv(
        csv_path=csv_path,
        download_base_dir=str(config.raw_output_dir),
        instaloader_instance=L,
        download_videos=args.download_videos,
    )

    logger.info(
        f"Download complete: {result['successful_posts']}/{result['total_posts']} posts, "
        f"{result['total_images']} images"
    )

    return result


def mode_watermark(config: Config, args: argparse.Namespace) -> dict:
    """
    Execute watermark-only mode.

    Adds watermarks to all images in raw output directory.
    """
    logger = get_logger()
    logger.info("=== WATERMARK MODE ===")

    if args.dry_run:
        logger.info(f"[DRY RUN] Would watermark images from: {config.raw_output_dir}")
        logger.info(f"[DRY RUN] Output directory: {config.processed_output_dir}")
        logger.info(f"[DRY RUN] Logo: {config.logo_path}")
        return {"dry_run": True}

    # Validate logo exists
    config.validate_for_watermark()

    # Ensure output directory exists
    config.ensure_directories()

    # Process all images
    processed_files = add_watermark_to_folder(
        input_folder=str(config.raw_output_dir),
        output_folder=str(config.processed_output_dir),
        logo_path=str(config.logo_path),
        position=config.watermark_position,
        opacity=config.watermark_opacity,
        margin=config.watermark_margin,
        size_ratio=config.watermark_size_ratio,
        recursive=True,
    )

    logger.info(f"Watermark complete: {len(processed_files)} images processed")

    return {"processed_files": processed_files}


def mode_download_and_watermark(config: Config, args: argparse.Namespace) -> dict:
    """
    Execute combined download and watermark mode.
    """
    logger = get_logger()
    logger.info("=== DOWNLOAD AND WATERMARK MODE ===")

    # First download
    download_result = mode_download(config, args)

    if args.dry_run:
        return download_result

    # Then watermark
    watermark_result = mode_watermark(config, args)

    return {
        "download": download_result,
        "watermark": watermark_result,
    }


def mode_single(config: Config, args: argparse.Namespace) -> dict:
    """
    Download and watermark a single Instagram post.
    """
    logger = get_logger()
    logger.info("=== SINGLE POST MODE ===")

    if not args.url:
        logger.error("--url is required for single mode")
        return {"error": "URL required"}

    if args.dry_run:
        logger.info(f"[DRY RUN] Would download: {args.url}")
        return {"dry_run": True}

    config.ensure_directories()

    # Create Instaloader instance
    L = create_instaloader_instance(
        username=config.ig_username,
        password=config.ig_password,
        download_videos=args.download_videos,
    )

    # Download the post
    from .downloader import download_carousel
    image_paths = download_carousel(
        post_url=args.url,
        download_dir=str(config.raw_output_dir),
        instaloader_instance=L,
        download_videos=args.download_videos,
    )

    logger.info(f"Downloaded {len(image_paths)} files")

    # Apply watermarks if logo exists
    processed_paths = []
    if config.logo_path.exists():
        processed_paths = add_watermark_batch(
            image_paths=image_paths,
            output_dir=str(config.processed_output_dir),
            logo_path=str(config.logo_path),
            position=config.watermark_position,
            opacity=config.watermark_opacity,
            margin=config.watermark_margin,
            size_ratio=config.watermark_size_ratio,
        )
        logger.info(f"Watermarked {len(processed_paths)} images")
    else:
        logger.warning(f"Logo not found at {config.logo_path}, skipping watermark")

    return {
        "url": args.url,
        "downloaded": image_paths,
        "processed": processed_paths,
    }


def mode_full(config: Config, args: argparse.Namespace) -> dict:
    """
    Execute full workflow: download, watermark, and optionally publish.
    """
    logger = get_logger()
    logger.info("=== FULL MODE ===")

    # Download and watermark
    result = mode_download_and_watermark(config, args)

    if args.dry_run:
        if args.publish:
            logger.info("[DRY RUN] Would publish carousels to Instagram")
        return result

    # Publish if requested
    if args.publish:
        logger.info("Starting publishing workflow...")

        if not args.image_host_url:
            logger.error(
                "Publishing requires --image-host-url. "
                "Images must be publicly accessible."
            )
            return {**result, "publish_error": "Missing image host URL"}

        try:
            config.validate_for_publish()
        except ConfigurationError as e:
            logger.error(f"Publishing not configured: {e}")
            return {**result, "publish_error": str(e)}

        # Get processed folders
        processed_dir = Path(config.processed_output_dir)
        post_folders = [d for d in processed_dir.iterdir() if d.is_dir()]

        published = []
        for folder in post_folders:
            # Find images in folder
            images = sorted([
                f for f in folder.glob('*')
                if f.suffix.lower() in {'.jpg', '.jpeg', '.png'}
            ])

            if len(images) < 2:
                logger.warning(f"Skipping {folder.name}: needs at least 2 images")
                continue

            if len(images) > 10:
                images = images[:10]

            # Build URLs
            image_urls = [
                f"{args.image_host_url.rstrip('/')}/{folder.name}/{img.name}"
                for img in images
            ]

            caption = args.caption or f"Carousel from {folder.name}"

            try:
                post_id = publish_carousel_from_urls(image_urls, caption, config)
                published.append({
                    "folder": str(folder),
                    "post_id": post_id,
                })
                logger.info(f"Published {folder.name}: {post_id}")

            except PublishError as e:
                logger.error(f"Failed to publish {folder.name}: {e}")

        result["published"] = published

    return result


def main() -> int:
    """
    Main entry point for the CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    args = parse_args()

    # Setup logging
    import logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(level=log_level)

    logger.info("Instagram Carousel Automation")
    logger.info(f"Mode: {args.mode}")

    try:
        # Load configuration
        config = load_config(args.env)

        # Override CSV path if provided
        if args.csv:
            config.csv_input_path = Path(args.csv)

        # Execute the appropriate mode
        if args.mode == "download":
            result = mode_download(config, args)

        elif args.mode == "watermark":
            result = mode_watermark(config, args)

        elif args.mode == "download_and_watermark":
            result = mode_download_and_watermark(config, args)

        elif args.mode == "single":
            result = mode_single(config, args)

        elif args.mode == "full":
            result = mode_full(config, args)

        else:
            logger.error(f"Unknown mode: {args.mode}")
            return 1

        # Check for errors in result
        if result.get("error"):
            logger.error(f"Operation failed: {result['error']}")
            return 1

        logger.info("Operation completed successfully")
        return 0

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
