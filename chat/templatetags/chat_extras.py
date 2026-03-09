import json

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''


@register.filter
def json_dumps(value):
    """Serialize a value to JSON for use in data attributes."""
    return json.dumps(value)


@register.filter
def dict_items(d):
    """Return dict.items() — avoids Django template resolving .items as a dict key lookup."""
    if isinstance(d, dict):
        return d.items()
    return []
