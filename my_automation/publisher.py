"""
Publisher Module
================
Functions for publishing carousels to Instagram using the Instagram Graph API.

IMPORTANT: This module requires a Facebook/Meta Business account with:
1. An Instagram Business or Creator account connected to a Facebook Page
2. A registered Facebook App with Instagram Graph API permissions
3. A long-lived access token with the following permissions:
   - instagram_basic
   - instagram_content_publish
   - pages_read_engagement

For setup instructions, see:
https://developers.facebook.com/docs/instagram-api/getting-started

Flow for publishing a carousel:
1. Upload each image to get media container IDs
2. Create a carousel container referencing all media containers
3. Publish the carousel container

Note: Images must be hosted on a publicly accessible URL.
For local images, you'll need to either:
- Host them temporarily on a server
- Use a service like Imgur or Cloudinary
- Set up a local tunnel with ngrok
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    import requests
except ImportError:
    raise ImportError(
        "requests is required. Install it with: pip install requests"
    )

from .utils import get_logger, is_image_file
from .config import Config


# Instagram Graph API base URL
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


class PublishError(Exception):
    """Raised when a publishing operation fails."""
    pass


@dataclass
class MediaContainer:
    """Represents an Instagram media container."""
    container_id: str
    status: str
    is_carousel_item: bool = False


def _make_api_request(
    endpoint: str,
    method: str = "POST",
    params: Optional[Dict[str, Any]] = None,
    access_token: str = "",
) -> Dict[str, Any]:
    """
    Make a request to the Instagram Graph API.

    Args:
        endpoint: API endpoint (relative to base URL)
        method: HTTP method (GET or POST)
        params: Request parameters
        access_token: Instagram access token

    Returns:
        JSON response as dictionary

    Raises:
        PublishError: If the API request fails
    """
    logger = get_logger()

    url = f"{GRAPH_API_BASE}/{endpoint}"
    params = params or {}
    params["access_token"] = access_token

    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=60)
        else:
            response = requests.post(url, data=params, timeout=60)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        error_data = {}
        try:
            error_data = e.response.json()
        except Exception:
            pass

        error_msg = error_data.get("error", {}).get("message", str(e))
        logger.error(f"API Error: {error_msg}")
        raise PublishError(f"Instagram API error: {error_msg}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise PublishError(f"Request failed: {e}")


def upload_image_for_carousel(
    image_url: str,
    config: Config,
) -> str:
    """
    Upload a single image as a carousel item container.

    This creates a media container that can be used as part of a carousel.
    The image must be accessible via a public URL.

    Args:
        image_url: Public URL of the image to upload
        config: Configuration object with API credentials

    Returns:
        Media container ID

    Raises:
        PublishError: If the upload fails

    API Endpoint:
        POST /{ig-user-id}/media

    Required Parameters:
        - image_url: Public URL of the image
        - is_carousel_item: true (indicates this is part of a carousel)
        - access_token: Valid access token

    Example:
        >>> container_id = upload_image_for_carousel(
        ...     "https://example.com/image1.jpg",
        ...     config
        ... )
    """
    logger = get_logger()
    logger.info(f"Uploading carousel item: {image_url}")

    config.validate_for_publish()

    params = {
        "image_url": image_url,
        "is_carousel_item": "true",
    }

    response = _make_api_request(
        endpoint=f"{config.ig_user_id}/media",
        method="POST",
        params=params,
        access_token=config.ig_access_token,
    )

    container_id = response.get("id")
    if not container_id:
        raise PublishError("No container ID returned from API")

    logger.info(f"Created carousel item container: {container_id}")
    return container_id


def create_carousel_media_container(
    image_urls: List[str],
    caption: str,
    config: Config,
) -> str:
    """
    Create a carousel media container from multiple images.

    This uploads all images as carousel items and creates a parent
    carousel container that references them.

    Args:
        image_urls: List of public URLs for images (2-10 images)
        caption: Caption/description for the carousel post
        config: Configuration object with API credentials

    Returns:
        Carousel container ID ready for publishing

    Raises:
        PublishError: If the operation fails

    API Flow:
        1. POST /{ig-user-id}/media for each image (with is_carousel_item=true)
        2. POST /{ig-user-id}/media with media_type=CAROUSEL and children=container_ids

    Limits:
        - Minimum 2 images, maximum 10 images per carousel
        - Images must be JPEG format
        - Maximum 8MB per image
        - Aspect ratio between 4:5 and 1.91:1

    Example:
        >>> container_id = create_carousel_media_container(
        ...     ["https://example.com/1.jpg", "https://example.com/2.jpg"],
        ...     "Check out these photos!",
        ...     config
        ... )
    """
    logger = get_logger()

    # Validate input
    if len(image_urls) < 2:
        raise PublishError("Carousel requires at least 2 images")
    if len(image_urls) > 10:
        raise PublishError("Carousel cannot have more than 10 images")

    config.validate_for_publish()

    logger.info(f"Creating carousel with {len(image_urls)} images")

    # Step 1: Upload each image as a carousel item
    child_container_ids = []

    for idx, image_url in enumerate(image_urls, start=1):
        logger.info(f"Uploading image {idx}/{len(image_urls)}")

        try:
            container_id = upload_image_for_carousel(image_url, config)
            child_container_ids.append(container_id)

            # Small delay to avoid rate limiting
            if idx < len(image_urls):
                time.sleep(1)

        except PublishError as e:
            logger.error(f"Failed to upload image {idx}: {e}")
            raise

    # Step 2: Create the carousel container
    logger.info("Creating carousel container...")

    params = {
        "media_type": "CAROUSEL",
        "caption": caption,
        "children": ",".join(child_container_ids),
    }

    response = _make_api_request(
        endpoint=f"{config.ig_user_id}/media",
        method="POST",
        params=params,
        access_token=config.ig_access_token,
    )

    carousel_container_id = response.get("id")
    if not carousel_container_id:
        raise PublishError("No carousel container ID returned from API")

    logger.info(f"Created carousel container: {carousel_container_id}")
    return carousel_container_id


def check_container_status(
    container_id: str,
    config: Config,
) -> Dict[str, Any]:
    """
    Check the status of a media container.

    Before publishing, containers must be in "FINISHED" status.

    Args:
        container_id: Media container ID to check
        config: Configuration object with API credentials

    Returns:
        Dictionary with status information:
        {
            "id": str,
            "status_code": str,  # "FINISHED", "IN_PROGRESS", "ERROR"
            "status": str,       # Detailed status message (if error)
        }

    API Endpoint:
        GET /{container-id}?fields=status_code

    Example:
        >>> status = check_container_status(container_id, config)
        >>> if status["status_code"] == "FINISHED":
        ...     publish_carousel(container_id, config)
    """
    logger = get_logger()

    config.validate_for_publish()

    response = _make_api_request(
        endpoint=container_id,
        method="GET",
        params={"fields": "status_code,status"},
        access_token=config.ig_access_token,
    )

    status_code = response.get("status_code", "UNKNOWN")
    logger.info(f"Container {container_id} status: {status_code}")

    return response


def wait_for_container_ready(
    container_id: str,
    config: Config,
    max_attempts: int = 30,
    delay_seconds: int = 2,
) -> bool:
    """
    Wait for a media container to be ready for publishing.

    Polls the container status until it's FINISHED or times out.

    Args:
        container_id: Media container ID to wait for
        config: Configuration object with API credentials
        max_attempts: Maximum number of status checks
        delay_seconds: Delay between checks in seconds

    Returns:
        True if container is ready, False if timed out or error

    Example:
        >>> if wait_for_container_ready(container_id, config):
        ...     publish_carousel(container_id, config)
    """
    logger = get_logger()
    logger.info(f"Waiting for container {container_id} to be ready...")

    for attempt in range(max_attempts):
        status = check_container_status(container_id, config)
        status_code = status.get("status_code", "")

        if status_code == "FINISHED":
            logger.info("Container is ready for publishing")
            return True

        elif status_code == "ERROR":
            error_msg = status.get("status", "Unknown error")
            logger.error(f"Container processing failed: {error_msg}")
            return False

        elif status_code == "IN_PROGRESS":
            logger.info(f"Processing... (attempt {attempt + 1}/{max_attempts})")
            time.sleep(delay_seconds)

        else:
            logger.warning(f"Unknown status: {status_code}")
            time.sleep(delay_seconds)

    logger.error("Timed out waiting for container to be ready")
    return False


def publish_carousel(
    container_id: str,
    config: Config,
) -> str:
    """
    Publish a carousel container to Instagram.

    The container must be in FINISHED status before publishing.

    Args:
        container_id: Carousel container ID to publish
        config: Configuration object with API credentials

    Returns:
        ID of the published Instagram post

    Raises:
        PublishError: If publishing fails

    API Endpoint:
        POST /{ig-user-id}/media_publish

    Required Parameters:
        - creation_id: The container ID to publish
        - access_token: Valid access token

    Example:
        >>> post_id = publish_carousel(container_id, config)
        >>> print(f"Published! Post ID: {post_id}")
    """
    logger = get_logger()

    config.validate_for_publish()

    logger.info(f"Publishing carousel container: {container_id}")

    # Check if container is ready
    if not wait_for_container_ready(container_id, config):
        raise PublishError("Container is not ready for publishing")

    # Publish
    params = {
        "creation_id": container_id,
    }

    response = _make_api_request(
        endpoint=f"{config.ig_user_id}/media_publish",
        method="POST",
        params=params,
        access_token=config.ig_access_token,
    )

    post_id = response.get("id")
    if not post_id:
        raise PublishError("No post ID returned from API")

    logger.info(f"Successfully published carousel! Post ID: {post_id}")
    return post_id


def publish_carousel_from_urls(
    image_urls: List[str],
    caption: str,
    config: Config,
) -> str:
    """
    Complete flow to publish a carousel from image URLs.

    This is a convenience function that:
    1. Creates carousel item containers for each image
    2. Creates the carousel container
    3. Waits for processing to complete
    4. Publishes the carousel

    Args:
        image_urls: List of public URLs for images (2-10 images)
        caption: Caption for the carousel
        config: Configuration object with API credentials

    Returns:
        ID of the published Instagram post

    Raises:
        PublishError: If any step fails

    Example:
        >>> post_id = publish_carousel_from_urls(
        ...     [
        ...         "https://example.com/image1.jpg",
        ...         "https://example.com/image2.jpg",
        ...     ],
        ...     "My carousel post!",
        ...     config
        ... )
    """
    logger = get_logger()
    logger.info("Starting carousel publishing flow...")

    # Create the carousel container
    container_id = create_carousel_media_container(image_urls, caption, config)

    # Publish it
    return publish_carousel(container_id, config)


def publish_carousel_from_folder(
    folder_path: str,
    caption: str,
    config: Config,
    image_hosting_base_url: str = "",
) -> str:
    """
    Publish a carousel from images in a local folder.

    IMPORTANT: Instagram Graph API requires publicly accessible image URLs.
    You must provide a base URL where your images are hosted, or set up
    image hosting separately before calling this function.

    Args:
        folder_path: Path to folder containing images
        caption: Caption for the carousel
        config: Configuration object with API credentials
        image_hosting_base_url: Base URL where images are publicly hosted
                                (e.g., "https://yourserver.com/images/")
                                Images should be accessible at base_url + filename

    Returns:
        ID of the published Instagram post

    Raises:
        PublishError: If publishing fails or no images found

    Note:
        This function assumes images in folder_path are also available at
        image_hosting_base_url with the same filenames. You need to upload
        images to your server first using a separate process.

    Example:
        >>> # First, upload images to your server
        >>> # Then call this function
        >>> post_id = publish_carousel_from_folder(
        ...     "./output/processed/ABC123",
        ...     "Check out these photos!",
        ...     config,
        ...     "https://myserver.com/uploads/"
        ... )
    """
    logger = get_logger()

    # Validate folder
    folder = Path(folder_path)
    if not folder.exists():
        raise PublishError(f"Folder not found: {folder_path}")

    # Find images
    image_extensions = {'.jpg', '.jpeg', '.png'}
    images = sorted([
        f for f in folder.glob('*')
        if f.suffix.lower() in image_extensions
    ])

    if len(images) < 2:
        raise PublishError(
            f"Need at least 2 images for carousel, found {len(images)} in {folder_path}"
        )

    if len(images) > 10:
        logger.warning(f"Found {len(images)} images, using first 10")
        images = images[:10]

    logger.info(f"Found {len(images)} images in {folder_path}")

    if not image_hosting_base_url:
        raise PublishError(
            "image_hosting_base_url is required. Images must be publicly accessible. "
            "Upload images to a server and provide the base URL."
        )

    # Build image URLs
    image_urls = [
        f"{image_hosting_base_url.rstrip('/')}/{img.name}"
        for img in images
    ]

    return publish_carousel_from_urls(image_urls, caption, config)


# ============================================================================
# SETUP INSTRUCTIONS
# ============================================================================
"""
SETUP GUIDE FOR INSTAGRAM GRAPH API

