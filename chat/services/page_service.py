"""
Read/write/patch page JSON data files in the Astro repo.

Pages are stored as JSON files in src/data/pages/{key}.json.
The manifest (manifest.json) lists all managed pages.
"""
import json
import logging

from .git_service import read_file_from_repo, write_file_to_repo

logger = logging.getLogger(__name__)

_PAGES_DIR = "src/data/pages"


def read_page_data(page_key: str) -> dict:
    """Read a page's JSON data from the repo. Returns {} if not found."""
    path = f"{_PAGES_DIR}/{page_key}.json"
    raw = read_file_from_repo(path)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Malformed JSON for page %s", page_key)
        return {}


def write_page_data(page_key: str, data: dict) -> None:
    """Write a full page JSON data object to the repo."""
    path = f"{_PAGES_DIR}/{page_key}.json"
    content = json.dumps(data, indent=2, ensure_ascii=False)
    write_file_to_repo(path, content.encode("utf-8"))


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
    raw = read_file_from_repo(f"{_PAGES_DIR}/manifest.json")
    if not raw:
        return {"pages": []}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Malformed manifest.json")
        return {"pages": []}
