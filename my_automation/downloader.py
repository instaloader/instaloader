"""
Downloader Module
=================
Functions for downloading Instagram carousels and posts using Instaloader.
"""

import csv
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path to import instaloader
sys.path.insert(0, str(Path(__file__).parent.parent))

import instaloader
from instaloader import Post, Instaloader
from instaloader.exceptions import (
    InstaloaderException,
    LoginRequiredException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    QueryReturnedNotFoundException,
)

from .utils import (
    get_logger,
    extract_shortcode_from_url,
    ensure_directory,
    sanitize_filename,
    ProgressTracker,
)


class DownloadError(Exception):
    """Raised when a download operation fails."""
    pass


def create_instaloader_instance(
    username: Optional[str] = None,
    password: Optional[str] = None,
    session_file: Optional[str] = None,
    download_videos: bool = False,
    download_video_thumbnails: bool = False,
    download_geotags: bool = False,
    download_comments: bool = False,
    save_metadata: bool = False,
) -> Instaloader:
    """
    Create and configure an Instaloader instance.

    Args:
        username: Instagram username for login (optional)
        password: Instagram password for login (optional)
        session_file: Path to session file for persistent login
        download_videos: Whether to download videos
        download_video_thumbnails: Whether to download video thumbnails
        download_geotags: Whether to save geotag data
        download_comments: Whether to save comments
        save_metadata: Whether to save post metadata as JSON

    Returns:
        Configured Instaloader instance

    Example:
        >>> L = create_instaloader_instance()
        >>> L = create_instaloader_instance(username="user", password="pass")
    """
    logger = get_logger()

    # Create instance with our preferred settings
    L = Instaloader(
        download_videos=download_videos,
        download_video_thumbnails=download_video_thumbnails,
        download_geotags=download_geotags,
        download_comments=download_comments,
        save_metadata=save_metadata,
        compress_json=False,
        post_metadata_txt_pattern='',  # Don't create txt files
        storyitem_metadata_txt_pattern='',
        filename_pattern='{shortcode}_{medianum}',  # Numbered files for carousel
    )

    # Try to login if credentials provided
    if username and password:
        try:
            logger.info(f"Attempting login as {username}...")
            L.login(username, password)
            logger.info("Login successful")
        except Exception as e:
            logger.warning(f"Login failed: {e}. Continuing without login.")

    # Try to load existing session
    elif session_file and Path(session_file).exists():
        try:
            L.load_session_from_file(username or '', session_file)
            logger.info("Loaded existing session")
        except Exception as e:
            logger.warning(f"Could not load session: {e}")

    return L


