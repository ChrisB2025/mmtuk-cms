"""
Astro Schema Validator Service

Validates content frontmatter against Astro's Zod schemas (converted to JSON Schema).
This prevents content that passes CMS validation but fails Astro's build from being committed.

Schemas are fetched from the deployed MMTUK site or local repo and cached in memory.
"""

import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from jsonschema import validate, ValidationError, Draft7Validator
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache key and TTL
SCHEMA_CACHE_KEY = 'astro_schemas'
SCHEMA_CACHE_TTL = 86400  # 24 hours

# Schema source URLs (try in order)
SCHEMA_SOURCES = [
    # 1. Deployed site (production)
    'https://mmtuk.org/schemas/',
    # 2. Local repo (for development)
    'file://{repo_path}/public/schemas/',
]


def _get_schema_path(content_type: str) -> str:
    """Get the filename for a content type's schema."""
    # Map CMS content types to Astro collection names
    type_mapping = {
        'article': 'articles',
        'news': 'news',
        'bio': 'bios',
        'ecosystem': 'ecosystem',
        'localNews': 'localNews',
        'localGroup': 'localGroups',
        'localEvent': 'localEvents',
        'briefing': 'briefings',
    }
    collection_name = type_mapping.get(content_type, content_type)
    return f'{collection_name}.json'


def _fetch_schema_from_url(url: str) -> Optional[dict]:
    """Fetch a single schema file from a URL or file path."""
    try:
        if url.startswith('file://'):
            # Read from local file
            file_path = url.replace('file://', '')
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Fetch from HTTP/HTTPS
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.debug('Failed to fetch schema from %s: %s', url, e)
        return None


def fetch_schemas() -> Dict[str, dict]:
    """
    Fetch all content collection schemas from available sources.

    Tries sources in order:
    1. Deployed site (https://mmtuk.org/schemas/)
    2. Local repo (file://[REPO_CLONE_DIR]/public/schemas/)

    Returns:
        Dict mapping content type to JSON schema dict

    Raises:
        Exception: If no schemas could be fetched from any source
    """
    # Try cache first
    cached = cache.get(SCHEMA_CACHE_KEY)
    if cached:
        logger.debug('Using cached Astro schemas')
        return cached

    schemas = {}
    content_types = ['article', 'news', 'bio', 'ecosystem', 'localNews', 'localGroup', 'localEvent', 'briefing']

    # Prepare sources (replace placeholder for local repo)
    sources = []
    for source_template in SCHEMA_SOURCES:
        if '{repo_path}' in source_template:
            repo_path = Path(settings.REPO_CLONE_DIR) if hasattr(settings, 'REPO_CLONE_DIR') else None
            if repo_path and repo_path.exists():
                sources.append(source_template.format(repo_path=str(repo_path).replace('\\', '/')))
        else:
            sources.append(source_template)

    # Try each source until we get all schemas
    for source_base in sources:
        logger.info('Attempting to fetch schemas from: %s', source_base)
        temp_schemas = {}

        for content_type in content_types:
            schema_file = _get_schema_path(content_type)
            schema_url = source_base + schema_file

            schema = _fetch_schema_from_url(schema_url)
            if schema:
                temp_schemas[content_type] = schema
                logger.debug('Fetched schema for %s', content_type)

        # If we got all schemas from this source, use them
        if len(temp_schemas) == len(content_types):
            schemas = temp_schemas
            logger.info('Successfully fetched all %d schemas from %s', len(schemas), source_base)
            break

    if not schemas:
        raise Exception('Failed to fetch Astro schemas from any source. Schema validation disabled.')

    # Cache for 24 hours
    cache.set(SCHEMA_CACHE_KEY, schemas, SCHEMA_CACHE_TTL)

    return schemas


def validate_against_astro_schema(content_type: str, frontmatter: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate frontmatter against the Astro Zod schema (as JSON Schema).

    Args:
        content_type: CMS content type (article, news, bio, etc.)
        frontmatter: Dictionary of frontmatter fields to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if validation passes
        - (False, error_message) if validation fails

    Edge cases:
    - Date fields: Converts Python date/datetime to ISO 8601 string for validation
    - Null vs undefined: JSON Schema allows null where Zod uses .optional()
    - Missing schemas: Falls back to permissive mode (logs warning, returns valid)
    """
    try:
        # Fetch schemas (uses cache if available)
        schemas = fetch_schemas()

        if content_type not in schemas:
            logger.warning('No Astro schema found for content type: %s. Skipping validation.', content_type)
            return (True, None)

        schema = schemas[content_type]

        # Prepare frontmatter for validation
        # Convert datetime objects to ISO 8601 strings
        prepared = {}
        for key, value in frontmatter.items():
            if isinstance(value, (datetime.date, datetime)):
                prepared[key] = value.isoformat()
            else:
                prepared[key] = value

        # Validate using jsonschema
        # Note: Draft7Validator is used because zod-to-json-schema outputs Draft 7
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(prepared))

        if errors:
            # Format validation errors for user
            error_messages = []
            for error in errors:
                field_path = '.'.join(str(p) for p in error.path) if error.path else 'root'
                error_messages.append(f"Field '{field_path}': {error.message}")

            error_summary = '; '.join(error_messages[:3])  # Show first 3 errors
            if len(error_messages) > 3:
                error_summary += f' (and {len(error_messages) - 3} more errors)'

            logger.warning('Astro schema validation failed for %s: %s', content_type, error_summary)
            return (False, f'Content does not match Astro schema: {error_summary}')

        logger.debug('Astro schema validation passed for %s', content_type)
        return (True, None)

    except Exception as e:
        # If schema validation system fails, log error but don't block content
        logger.exception('Astro schema validator error for %s: %s', content_type, e)
        # Fail open: allow content through if validator itself is broken
        return (True, None)


def invalidate_schema_cache():
    """Force re-fetch of schemas on next validation."""
    cache.delete(SCHEMA_CACHE_KEY)
    logger.info('Invalidated Astro schema cache')


# Convenience function for use in management commands
def prefetch_schemas():
    """
    Prefetch and cache schemas.
    Useful for warming cache on deployment or testing schema availability.
    """
    try:
        schemas = fetch_schemas()
        logger.info('Prefetched %d Astro schemas', len(schemas))
        return True
    except Exception as e:
        logger.error('Failed to prefetch schemas: %s', e)
        return False
