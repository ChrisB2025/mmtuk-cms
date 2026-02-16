"""
Service for generating Astro redirect configuration from deleted content.

This service queries ContentAuditLog for deleted content entries with redirect_target
and generates an Astro redirects configuration file.
"""

import logging
from pathlib import Path
from typing import Dict, List
from django.conf import settings

from chat.models import ContentAuditLog

logger = logging.getLogger(__name__)


def get_active_redirects() -> Dict[str, str]:
    """
    Get all active redirects from ContentAuditLog.

    Returns:
        Dict mapping source paths to redirect targets
        Example: {'/articles/old-slug': '/articles', '/news/deleted': '/news'}
    """
    # Query deleted content entries with redirect targets
    deleted_entries = ContentAuditLog.objects.filter(
        action='delete',
        deleted_at__isnull=False,
    ).exclude(
        redirect_target=''
    ).order_by('deleted_at')

    redirects = {}
    for entry in deleted_entries:
        source_path = entry.get_source_path()
        redirects[source_path] = entry.redirect_target

    return redirects


def generate_redirects_config() -> str:
    """
    Generate Astro redirects configuration JavaScript code.

    Returns:
        JavaScript code for redirects configuration
    """
    redirects = get_active_redirects()

    if not redirects:
        return """// Auto-generated redirects from MMTUK CMS
// No redirects configured yet

export default {};
"""

    lines = [
        "// Auto-generated redirects from MMTUK CMS",
        "// DO NOT EDIT MANUALLY - Changes will be overwritten on next publish",
        "",
        "export default {",
    ]

    for source, target in redirects.items():
        # Escape single quotes in paths (unlikely but safe)
        source_escaped = source.replace("'", "\\'")
        target_escaped = target.replace("'", "\\'")
        lines.append(f"  '{source_escaped}': '{target_escaped}',")

    lines.append("};")
    lines.append("")  # Trailing newline

    return "\n".join(lines)


def write_redirects_to_repo() -> bool:
    """
    Write generated redirects configuration to MMTUK repo.

    Returns:
        True if successful, False otherwise
    """
    from chat.services.git_service import ensure_repo, write_file_to_repo

    try:
        ensure_repo()

        # Generate redirects config
        config_content = generate_redirects_config()

        # Write to redirects.config.mjs in Astro repo
        redirects_path = 'redirects.config.mjs'

        write_file_to_repo(redirects_path, config_content)

        logger.info(f'Wrote redirects config to {redirects_path}')
        return True

    except Exception as e:
        logger.exception(f'Failed to write redirects config: {e}')
        return False


def get_redirect_summary() -> Dict[str, any]:
    """
    Get summary of redirect configuration for display.

    Returns:
        Dict with redirect stats and list of active redirects
    """
    redirects = get_active_redirects()

    # Group by target
    grouped = {}
    for source, target in redirects.items():
        if target not in grouped:
            grouped[target] = []
        grouped[target].append(source)

    return {
        'total_count': len(redirects),
        'redirects': redirects,
        'grouped': grouped,
    }


def validate_redirect_target(target: str) -> tuple[bool, str]:
    """
    Validate a redirect target URL.

    Args:
        target: URL path to validate (e.g., '/articles' or '/articles/category')

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not target:
        return True, ""  # Empty is valid (intentional 404)

    target = target.strip()

    # Must start with /
    if not target.startswith('/'):
        return False, "Redirect target must start with /"

    # Must not end with / (unless it's just "/")
    if target != '/' and target.endswith('/'):
        return False, "Redirect target should not end with /"

    # Check for invalid characters
    invalid_chars = ['<', '>', '"', '\\', '{', '}', '|', '^', '`']
    for char in invalid_chars:
        if char in target:
            return False, f"Redirect target contains invalid character: {char}"

    # Check for spaces
    if ' ' in target:
        return False, "Redirect target should not contain spaces (use %20 or -)"

    return True, ""


def update_astro_config_imports() -> str:
    """
    Generate import statement for astro.config.mjs to use generated redirects.

    Returns:
        Instruction text for manually updating astro.config.mjs
    """
    return """
To use auto-generated redirects in Astro:

1. Add this import at the top of astro.config.mjs:
   import autoRedirects from './redirects.config.mjs';

2. Merge with existing redirects:
   redirects: {
     ...autoRedirects,
     // Manual redirects below (take precedence over auto-generated)
     '/articles/mmt-uk-commentary-1': '/articles/mmtuk-commentary-1',
     // ... other manual redirects
   }

This allows manual redirects to override auto-generated ones if needed.
""".strip()
