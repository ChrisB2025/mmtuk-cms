"""
Markdown file generation and file path resolution for MMTUK content.
"""

import logging

from content_schema.schemas import (
    CONTENT_TYPES,
    validate_frontmatter,
    apply_defaults,
    format_date,
)

logger = logging.getLogger(__name__)


def get_file_path(content_type, slug):
    """Get the relative file path within the repo for a content item."""
    schema = CONTENT_TYPES.get(content_type)
    if not schema:
        raise ValueError(f'Unknown content type: {content_type}')

    filename = schema['filename_pattern'].format(slug=slug)
    return schema['directory'] + filename


def get_image_path(content_type, slug, extension='png'):
    """Get the relative image path within the repo's public/images/ dir."""
    if content_type == 'bio':
        return f'public/images/bios/{slug}.{extension}'
    if content_type == 'briefing':
        return f'public/images/briefings/{slug}-thumbnail.{extension}'
    return f'public/images/{slug}.{extension}'


def _yaml_value(value):
    """Format a Python value for YAML frontmatter."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        # YAML array format
        items = ', '.join(f'"{v}"' for v in value)
        return f'[{items}]'
    if isinstance(value, str):
        # Quote strings that contain special YAML characters
        if any(c in value for c in (':', '#', '{', '}', '[', ']', ',', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '`')):
            escaped = value.replace('"', '\\"')
            return f'"{escaped}"'
        if value.lower() in ('true', 'false', 'yes', 'no', 'null', 'on', 'off'):
            return f'"{value}"'
        return value
    return str(value)


def generate_markdown(content_type, frontmatter, body=''):
    """
    Validate frontmatter, apply defaults, and generate a complete markdown file.
    Returns (markdown_string, errors_list).
    """
    schema = CONTENT_TYPES.get(content_type)
    if not schema:
        return None, [f'Unknown content type: {content_type}']

    # Apply defaults
    frontmatter = apply_defaults(content_type, frontmatter)

    # Validate
    is_valid, errors = validate_frontmatter(content_type, frontmatter)
    if not is_valid:
        return None, errors

    # Build YAML frontmatter
    lines = ['---']
    # Emit fields in schema order for consistency
    for field_name in schema['fields']:
        if field_name in frontmatter and frontmatter[field_name] is not None:
            value = frontmatter[field_name]
            # Format dates
            if schema['fields'][field_name]['type'] in ('date', 'datetime'):
                value = format_date(value)
            lines.append(f'{field_name}: {_yaml_value(value)}')
    lines.append('---')
    lines.append('')

    if body:
        lines.append(body)
        if not body.endswith('\n'):
            lines.append('')

    return '\n'.join(lines), []
