"""
Read, search, and list existing content from the MMTUK Astro repo.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import yaml
from django.conf import settings
from django.core.cache import cache

from content_schema.schemas import CONTENT_TYPES
from .git_service import ensure_repo, read_file_from_repo, list_files_in_directory

logger = logging.getLogger(__name__)

CACHE_TTL = 60  # seconds
CACHE_KEY_PREFIX = 'content_reader'


def _cache_key(name, *args):
    parts = [CACHE_KEY_PREFIX, name] + [str(a) for a in args if a]
    return ':'.join(parts)


def invalidate_cache():
    """Invalidate all content reader cache entries."""
    # LocMemCache doesn't support wildcard delete, so we clear the whole cache.
    # This is acceptable because the cache is only used for content reader data
    # and rate limiting (which has its own TTL and recovers quickly).
    cache.clear()


def _ensure_repo_available():
    """Ensure the repo is cloned and up to date. In DEBUG mode, also checks output dir."""
    try:
        ensure_repo()
    except Exception:
        logger.warning('Could not ensure repo; will try to read from existing clone or output dir')


def _get_content_dir(content_type):
    """Get the repo directory for a content type."""
    schema = CONTENT_TYPES.get(content_type)
    if not schema:
        return None
    return schema['directory']


def _parse_frontmatter(raw_text):
    """
    Parse YAML frontmatter from a markdown file.
    Returns (frontmatter_dict, body_text) or (None, raw_text) if no frontmatter found.
    """
    if not raw_text or not raw_text.startswith('---'):
        return None, raw_text

    # Find the closing ---
    end_idx = raw_text.find('---', 3)
    if end_idx == -1:
        return None, raw_text

    yaml_str = raw_text[3:end_idx].strip()
    body = raw_text[end_idx + 3:].strip()

    try:
        frontmatter = yaml.safe_load(yaml_str)
        if not isinstance(frontmatter, dict):
            return None, raw_text
        return frontmatter, body
    except yaml.YAMLError:
        logger.warning('Failed to parse YAML frontmatter')
        return None, raw_text


def _get_title_from_frontmatter(frontmatter, content_type):
    """Extract the display title from frontmatter based on content type."""
    if not frontmatter:
        return 'Untitled'
    # Different content types use different title fields
    return (
        frontmatter.get('title')
        or frontmatter.get('heading')  # local_news uses 'heading'
        or frontmatter.get('name')  # bio and ecosystem use 'name'
        or 'Untitled'
    )


def _file_modified_date(relative_path):
    """Get the modification date of a file in the repo clone."""
    clone_dir = Path(settings.REPO_CLONE_DIR)
    full_path = clone_dir / relative_path
    if full_path.exists():
        ts = os.path.getmtime(str(full_path))
        return datetime.fromtimestamp(ts)
    return None


def list_content(content_type=None):
    """
    List all content files, optionally filtered by type.
    Returns a list of dicts: [{content_type, slug, title, frontmatter, file_path, modified_date}]
    """
    cache_k = _cache_key('list', content_type or 'all')
    cached = cache.get(cache_k)
    if cached is not None:
        return cached

    _ensure_repo_available()

    results = []
    types_to_scan = [content_type] if content_type else list(CONTENT_TYPES.keys())

    for ct in types_to_scan:
        directory = _get_content_dir(ct)
        if not directory:
            continue

        files = list_files_in_directory(directory)
        for file_path in files:
            raw = read_file_from_repo(file_path)
            if raw is None:
                continue

            frontmatter, body = _parse_frontmatter(raw)
            slug = frontmatter.get('slug', '') if frontmatter else ''
            if not slug:
                # Derive slug from filename
                slug = Path(file_path).stem

            title = _get_title_from_frontmatter(frontmatter, ct)
            modified = _file_modified_date(file_path)

            results.append({
                'content_type': ct,
                'slug': slug,
                'title': title,
                'frontmatter': frontmatter or {},
                'file_path': file_path,
                'modified_date': modified,
            })

    cache.set(cache_k, results, CACHE_TTL)
    return results


def _find_file_path_by_slug(content_type, slug):
    """
    Find the actual file path for a content item by its frontmatter slug.
    Handles cases where the filename doesn't match the slug.
    Returns the file_path string or None.
    """
    # First try direct path (fast path for when filename == slug)
    schema = CONTENT_TYPES.get(content_type)
    if not schema:
        return None

    direct_path = schema['directory'] + schema['filename_pattern'].format(slug=slug)
    raw = read_file_from_repo(direct_path)
    if raw is not None:
        return direct_path

    # Fallback: scan directory and match by frontmatter slug
    all_items = list_content(content_type)
    for item in all_items:
        if item['slug'] == slug:
            return item['file_path']

    return None


def read_content(content_type, slug):
    """
    Read a single content file.
    Returns {frontmatter, body, raw_markdown, file_path} or None if not found.
    """
    cache_k = _cache_key('read', content_type, slug)
    cached = cache.get(cache_k)
    if cached is not None:
        return cached

    _ensure_repo_available()

    file_path = _find_file_path_by_slug(content_type, slug)
    if not file_path:
        return None

    raw = read_file_from_repo(file_path)
    if raw is None:
        return None

    frontmatter, body = _parse_frontmatter(raw)

    result = {
        'frontmatter': frontmatter or {},
        'body': body,
        'raw_markdown': raw,
        'file_path': file_path,
    }

    cache.set(cache_k, result, CACHE_TTL)
    return result


def search_content(query, content_type=None):
    """
    Full-text search across titles, summaries, and body text.
    Returns a list of matching items (same shape as list_content results).
    """
    if not query or not query.strip():
        return []

    query_lower = query.lower().strip()
    all_content = list_content(content_type)

    matches = []
    for item in all_content:
        fm = item.get('frontmatter', {})
        searchable = ' '.join([
            str(item.get('title', '')),
            str(fm.get('summary', '')),
            str(fm.get('description', '')),
            str(fm.get('text', '')),  # local_news text field
            str(fm.get('author', '')),
            str(fm.get('category', '')),
            str(item.get('slug', '')),
        ]).lower()

        if query_lower in searchable:
            matches.append(item)

    return matches


def get_content_stats():
    """
    Get aggregate statistics about site content.
    Returns {total, by_type: {type: {count, recent_title, recent_date, draft_count}}}
    """
    cache_k = _cache_key('stats')
    cached = cache.get(cache_k)
    if cached is not None:
        return cached

    all_content = list_content()

    stats = {
        'total': len(all_content),
        'by_type': {},
    }

    # Group by content type
    by_type = {}
    for item in all_content:
        ct = item['content_type']
        if ct not in by_type:
            by_type[ct] = []
        by_type[ct].append(item)

    for ct, items in by_type.items():
        # Sort by date (most recent first)
        def sort_key(x):
            fm = x.get('frontmatter', {})
            d = fm.get('pubDate') or fm.get('date') or ''
            if isinstance(d, datetime):
                return d.isoformat()
            return str(d)

        items_sorted = sorted(items, key=sort_key, reverse=True)

        # Count drafts (briefings with draft: true)
        draft_count = sum(
            1 for i in items
            if i.get('frontmatter', {}).get('draft') is True
        )

        recent = items_sorted[0] if items_sorted else None
        schema = CONTENT_TYPES.get(ct, {})

        stats['by_type'][ct] = {
            'count': len(items),
            'name': schema.get('name', ct),
            'recent_title': recent['title'] if recent else None,
            'recent_date': sort_key(recent) if recent else None,
            'draft_count': draft_count,
        }

    cache.set(cache_k, stats, CACHE_TTL)
    return stats


def check_slug_exists(content_type, slug):
    """
    Check if a content file with this slug already exists.
    Returns True if it exists, False otherwise.
    """
    return _find_file_path_by_slug(content_type, slug) is not None


def list_images(directory=None):
    """
    Scan public/images/ for image files.
    Returns [{path, filename, size, modified_date}]
    """
    cache_k = _cache_key('images', directory or 'all')
    cached = cache.get(cache_k)
    if cached is not None:
        return cached

    _ensure_repo_available()

    clone_dir = Path(settings.REPO_CLONE_DIR)
    base_dir = clone_dir / 'public' / 'images'

    if directory:
        base_dir = base_dir / directory

    if not base_dir.exists():
        return []

    image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.avif', '.svg', '.gif', '.heic'}
    results = []

    for f in sorted(base_dir.rglob('*')):
        if not f.is_file():
            continue
        if f.suffix.lower() not in image_extensions:
            continue

        rel_path = str(f.relative_to(clone_dir)).replace('\\', '/')
        # Path as used in frontmatter (relative to public/)
        web_path = '/' + str(f.relative_to(clone_dir / 'public')).replace('\\', '/')

        results.append({
            'path': rel_path,
            'web_path': web_path,
            'filename': f.name,
            'size': f.stat().st_size,
            'modified_date': datetime.fromtimestamp(os.path.getmtime(str(f))),
        })

    cache.set(cache_k, results, CACHE_TTL)
    return results