def download_carousel(
    post_url: str,
    download_dir: str,
    instaloader_instance: Optional[Instaloader] = None,
    download_videos: bool = False,
) -> List[str]:
    """
    Download all images (and optionally videos) from an Instagram post.

    Works with both single posts and carousels (posts with multiple images).

    Args:
        post_url: URL of the Instagram post
        download_dir: Directory to save downloaded files
        instaloader_instance: Optional pre-configured Instaloader instance
        download_videos: Whether to also download videos in carousels

    Returns:
        List of paths to downloaded image files

    Raises:
        DownloadError: If the download fails

    Example:
        >>> paths = download_carousel(
        ...     "https://www.instagram.com/p/ABC123/",
        ...     "./output/raw"
        ... )
        >>> print(paths)
        ['./output/raw/ABC123/ABC123_1.jpg', './output/raw/ABC123/ABC123_2.jpg']
    """
    logger = get_logger()

    # Extract shortcode from URL
    shortcode = extract_shortcode_from_url(post_url)
    if not shortcode:
        raise DownloadError(f"Could not extract shortcode from URL: {post_url}")

    logger.info(f"Downloading post {shortcode} from {post_url}")

    # Create or use provided Instaloader instance
    L = instaloader_instance or create_instaloader_instance(
        download_videos=download_videos
    )

    # Create post-specific directory
    post_dir = Path(download_dir) / shortcode
    ensure_directory(post_dir)

    downloaded_files: List[str] = []

    try:
        # Get post object from shortcode
        post = Post.from_shortcode(L.context, shortcode)

        # Check if it's a carousel (multiple images/videos)
        is_carousel = post.typename == 'GraphSidecar'

        if is_carousel:
            logger.info(f"Post {shortcode} is a carousel with multiple items")

            # Download each item in the carousel
            for idx, node in enumerate(post.get_sidecar_nodes(), start=1):
                if node.is_video:
                    if download_videos and node.video_url:
                        file_path = post_dir / f"{shortcode}_{idx}.mp4"
                        _download_file(L, node.video_url, str(file_path))
                        downloaded_files.append(str(file_path))
                        logger.info(f"Downloaded video: {file_path}")
                    else:
                        logger.info(f"Skipping video item {idx} (videos disabled)")
                else:
                    # Download image
                    file_path = post_dir / f"{shortcode}_{idx}.jpg"
                    _download_file(L, node.display_url, str(file_path))
                    downloaded_files.append(str(file_path))
                    logger.info(f"Downloaded image: {file_path}")

        else:
            # Single image or video post
            if post.is_video:
                if download_videos and post.video_url:
                    file_path = post_dir / f"{shortcode}_1.mp4"
                    _download_file(L, post.video_url, str(file_path))
                    downloaded_files.append(str(file_path))
                    logger.info(f"Downloaded video: {file_path}")
                else:
                    logger.info(f"Post {shortcode} is a video, skipping (videos disabled)")
            else:
                file_path = post_dir / f"{shortcode}_1.jpg"
                _download_file(L, post.url, str(file_path))
                downloaded_files.append(str(file_path))
                logger.info(f"Downloaded image: {file_path}")

        logger.info(f"Successfully downloaded {len(downloaded_files)} files from {shortcode}")

    except QueryReturnedNotFoundException:
        raise DownloadError(f"Post not found: {post_url}")
    except PrivateProfileNotFollowedException:
        raise DownloadError(f"Post is from a private profile: {post_url}")
    except LoginRequiredException:
        raise DownloadError(f"Login required to access: {post_url}")
    except InstaloaderException as e:
        raise DownloadError(f"Instaloader error for {post_url}: {e}")
    except Exception as e:
        raise DownloadError(f"Unexpected error downloading {post_url}: {e}")

    return downloaded_files


def _download_file(loader: Instaloader, url: str, dest_path: str) -> None:
    """
    Download a file from URL to destination path.

    Args:
        loader: Instaloader instance (used for its session/cookies)
        url: URL to download from
        dest_path: Local path to save file
    """
    import requests

    response = loader.context.get_raw(url)
    with open(dest_path, 'wb') as f:
        f.write(response.content)


