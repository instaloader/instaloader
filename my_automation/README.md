# My Automation - Instagram Carousel Tool

A modular automation system built on top of [Instaloader](https://github.com/instaloader/instaloader) for:
- Downloading Instagram carousels (posts with multiple images)
- Adding watermarks/logos to images
- Publishing carousels via Instagram Graph API

## Features

- **Download Carousels**: Download all images from Instagram posts, including carousels with multiple images
- **Batch Processing**: Process multiple posts from a CSV file
- **Watermarking**: Add your logo to images with customizable position, opacity, and size
- **Publishing**: Publish carousels to Instagram via Graph API (requires setup)
- **Flexible CLI**: Run different modes via command line

## Installation

### 1. Install Dependencies

```bash
# Install Instaloader (if not already installed)
pip install instaloader

# Install extra dependencies for my_automation
pip install -r my_automation/requirements-extra.txt
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp my_automation/.env.example my_automation/.env

# Edit with your settings
nano my_automation/.env
```

### 3. Add Your Logo

Place your logo file (PNG with transparency recommended) in:
```
./assets/logo.png
```

### 4. Prepare Your CSV

Create a CSV file with Instagram URLs:
```csv
url
https://www.instagram.com/p/ABC123/
https://www.instagram.com/p/DEF456/
https://www.instagram.com/p/GHI789/
```

Save it as `./posts.csv` or specify a custom path in `.env`.

## Usage

### Basic Modes

```bash
# Download carousels from CSV
python -m my_automation --mode download

# Download and add watermarks
python -m my_automation --mode download_and_watermark

# Only add watermarks (to already downloaded images)
python -m my_automation --mode watermark

# Download a single post
python -m my_automation --mode single --url "https://instagram.com/p/ABC123/"
```

### Advanced Options

```bash
# Use verbose logging
python -m my_automation --mode download -v

# Dry run (show what would be done)
python -m my_automation --mode download --dry-run

# Use custom CSV file
python -m my_automation --mode download --csv ./my_posts.csv

# Also download videos
python -m my_automation --mode download --download-videos

# Full workflow with publishing
python -m my_automation --mode full --publish --image-host-url "https://myserver.com/images/" --caption "Check this out!"
```

### All Options

```
--mode              Operation mode: download, watermark, download_and_watermark, full, single
--url               Instagram post URL (for single mode)
--csv               Path to CSV file with URLs
--env               Path to .env file
--publish           Publish to Instagram (requires Graph API setup)
--caption           Caption for published posts
--image-host-url    Base URL where images are hosted (for publishing)
--download-videos   Also download videos from carousels
-v, --verbose       Enable verbose logging
--dry-run           Show what would be done without making changes
```

## Configuration

### Environment Variables

Create a `.env` file with the following settings:

```bash
# Instagram Graph API (required for publishing)
IG_APP_ID=your_app_id
IG_APP_SECRET=your_app_secret
IG_ACCESS_TOKEN=your_access_token
IG_USER_ID=your_instagram_user_id

# Paths
LOGO_PATH=./assets/logo.png
RAW_OUTPUT_DIR=./output/raw
PROCESSED_OUTPUT_DIR=./output/processed
CSV_INPUT_PATH=./posts.csv

# Instagram credentials (optional, for private content)
IG_USERNAME=
IG_PASSWORD=

# Watermark settings
WATERMARK_POSITION=bottom-right  # top-left, top-right, bottom-left, bottom-right, center
WATERMARK_OPACITY=0.3            # 0.0 to 1.0
WATERMARK_MARGIN=32              # pixels from edge
WATERMARK_SIZE_RATIO=0.15        # logo width as fraction of image width
```

## Output Structure

```
output/
├── raw/                    # Downloaded images
│   ├── ABC123/
│   │   ├── ABC123_1.jpg
│   │   └── ABC123_2.jpg
│   └── DEF456/
│       └── DEF456_1.jpg
└── processed/              # Watermarked images
    ├── ABC123/
    │   ├── ABC123_1.jpg
    │   └── ABC123_2.jpg
    └── DEF456/
        └── DEF456_1.jpg

logs/
└── actions.log             # Activity log
```

## Setting Up Instagram Graph API (for Publishing)

Publishing carousels requires a Facebook/Meta Business account with proper API access.

### Prerequisites

1. **Instagram Business/Creator Account**: Your Instagram account must be a Business or Creator account
2. **Facebook Page**: Connect your Instagram account to a Facebook Page
3. **Facebook App**: Create an app in the [Facebook Developer Console](https://developers.facebook.com/)

### Setup Steps

1. Create a Facebook App with "Instagram Graph API" product
2. Add these permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
3. Generate a long-lived access token
4. Get your Instagram User ID from the API
5. Add credentials to your `.env` file

### Image Hosting Requirement

Instagram Graph API requires images to be accessible via **public URLs**. Options:
- Upload to a CDN (Cloudinary, AWS S3, etc.)
- Host on your own server
- Use ngrok for local development

## Running Tests

```bash
# Install test dependencies
pip install pytest

# Run tests
pytest tests/test_automation.py -v
```

## Project Structure

```
my_automation/
├── __init__.py          # Package initialization
├── __main__.py          # Entry point for python -m
├── config.py            # Configuration management
├── downloader.py        # Instagram download functions
├── watermark.py         # Image watermarking functions
├── publisher.py         # Instagram Graph API publishing
├── main.py              # CLI orchestration
├── utils.py             # Utility functions and logging
├── requirements-extra.txt
├── .env.example
└── README.md
```

## Troubleshooting

### "Login required" error
Some content may require being logged in. Add your Instagram credentials to `.env`:
```bash
IG_USERNAME=your_username
IG_PASSWORD=your_password
```

### "Logo file not found"
Make sure your logo exists at the path specified in `LOGO_PATH`. Default is `./assets/logo.png`.

### Rate limiting
Instagram may temporarily block requests if you download too many posts quickly. Wait a few minutes and try again.

### Publishing fails
- Verify your Graph API credentials are correct
- Ensure images are publicly accessible via URL
- Check that you have the required permissions

## License

This automation module is provided as-is. The underlying Instaloader library has its own license - see the main repository.
