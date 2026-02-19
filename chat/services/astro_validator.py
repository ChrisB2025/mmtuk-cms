"""
Astro Schema Validator Service

Validates content frontmatter against Astro's Zod schemas (converted to JSON Schema).
This prevents content that passes CMS validation but fails Astro's build from being committed.

Schemas are fetched from the deployed MMTUK site or local repo and cached in memory.
"""

import logging
import json
import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import requests
from jsonschema import validate, ValidationError, Draft7Validator
from django.conf import settings
from django.core.cache import cache

from .validation_helpers import (
    validate_date_format,
    validate_slug_format,
    validate_url_format,
    validate_enum_value,
    ValidationResult
)

logger = logging.getLogger(__name__)

# Cache key and TTL
SCHEMA_CACHE_KEY = 'astro_schemas'
SCHEMA_CACHE_TTL = 86400  # 24 hours

# Schema source URLs (try in order)
SCHEMA_SOURCES = [
    # 1. Local repo (fast, always available if clone exists)
    'file://{repo_path}/public/schemas/',
    # 2. Deployed site (fallback if local repo unavailable)
    'https://mmtuk.org/schemas/',
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
            response = requests.get(url, timeout=3)
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


def _format_validation_error(error: ValidationError, frontmatter: dict, content_type: str) -> str:
    """
    Format a JSON Schema validation error with helpful context and fix suggestions.

    Args:
        error: ValidationError from jsonschema
        frontmatter: The frontmatter being validated
        content_type: Content type being validated

    Returns:
        Formatted error message with field path, actual vs expected, and fix suggestions
    """
    field_path = '.'.join(str(p) for p in error.path) if error.path else 'root'

    # Get actual value if possible
    actual_value = frontmatter
    for part in error.path:
        if isinstance(actual_value, dict):
            actual_value = actual_value.get(part, '<missing>')
        else:
            actual_value = '<not accessible>'
            break

    # Base error message
    parts = [f"**{field_path}**: {error.message}"]

    # Add actual value (truncate if too long)
    if actual_value != '<missing>':
        value_str = repr(actual_value)
        if len(value_str) > 100:
            value_str = value_str[:97] + '...'
        parts.append(f"  Actual value: {value_str}")

    # Add expected format/value from schema
    if error.validator == 'type':
        expected_type = error.validator_value
        parts.append(f"  Expected type: {expected_type}")

    elif error.validator == 'enum':
        allowed_values = error.validator_value
        parts.append(f"  Allowed values: {', '.join(repr(v) for v in allowed_values)}")

        # Suggest close match
        if isinstance(actual_value, str):
            for allowed in allowed_values:
                if isinstance(allowed, str) and allowed.lower() == actual_value.lower():
                    parts.append(f"  💡 Did you mean '{allowed}'? (check capitalization)")
                    break

    elif error.validator == 'required':
        parts.append(f"  💡 This field is required and cannot be empty")

    elif error.validator == 'format':
        parts.append(f"  Expected format: {error.validator_value}")

    # Add fix suggestions based on field name
    field_name = error.path[-1] if error.path else None
    if field_name:
        if 'date' in field_name.lower() or field_name in ('pubDate', 'sourceDate'):
            parts.append("  💡 Use ISO 8601 format: '2026-02-16' or '2026-02-16T10:00:00.000Z'")

        elif field_name == 'slug':
            parts.append("  💡 Use lowercase-with-hyphens format (e.g., 'my-article-slug')")

        elif 'url' in field_name.lower() or 'link' in field_name.lower():
            parts.append("  💡 Use full URL (https://example.com) or relative path (/path)")

    return '\n'.join(parts)


def _get_schema_info(schema: dict, field_path: List[str]) -> dict:
    """
    Extract schema information for a specific field path.

    Args:
        schema: JSON Schema dict
        field_path: Path to field (e.g., ['properties', 'title'])

    Returns:
        Dict with type, enum, format, etc. for the field
    """
    current = schema
    for part in field_path:
        if isinstance(current, dict):
            current = current.get(part, {})
        else:
            return {}
    return current if isinstance(current, dict) else {}


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
            # Format validation errors for user with detailed context
            error_messages = []
            for i, error in enumerate(errors[:5]):  # Show first 5 errors
                formatted = _format_validation_error(error, prepared, content_type)
                error_messages.append(formatted)

            # Build comprehensive error message
            error_count = len(errors)
            if error_count == 1:
                error_header = "❌ Validation Error:\n"
            else:
                error_header = f"❌ {error_count} Validation Errors:\n"

            error_body = '\n\n'.join(error_messages)

            if error_count > 5:
                error_body += f"\n\n... and {error_count - 5} more errors"

            full_error = error_header + error_body

            # Log summary for debugging
            error_summary = '; '.join(str(e.message) for e in errors[:3])
            if error_count > 3:
                error_summary += f' (and {error_count - 3} more)'
            logger.warning('Astro schema validation failed for %s: %s', content_type, error_summary)

            # Track metrics
            track_validation_result(content_type, is_valid=False, error_count=error_count)

            return (False, full_error)

        logger.debug('Astro schema validation passed for %s', content_type)

        # Track metrics
        track_validation_result(content_type, is_valid=True)

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


# Validation metrics tracking
METRICS_CACHE_KEY = 'astro_validation_metrics'
METRICS_CACHE_TTL = 3600  # 1 hour


def track_validation_result(content_type: str, is_valid: bool, error_count: int = 0):
    """
    Track validation metrics for monitoring and debugging.

    Args:
        content_type: Type of content validated
        is_valid: Whether validation passed
        error_count: Number of validation errors (if any)
    """
    try:
        metrics = cache.get(METRICS_CACHE_KEY, {})

        # Initialize metrics for content type if needed
        if content_type not in metrics:
            metrics[content_type] = {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'total_errors': 0,
            }

        # Update metrics
        metrics[content_type]['total'] += 1
        if is_valid:
            metrics[content_type]['passed'] += 1
        else:
            metrics[content_type]['failed'] += 1
            metrics[content_type]['total_errors'] += error_count

        # Save back to cache
        cache.set(METRICS_CACHE_KEY, metrics, METRICS_CACHE_TTL)

        # Log periodically (every 10th validation)
        if metrics[content_type]['total'] % 10 == 0:
            logger.info(
                'Validation metrics for %s: %d total, %d passed (%.1f%%), %d failed',
                content_type,
                metrics[content_type]['total'],
                metrics[content_type]['passed'],
                100.0 * metrics[content_type]['passed'] / metrics[content_type]['total'],
                metrics[content_type]['failed']
            )

    except Exception as e:
        # Don't let metrics tracking break validation
        logger.debug('Failed to track validation metrics: %s', e)


def get_validation_metrics() -> Dict[str, dict]:
    """
    Get current validation metrics.

    Returns:
        Dict mapping content type to metrics (total, passed, failed, total_errors)
    """
    return cache.get(METRICS_CACHE_KEY, {})


def reset_validation_metrics():
    """Reset validation metrics."""
    cache.delete(METRICS_CACHE_KEY)
    logger.info('Reset validation metrics')


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
