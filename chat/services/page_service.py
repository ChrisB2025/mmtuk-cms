"""
Read/write/patch page JSON data files.

Pages are stored as JSON files in content/data/pages/{key}.json.
"""
import json
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_PAGES_DIR = Path(settings.BASE_DIR) / 'content' / 'data' / 'pages'


def read_page_data(page_key: str) -> dict:
    """Read a page's JSON data. Returns {} if not found."""
    path = _PAGES_DIR / f'{page_key}.json'
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        logger.error("Malformed JSON for page %s", page_key)
        return {}


def write_page_data(page_key: str, data: dict) -> None:
    """Write a full page JSON data object."""
    path = _PAGES_DIR / f'{page_key}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def apply_page_patch(page_key: str, patch: dict) -> dict:
    """Deep-merge patch into existing page data and write. Returns updated data."""
    current = read_page_data(page_key)
    updated = _deep_merge(current, patch)
    write_page_data(page_key, updated)
    return updated


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge patch into base. Arrays are always replaced (not merged)."""
    result = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def read_manifest() -> dict:
    """Read manifest.json listing all managed pages. Returns {"pages": []} on error."""
    path = _PAGES_DIR / 'manifest.json'
    if not path.exists():
        return {"pages": []}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        logger.error("Malformed manifest.json")
        return {"pages": []}