1. CREATE A FACEBOOK APP
   - Go to https://developers.facebook.com/
   - Create a new app of type "Business"
   - Add the "Instagram Graph API" product

2. CONNECT INSTAGRAM ACCOUNT
   - Your Instagram account must be a Business or Creator account
   - Connect it to a Facebook Page you manage
   - This can be done in Instagram settings > Account > Switch to Professional Account

3. GET PERMISSIONS
   Your app needs these permissions:
   - instagram_basic
   - instagram_content_publish
   - pages_read_engagement

   For testing, use the Graph API Explorer to generate tokens with these permissions.

4. GET YOUR INSTAGRAM USER ID
   Use this API call:
   GET /me/accounts?fields=instagram_business_account

   Or use the Graph API Explorer to find your IG User ID.

5. GENERATE A LONG-LIVED ACCESS TOKEN
   Short-lived tokens expire in 1 hour. Exchange for a long-lived token:
   GET /oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &fb_exchange_token={short-lived-token}

   Long-lived tokens last 60 days.

6. SET UP YOUR .env FILE
   IG_APP_ID=your_app_id
   IG_APP_SECRET=your_app_secret
   IG_ACCESS_TOKEN=your_long_lived_token
   IG_USER_ID=your_ig_user_id

7. IMAGE HOSTING
   Images must be accessible via public URLs. Options:
   - Use a CDN like Cloudinary
   - Host on your own server
   - Use a temporary hosting service
   - Set up ngrok for local development

RATE LIMITS:
- 25 API calls per user per hour for content publishing
- Carousel creation counts as multiple calls (1 per image + 1 for carousel)

SUPPORTED FORMATS:
- JPEG images only for publishing
- Maximum 8MB per image
- Aspect ratio between 4:5 (portrait) and 1.91:1 (landscape)
- Minimum 320x320 pixels
"""
