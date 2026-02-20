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
        timeout=httpx.Timeout(connect=5, read=20, write=5, pool=5),
    )
    resp.raise_for_status()

    content_type = resp.headers.get('content-type', '')
    return resp.content, content_type


def optimize_image(image_bytes, source_format=None, max_width=1200):
    """
    Optimize image bytes for web delivery using WebP.

    - Photos (RGB): WebP lossy, quality=82 — typically 80-150 KB at 1200px
    - Transparent images (RGBA/LA): WebP lossless — still much smaller than PNG
    - Resizes to max_width (maintaining aspect ratio) if the image is wider.

    Returns WebP bytes.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Resize if wider than max_width (maintain aspect ratio)
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    output = io.BytesIO()

    if img.mode in ('RGBA', 'LA'):
        # Preserve transparency — WebP lossless
        img.save(output, format='WEBP', lossless=True)
    else:
        # Convert to RGB if necessary (e.g. CMYK, palette)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        # Lossy WebP — quality 82, method 6 (best compression)
        img.save(output, format='WEBP', quality=82, method=6)

    return output.getvalue()


# Backward-compat alias — used by upload_image() in views.py
convert_to_png = optimize_image


def get_image_dimensions(image_path):
    """
    Get the dimensions of an image file.
    Returns (width, height) or (None, None) if unable to read.
    """
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        return None, None


def process_image(url, slug):
    """
    Download an image and optimize it as WebP.
    Returns (webp_bytes, filename) or (None, None) on failure.
    """
    try:
        image_bytes, content_type = download_image(url)
    except Exception:
        logger.exception('Failed to download image from %s', url)
        return None, None

    # Always optimize + resize (handles format conversion and max_width in one step)
    try:
        image_bytes = optimize_image(image_bytes, max_width=1200)
    except Exception:
        logger.exception('Failed to process image from %s', url)
        return None, None

    filename = f'{slug}-thumbnail.webp'
    return image_bytes, filename
