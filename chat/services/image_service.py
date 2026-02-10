"""
Image download and conversion for MMTUK content.
"""

import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)


def download_image(url):
    """
    Download an image from a URL.
    For Substack CDN URLs, appends ?f_png to get PNG format.
    Returns (image_bytes, content_type).
    """
    # Substack CDN: request PNG format
    if 'substackcdn.com' in url and 'f_png' not in url:
        separator = '&' if '?' in url else '?'
        url = f'{url}{separator}f_png'

    resp = httpx.get(
        url,
        headers={'User-Agent': _USER_AGENT},
        follow_redirects=True,
        timeout=30,
    )
    resp.raise_for_status()

    content_type = resp.headers.get('content-type', '')
    return resp.content, content_type


def convert_to_png(image_bytes, source_format=None):
    """
    Convert image bytes to PNG format using Pillow.
    Returns PNG bytes.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB if necessary (e.g. RGBA, CMYK, palette)
    if img.mode in ('RGBA', 'LA'):
        # Preserve transparency
        pass
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    output = io.BytesIO()
    img.save(output, format='PNG')
    return output.getvalue()


def get_image_dimensions(image_path):
    """
    Get the dimensions of an image file.
    Returns (width, height) or (None, None) if unable to read.
    """
    try:
        img = Image.open(image_path)
        return img.size
    except Exception:
        return None, None


def process_image(url, slug):
    """
    Download an image and ensure it's in PNG format.
    Returns (png_bytes, filename) or (None, None) on failure.
    """
    try:
        image_bytes, content_type = download_image(url)
    except Exception:
        logger.exception('Failed to download image from %s', url)
        return None, None

    # Check if already PNG
    is_png = (
        content_type.startswith('image/png')
        or url.lower().endswith('.png')
        or image_bytes[:8] == b'\x89PNG\r\n\x1a\n'
    )

    if not is_png:
        try:
            image_bytes = convert_to_png(image_bytes)
        except Exception:
            logger.exception('Failed to convert image to PNG from %s', url)
            return None, None

    filename = f'{slug}-thumbnail.png'
    return image_bytes, filename
