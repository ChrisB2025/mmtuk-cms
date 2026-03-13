"""
Read, search, and list content from the Django database.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db.models import Q

from .field_mapping import (
    MODEL_MAP, get_model_class, get_title_field, instance_to_frontmatter,
)

logger = logging.getLogger(__name__)

# Human-readable names for content types
CONTENT_TYPE_NAMES = {
    'article': 'Article',
    'briefing': 'Briefing',
    'news': 'News',
    'bio': 'Bio',
    'ecosystem': 'Ecosystem Entry',
    'local_event': 'Local Event',
    'local_news': 'Local News',
    'local_group': 'Local Group',
}


def _instance_to_list_item(content_type, instance):
    """Convert a model instance to the standard list item dict."""
    title_field = get_title_field(content_type)
    title = getattr(instance, title_field, 'Untitled')

    # Get the date for sorting/display
    date_val = (
        getattr(instance, 'pub_date', None)
        or getattr(instance, 'date', None)
    )

    return {
        'content_type': content_type,
        'slug': instance.slug,
        'title': title,
        'frontmatter': instance_to_frontmatter(content_type, instance),
        'file_path': None,
        'modified_date': instance.updated_at,
        'created_at': instance.created_at,
    }


def list_content(content_type=None):
    """
    List all content, optionally filtered by type.
    Returns a list of dicts: [{content_type, slug, title, frontmatter, file_path, modified_date}]
    """
    results = []
    types_to_scan = [content_type] if content_type else list(MODEL_MAP.keys())

    for ct in types_to_scan:
        try:
            Model = get_model_class(ct)
        except ValueError:
            continue

        for instance in Model.objects.all().order_by('-created_at'):
            results.append(_instance_to_list_item(ct, instance))

    return results


def read_content(content_type, slug):
    """
    Read a single content item.
    Returns {frontmatter, body, raw_markdown, file_path} or None if not found.
    """
    try:
        Model = get_model_class(content_type)
    except ValueError:
        return None

    try:
        instance = Model.objects.get(slug=slug)
    except Model.DoesNotExist:
        return None

    return {
        'frontmatter': instance_to_frontmatter(content_type, instance),
        'body': instance.body,
        'raw_markdown': None,
        'file_path': None,
    }


def search_content(query, content_type=None):
    """
    Full-text search across titles, summaries, and body text.
    Returns a list of matching items (same shape as list_content results).
    """
    if not query or not query.strip():
        return []

    query = query.strip()
    results = []
    types_to_scan = [content_type] if content_type else list(MODEL_MAP.keys())

    for ct in types_to_scan:
        try:
            Model = get_model_class(ct)
        except ValueError:
            continue

        title_field = get_title_field(ct)

        # Build Q filter for searchable fields
        q = Q(**{f'{title_field}__icontains': query})
        q |= Q(slug__icontains=query)
        q |= Q(body__icontains=query)

        # Add type-specific search fields
        if hasattr(Model, 'summary'):
            q |= Q(summary__icontains=query)
        if hasattr(Model, 'author'):
            q |= Q(author__icontains=query)
        if hasattr(Model, 'category'):
            q |= Q(category__icontains=query)
        if hasattr(Model, 'text'):
            q |= Q(text__icontains=query)
        if hasattr(Model, 'description'):
            q |= Q(description__icontains=query)

        for instance in Model.objects.filter(q):
            results.append(_instance_to_list_item(ct, instance))

    return results


def get_content_stats():
    """
    Get aggregate statistics about site content.
    Returns {total, by_type: {type: {count, name, recent_title, recent_date, draft_count}}}
    """
    stats = {
        'total': 0,
        'by_type': {},
    }

    for ct, Model in MODEL_MAP.items():
        count = Model.objects.count()
        if count == 0:
            continue

        stats['total'] += count

        # Find most recent item
        title_field = get_title_field(ct)
        date_field = 'pub_date' if hasattr(Model, 'pub_date') else 'date'

        try:
            recent = Model.objects.order_by(f'-{date_field}').first()
        except Exception:
            recent = Model.objects.first()

        recent_title = getattr(recent, title_field, None) if recent else None
        recent_date = getattr(recent, date_field, None) if recent else None
        if recent_date:
            recent_date = recent_date.isoformat()

        # Count drafts
        draft_count = Model.objects.filter(status='draft').count()
        # For briefings, also count the 'draft' boolean flag
        if ct == 'briefing':
            draft_count += Model.objects.filter(draft=True, status='published').count()

        stats['by_type'][ct] = {
            'count': count,
            'name': CONTENT_TYPE_NAMES.get(ct, ct),
            'recent_title': recent_title,
            'recent_date': recent_date,
            'draft_count': draft_count,
        }

    return stats


def check_slug_exists(content_type, slug):
    """Check if a content item with this slug already exists."""
    try:
        Model = get_model_class(content_type)
    except ValueError:
        return False
    return Model.objects.filter(slug=slug).exists()


def list_images(directory=None):
    """
    Scan image directories for image files.
    Checks both MEDIA_ROOT/images/ and content/static/content/images/.
    Returns [{path, web_path, filename, size, modified_date}]
    """
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.avif', '.svg', '.gif', '.heic'}
    results = []

    # Scan directories
    scan_dirs = []

    # Media directory (CMS uploads)
    media_images = Path(settings.MEDIA_ROOT) / 'images'
    if directory:
        media_images = media_images / directory
    if media_images.exists():
        scan_dirs.append(('media', media_images, Path(settings.MEDIA_ROOT)))

    # Static directory (Phase 1/2 imported images)
    static_images = Path(settings.BASE_DIR) / 'content' / 'static' / 'content' / 'images'
    if directory:
        static_images = static_images / directory
    if static_images.exists():
        scan_dirs.append(('static', static_images, Path(settings.BASE_DIR) / 'content' / 'static' / 'content'))

    for source, base_dir, root_dir in scan_dirs:
        for f in sorted(base_dir.rglob('*')):
            if not f.is_file():
                continue
            if f.suffix.lower() not in image_extensions:
                continue

            results.append({
                'path': str(f.relative_to(root_dir)).replace('\\', '/'),
                'web_path': '/' + str(f.relative_to(base_dir.parent)).replace('\\', '/') if base_dir.name != 'images' else f'/images/{f.relative_to(base_dir)}'.replace('\\', '/'),
                'filename': f.name,
                'size': f.stat().st_size,
                'modified_date': datetime.fromtimestamp(os.path.getmtime(str(f))),
            })

    return results
