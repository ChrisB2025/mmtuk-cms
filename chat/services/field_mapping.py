"""
Map between camelCase frontmatter keys (used in CMS chat action blocks)
and snake_case Django model field names.
"""

import logging
import re
from datetime import date, datetime

from content.models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)

logger = logging.getLogger(__name__)

# camelCase (Claude action blocks) → snake_case (Django model fields)
FIELD_MAP = {
    'pubDate': 'pub_date',
    'readTime': 'read_time',
    'mainImage': 'main_image',
    'authorTitle': 'author_title',
    'sourceUrl': 'source_url',
    'sourceTitle': 'source_title',
    'sourceAuthor': 'source_author',
    'sourcePublication': 'source_publication',
    'sourceDate': 'source_date',
    'localGroup': 'local_group',
    'endDate': 'end_date',
    'partnerEvent': 'partner_event',
    'headerImage': 'header_image',
    'leaderName': 'leader_name',
    'leaderIntro': 'leader_intro',
    'discordLink': 'discord_link',
    'advisoryBoard': 'advisory_board',
    'activityStatus': 'activity_status',
    'headerVideo': 'header_video',
    'registrationLink': 'registration_link',
}

REVERSE_FIELD_MAP = {v: k for k, v in FIELD_MAP.items()}

# Content type string → Django model class
MODEL_MAP = {
    'article': Article,
    'briefing': Briefing,
    'news': News,
    'bio': Bio,
    'ecosystem': EcosystemEntry,
    'local_event': LocalEvent,
    'local_news': LocalNews,
    'local_group': LocalGroup,
}

# Which field holds the "title" for each content type
TITLE_FIELD_MAP = {
    'local_news': 'heading',
    'bio': 'name',
    'ecosystem': 'name',
}

# Fields that are ForeignKey references (value is a slug string)
FK_FIELDS = {
    'local_group': LocalGroup,
}

# Fields that need date parsing
DATE_FIELDS = {
    'pub_date', 'date', 'end_date', 'source_date',
}


def get_model_class(content_type):
    """Get the Django model class for a content type string."""
    model = MODEL_MAP.get(content_type)
    if not model:
        raise ValueError(f'Unknown content type: {content_type}')
    return model


def get_title_field(content_type):
    """Get the title field name for a content type."""
    return TITLE_FIELD_MAP.get(content_type, 'title')


def get_title(content_type, instance):
    """Get the title value from a model instance."""
    return getattr(instance, get_title_field(content_type), '')


def _parse_date(value):
    """Parse a date string into a date object. Handles ISO format strings."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        # Strip time component if present (e.g. "2024-01-15T00:00:00.000Z")
        value = value.strip()
        if 'T' in value:
            value = value.split('T')[0]
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            pass
    return value


def _resolve_fk(field_name, value):
    """Resolve a FK field from a slug string to a model instance."""
    model = FK_FIELDS.get(field_name)
    if not model:
        return value
    if value is None or value == '':
        return None
    # Already a model instance
    if isinstance(value, model):
        return value
    # Look up by slug
    try:
        return model.objects.get(slug=value)
    except model.DoesNotExist:
        raise ValueError(f'{field_name}: no {model.__name__} with slug "{value}"')


def camel_to_snake(frontmatter):
    """
    Convert a camelCase frontmatter dict to snake_case Django model fields.
    Also resolves FK references and parses date strings.
    """
    result = {}
    for key, value in frontmatter.items():
        # Map key
        snake_key = FIELD_MAP.get(key, key)

        # Skip None/empty optional values
        if value is None or value == '' or value == 'None':
            continue

        # Strip whitespace from strings
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue

        # Resolve FK fields
        if snake_key in FK_FIELDS:
            value = _resolve_fk(snake_key, value)

        # Parse date fields
        if snake_key in DATE_FIELDS:
            value = _parse_date(value)

        result[snake_key] = value

    return result


def snake_to_camel(fields):
    """
    Convert a snake_case dict to camelCase for Claude-facing display.
    Also converts FK instances back to slug strings and dates to ISO strings.
    """
    result = {}
    for key, value in fields.items():
        # Skip internal Django fields
        if key in ('id', 'created_at', 'updated_at', 'status'):
            continue

        # Map key
        camel_key = REVERSE_FIELD_MAP.get(key, key)

        # Convert FK instances to slug strings
        if isinstance(value, LocalGroup):
            value = value.slug

        # Convert dates to ISO strings
        if isinstance(value, date):
            value = value.strftime('%Y-%m-%dT00:00:00.000Z')
        if isinstance(value, datetime):
            value = value.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        result[camel_key] = value

    return result


def instance_to_frontmatter(content_type, instance):
    """
    Convert a model instance to a camelCase frontmatter dict
    (matching what Claude expects in action blocks).
    """
    model = get_model_class(content_type)
    fields = {}
    for field in model._meta.get_fields():
        if not hasattr(field, 'column'):
            continue  # skip reverse relations
        name = field.name
        if name in ('id', 'created_at', 'updated_at'):
            continue
        value = getattr(instance, name)
        # For FK fields, get the related instance
        if name.endswith('_id') and name[:-3] in FK_FIELDS:
            continue  # skip raw FK id, we'll get the object
        fields[name] = value

    return snake_to_camel(fields)


def generate_slug(title):
    """Generate a URL-safe slug from a title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def auto_layout(category):
    """Determine article layout from category."""
    if category in ('Core Ideas', 'Core Insights'):
        return 'simplified'
    if category == 'But what about...?':
        return 'rebuttal'
    return 'default'