def download_from_csv(
    csv_path: str,
    download_base_dir: str,
    url_column: str = 'url',
    instaloader_instance: Optional[Instaloader] = None,
    download_videos: bool = False,
) -> Dict[str, Any]:
    """
    Download posts from a CSV file containing Instagram URLs.

    Args:
        csv_path: Path to CSV file with Instagram URLs
        download_base_dir: Base directory for downloads
        url_column: Name of the column containing URLs (default: 'url')
        instaloader_instance: Optional pre-configured Instaloader instance
        download_videos: Whether to download videos

    Returns:
        Dictionary with download statistics:
        {
            "total_posts": int,
            "successful_posts": int,
            "failed_posts": int,
            "total_images": int,
            "posts": [
                {"url": str, "shortcode": str, "image_paths": list, "error": str or None},
                ...
            ]
        }

    Example:
        >>> result = download_from_csv("./posts.csv", "./output/raw")
        >>> print(f"Downloaded {result['total_images']} images from {result['successful_posts']} posts")
    """
    logger = get_logger()

    # Validate CSV file exists
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Read URLs from CSV
    urls: List[str] = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            if url_column not in reader.fieldnames:
                raise ValueError(
                    f"Column '{url_column}' not found in CSV. "
                    f"Available columns: {reader.fieldnames}"
                )

            for row in reader:
                url = row[url_column].strip()
                if url:
                    urls.append(url)

    except csv.Error as e:
        raise ValueError(f"Error reading CSV file: {e}")

    logger.info(f"Found {len(urls)} URLs in {csv_path}")

    # Create base download directory
    ensure_directory(Path(download_base_dir))

    # Create or use provided Instaloader instance
    L = instaloader_instance or create_instaloader_instance(
        download_videos=download_videos
    )

    # Track results
    results: Dict[str, Any] = {
        "total_posts": len(urls),
        "successful_posts": 0,
        "failed_posts": 0,
        "total_images": 0,
        "posts": []
    }

    # Progress tracker
    tracker = ProgressTracker(len(urls), "Downloading posts")

    # Download each URL
    for url in urls:
        shortcode = extract_shortcode_from_url(url) or "unknown"
        post_result = {
            "url": url,
            "shortcode": shortcode,
            "image_paths": [],
            "error": None
        }

        try:
            image_paths = download_carousel(
                post_url=url,
                download_dir=download_base_dir,
                instaloader_instance=L,
                download_videos=download_videos,
            )
            post_result["image_paths"] = image_paths
            results["successful_posts"] += 1
            results["total_images"] += len(image_paths)

        except DownloadError as e:
            post_result["error"] = str(e)
            results["failed_posts"] += 1
            logger.error(f"Failed to download {url}: {e}")

        except Exception as e:
            post_result["error"] = f"Unexpected error: {e}"
            results["failed_posts"] += 1
            logger.error(f"Unexpected error downloading {url}: {e}")

        results["posts"].append(post_result)
        tracker.update(message=shortcode)

    tracker.complete()

    # Log summary
    logger.info(
        f"Download complete: {results['successful_posts']}/{results['total_posts']} posts, "
        f"{results['total_images']} images, {results['failed_posts']} failures"
    )

    return results


def get_post_info(post_url: str, instaloader_instance: Optional[Instaloader] = None) -> Dict[str, Any]:
    """
    Get information about an Instagram post without downloading.

    Args:
        post_url: URL of the Instagram post
        instaloader_instance: Optional pre-configured Instaloader instance

    Returns:
        Dictionary with post information:
        {
            "shortcode": str,
            "owner": str,
            "caption": str,
            "is_carousel": bool,
            "item_count": int,
            "has_video": bool,
            "date": datetime,
            "likes": int,
        }

    Example:
        >>> info = get_post_info("https://www.instagram.com/p/ABC123/")
        >>> print(f"Post by {info['owner']} with {info['item_count']} items")
    """
    logger = get_logger()

    shortcode = extract_shortcode_from_url(post_url)
    if not shortcode:
        raise DownloadError(f"Could not extract shortcode from URL: {post_url}")

    L = instaloader_instance or create_instaloader_instance()

    try:
        post = Post.from_shortcode(L.context, shortcode)

        is_carousel = post.typename == 'GraphSidecar'
        item_count = 1
        has_video = post.is_video

        if is_carousel:
            nodes = list(post.get_sidecar_nodes())
            item_count = len(nodes)
            has_video = any(node.is_video for node in nodes)

        return {
            "shortcode": shortcode,
            "owner": post.owner_username,
            "caption": post.caption or "",
            "is_carousel": is_carousel,
            "item_count": item_count,
            "has_video": has_video,
            "date": post.date_utc,
            "likes": post.likes,
        }

    except Exception as e:
        logger.error(f"Error getting info for {post_url}: {e}")
        raise DownloadError(f"Could not get post info: {e}")
