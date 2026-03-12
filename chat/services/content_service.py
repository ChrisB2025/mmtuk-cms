"""
Content CRUD operations via Django ORM.

Replaces the previous markdown file generation approach.
Content is now stored directly in the database.
"""

import logging
import math
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from .field_mapping import (
    camel_to_snake, get_model_class, get_title_field, auto_layout,
)

logger = logging.getLogger(__name__)


def create_content(content_type, frontmatter, body='', status='published'):
    """
    Create a new content item from camelCase frontmatter dict.

    Returns (instance, errors_list). On failure, instance is None.
    """
    try:
        Model = get_model_class(content_type)
    except ValueError as e:
        return None, [str(e)]

    try:
        fields = camel_to_snake(frontmatter)
    except ValueError as e:
        return None, [str(e)]

    # Set body and status
    fields['body'] = body or ''
    fields['status'] = status

    # Auto-set article layout from category
    if content_type == 'article' and 'category' in fields:
        if 'layout' not in fields or not fields.get('layout'):
            fields['layout'] = auto_layout(fields['category'])

    # Handle ecosystem's activity_status vs status
    # The schema uses 'status' for Active/Inactive/Archived, but Django model
    # uses 'activity_status' (to avoid collision with draft/published 'status')
    # The field_mapping handles this via activityStatus → activity_status

    try:
        instance = Model(**fields)
        instance.full_clean()
        instance.save()
        return instance, []
    except ValidationError as e:
        errors = []
        if hasattr(e, 'message_dict'):
            for field, messages in e.message_dict.items():
                for msg in messages:
                    errors.append(f'{field}: {msg}')
        else:
            errors.append(str(e))
        return None, errors
    except Exception as e:
        logger.exception('Failed to create %s', content_type)
        return None, [str(e)]


def update_content(content_type, slug, frontmatter=None, body=None):
    """
    Update an existing content item. Supports partial updates.

    Returns (instance, errors_list). On failure, instance is None.
    """
    try:
        Model = get_model_class(content_type)
    except ValueError as e:
        return None, [str(e)]

    try:
        instance = Model.objects.get(slug=slug)
    except Model.DoesNotExist:
        return None, [f'{content_type} with slug "{slug}" not found']

    # Apply frontmatter updates
    if frontmatter:
        try:
            fields = camel_to_snake(frontmatter)
        except ValueError as e:
            return None, [str(e)]

        # Auto-set article layout from category if category changed
        if content_type == 'article' and 'category' in fields:
            if 'layout' not in fields:
                fields['layout'] = auto_layout(fields['category'])

        for field_name, value in fields.items():
            setattr(instance, field_name, value)

    # Update body if provided
    if body is not None:
        instance.body = body

    try:
        instance.full_clean()
        instance.save()
        return instance, []
    except ValidationError as e:
        errors = []
        if hasattr(e, 'message_dict'):
            for field, messages in e.message_dict.items():
                for msg in messages:
                    errors.append(f'{field}: {msg}')
        else:
            errors.append(str(e))
        return None, errors
    except Exception as e:
        logger.exception('Failed to update %s/%s', content_type, slug)
        return None, [str(e)]


def delete_content(content_type, slug):
    """
    Delete a content item by type and slug.

    Returns (success: bool, error_message: str or None).
    """
    try:
        Model = get_model_class(content_type)
    except ValueError as e:
        return False, str(e)

    try:
        instance = Model.objects.get(slug=slug)
        instance.delete()
        return True, None
    except Model.DoesNotExist:
        return False, f'{content_type} with slug "{slug}" not found'
    except Exception as e:
        logger.exception('Failed to delete %s/%s', content_type, slug)
        return False, str(e)


def get_image_save_path(content_type, slug, extension='webp'):
    """
    Get the filesystem path for saving a CMS-uploaded image.

    Returns (absolute_path, relative_web_path).
    """
    if content_type == 'bio':
        rel = f'images/bios/{slug}.{extension}'
    elif content_type == 'briefing':
        rel = f'images/briefings/{slug}-thumbnail.{extension}'
    else:
        rel = f'images/{slug}.{extension}'

    abs_path = Path(settings.MEDIA_ROOT) / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    web_path = f'/{rel}'
    return abs_path, web_path


def estimate_read_time(text):
    """Estimate read time in minutes (200 wpm average)."""
    words = len(text.split())
    return max(1, math.ceil(words / 200))
