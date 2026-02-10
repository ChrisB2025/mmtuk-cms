"""
PDF extraction service: text and image extraction using PyMuPDF.
"""

import io
import logging
import os
import shutil

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_PAGES = 100
MAX_IMAGES = 20


def extract_pdf(file_bytes, filename):
    """
    Extract text and images from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file.
        filename: Original filename (for logging/metadata).

    Returns:
        dict with keys: filename, page_count, text, images, metadata.
        Each image is {page, data, ext, width, height}.

    Raises:
        ValueError: If the file is too large, has too many pages, or is encrypted.
    """
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f'PDF exceeds the {MAX_FILE_SIZE // (1024*1024)}MB size limit.')

    try:
        doc = fitz.open(stream=file_bytes, filetype='pdf')
    except Exception as exc:
        raise ValueError(f'Could not open PDF: {exc}')

    if doc.is_encrypted:
        doc.close()
        raise ValueError('This PDF is encrypted/password-protected and cannot be processed.')

    if doc.page_count > MAX_PAGES:
        doc.close()
        raise ValueError(f'PDF has {doc.page_count} pages, which exceeds the {MAX_PAGES}-page limit.')

    # Extract metadata
    meta = doc.metadata or {}
    metadata = {
        'title': meta.get('title', '') or '',
        'author': meta.get('author', '') or '',
        'subject': meta.get('subject', '') or '',
    }

    # Extract text from all pages
    text_parts = []
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        page_text = page.get_text('text')
        if page_text.strip():
            text_parts.append(page_text)

    full_text = '\n\n'.join(text_parts)

    # Extract images (up to MAX_IMAGES)
    images = []
    for page_num in range(doc.page_count):
        if len(images) >= MAX_IMAGES:
            break
        page = doc.load_page(page_num)
        image_list = page.get_images(full=True)
        for img_info in image_list:
            if len(images) >= MAX_IMAGES:
                break
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image or not base_image.get('image'):
                    continue
                # Skip tiny images (likely icons/bullets)
                w = base_image.get('width', 0)
                h = base_image.get('height', 0)
                if w < 50 or h < 50:
                    continue
                images.append({
                    'page': page_num + 1,
                    'data': base_image['image'],
                    'ext': base_image.get('ext', 'png'),
                    'width': w,
                    'height': h,
                })
            except Exception:
                logger.debug('Failed to extract image xref=%s from %s', xref, filename)
                continue

    doc.close()

    return {
        'filename': filename,
        'page_count': doc.page_count if hasattr(doc, 'page_count') else len(text_parts),
        'text': full_text,
        'images': images,
        'metadata': metadata,
    }


def save_pdf_images(conversation_id, images):
    """
    Save extracted PDF images to temp directory for later use.

    Args:
        conversation_id: UUID of the conversation (used as directory name).
        images: List of image dicts from extract_pdf().

    Returns:
        List of saved image metadata (without raw bytes).
    """
    temp_dir = os.path.join('media', 'pdf_temp', str(conversation_id))
    os.makedirs(temp_dir, exist_ok=True)

    saved = []
    for i, img in enumerate(images):
        ext = img.get('ext', 'png')
        filepath = os.path.join(temp_dir, f'image_{i}.{ext}')
        with open(filepath, 'wb') as f:
            f.write(img['data'])
        saved.append({
            'index': i,
            'page': img['page'],
            'ext': ext,
            'width': img['width'],
            'height': img['height'],
            'path': filepath,
        })

    return saved


def get_pdf_image(conversation_id, index):
    """
    Retrieve a previously saved PDF image by index.

    Args:
        conversation_id: UUID of the conversation.
        index: Image index (0-based).

    Returns:
        (image_bytes, extension) or (None, None) if not found.
    """
    temp_dir = os.path.join('media', 'pdf_temp', str(conversation_id))
    if not os.path.isdir(temp_dir):
        return None, None

    # Find the file matching this index (any extension)
    prefix = f'image_{index}.'
    for fname in os.listdir(temp_dir):
        if fname.startswith(prefix):
            filepath = os.path.join(temp_dir, fname)
            ext = fname.rsplit('.', 1)[-1]
            with open(filepath, 'rb') as f:
                return f.read(), ext

    return None, None


def cleanup_pdf_temp(conversation_id):
    """Remove temp directory for a conversation's PDF images."""
    temp_dir = os.path.join('media', 'pdf_temp', str(conversation_id))
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
